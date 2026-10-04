import os
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

import requests

import db

BASE_URL = "https://api.nessieisreal.com"
RESERVE_BALANCE = 100000
CHECKING_BALANCE = 1000
RESERVE_SETTING = "reserve_account_id"


class ConfigError(Exception):
    pass


class ApiError(Exception):
    pass


def configured():
    return bool(os.environ.get("NESSIE_API_KEY", "").strip())


def link(name, city):
    first_name, last_name = _split_name(name)
    customer_id = create_customer(first_name, last_name, city)
    account_id = create_account(customer_id, f"{name} checking", balance=CHECKING_BALANCE)
    db.set_setting(f"checking_opened:{account_id}", "1")
    _ensure_reserve()
    return customer_id, account_id


def balance(customer_id, account_id):
    account_id = _usable_account(customer_id, account_id)
    return account_id, Decimal(str(available_balance(account_id))).quantize(Decimal("0.01"))


def charge(customer_id, account_id, amount, memo):
    account_id = _usable_account(customer_id, account_id)
    amount = Decimal(str(amount))
    if amount <= 0:
        return account_id, None, Decimal("0.00")
    reserve_id = _ensure_reserve()
    moved = Decimal(whole_dollars(amount)).quantize(Decimal("0.01"))
    transfer_id = create_transfer(account_id, reserve_id, moved, memo)
    return account_id, transfer_id, moved


def payout(customer_id, account_id, amount, memo):
    account_id = _usable_account(customer_id, account_id)
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ApiError("A payout has to be greater than zero.")
    reserve_id = _ensure_reserve()
    moved = Decimal(whole_dollars(amount)).quantize(Decimal("0.01"))
    transfer_id = create_transfer(reserve_id, account_id, moved, memo)
    return account_id, transfer_id, moved


def api_key():
    key = os.environ.get("NESSIE_API_KEY", "").strip()
    if not key:
        raise ConfigError("The bank API key is missing. Accounts cannot be linked yet.")
    return key


def create_customer(first_name, last_name, city):
    payload = _request(
        "POST",
        "/customers",
        {
            "first_name": first_name,
            "last_name": last_name,
            "address": {
                "street_number": "1",
                "street_name": "Main",
                "city": city,
                "state": "MI",
                "zip": "48104",
            },
        },
    )
    return _object_id(payload)


def create_account(customer_id, nickname, balance=0):
    payload = _request(
        "POST",
        f"/customers/{customer_id}/accounts",
        {
            "type": "Checking",
            "nickname": nickname,
            "rewards": 0,
            "balance": balance,
        },
    )
    return _object_id(payload)


def get_account(account_id):
    payload = _request("GET", f"/accounts/{account_id}")
    if isinstance(payload, dict) and "balance" in payload:
        return payload
    raise ApiError("The bank account response was missing a balance.")


def available_balance(account_id):
    account = get_account(account_id)
    balance = float(account.get("balance") or 0)
    for deposit in _transactions(account_id, "deposits"):
        balance += float(deposit.get("amount") or 0)
    for withdrawal in _transactions(account_id, "withdrawals"):
        balance -= float(withdrawal.get("amount") or 0)
    return round(balance, 2)


def fund_account(account_id, amount, description):
    account = get_account(account_id)
    if float(account.get("balance") or 0) >= float(amount):
        return
    _request(
        "POST",
        f"/accounts/{account_id}/deposits",
        {
            "medium": "balance",
            "transaction_date": date.today().isoformat(),
            "status": "completed",
            "amount": amount,
            "description": description,
        },
    )


def whole_dollars(amount):
    value = Decimal(str(amount)).quantize(Decimal("0.01"))
    whole = int(value.to_integral_value(rounding=ROUND_HALF_UP))
    if value > 0 and whole < 1:
        return 1
    return whole


def _usable_account(customer_id, account_id):
    flag = f"checking_opened:{account_id}"
    raw = float(get_account(account_id).get("balance") or 0)
    if raw >= CHECKING_BALANCE:
        db.set_setting(flag, "1")
        return account_id
    if db.get_setting(flag) and raw > 0:
        return account_id
    # A deposit does not raise the balance stored at account creation.
    opened = create_account(customer_id, "Checking", balance=CHECKING_BALANCE)
    db.set_setting(f"checking_opened:{opened}", "1")
    return opened


def _ensure_reserve():
    existing = db.get_setting(RESERVE_SETTING)
    if not existing:
        customer_id = create_customer("HedgeCast", "Reserve", "Ann Arbor")
        existing = create_account(customer_id, "HedgeCast reserve", balance=RESERVE_BALANCE)
        db.set_setting(RESERVE_SETTING, existing)
    fund_account(existing, RESERVE_BALANCE, "HedgeCast reserve")
    return existing


def _split_name(name):
    parts = name.split()
    if len(parts) == 1:
        return parts[0][:40], "Business"
    return parts[0][:40], " ".join(parts[1:])[:40]


def create_transfer(payer_account_id, payee_account_id, amount, description):
    # The sandbox transfer body no longer accepts a payee, and amounts are whole
    # dollars. A withdrawal plus a deposit is what the ledger can count.
    amount = whole_dollars(amount)
    if amount <= 0:
        raise ApiError("The bank could not move that amount.")
    today = date.today().isoformat()
    movement = {
        "medium": "balance",
        "transaction_date": today,
        "status": "completed",
        "amount": amount,
        "description": description,
    }
    transfer = _request(
        "POST",
        f"/accounts/{payer_account_id}/transfers",
        {
            "status": "completed",
            "transaction_date": today,
            "amount": amount,
            "description": description,
        },
    )
    _request("POST", f"/accounts/{payer_account_id}/withdrawals", movement)
    _request("POST", f"/accounts/{payee_account_id}/deposits", movement)
    return _object_id(transfer)


def _transactions(account_id, kind):
    payload = _request("GET", f"/accounts/{account_id}/{kind}")
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _request(method, path, body=None):
    try:
        response = requests.request(
            method,
            f"{BASE_URL}{path}",
            params={"key": api_key()},
            json=body,
            timeout=20,
        )
    except requests.RequestException as exc:
        raise ApiError(f"The bank request failed: {_redact(exc)}") from exc
    try:
        payload = response.json()
    except ValueError:
        payload = {"message": response.text[:400]}
    if not response.ok:
        message = payload.get("message") if isinstance(payload, dict) else response.text
        raise ApiError(f"Bank {response.status_code}: {_redact(message or response.text[:400])}")
    return payload


def _redact(value):
    message = str(value)
    key = os.environ.get("NESSIE_API_KEY", "").strip()
    if key:
        message = message.replace(key, "[key]")
    if "?key=" in message:
        message = message.split("?key=", 1)[0]
    return message[:400]


def _object_id(payload):
    if isinstance(payload, dict):
        if payload.get("_id"):
            return payload["_id"]
        if payload.get("id"):
            return payload["id"]
        for value in payload.values():
            if isinstance(value, dict) and (value.get("_id") or value.get("id")):
                return value.get("_id") or value["id"]
    raise ApiError("The bank response had no account id.")
