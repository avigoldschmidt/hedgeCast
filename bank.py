import os

import nessie


class ConfigError(Exception):
    pass


class ApiError(Exception):
    pass


def configured():
    try:
        _require()
    except ConfigError:
        return False
    return nessie.configured()


def link(name, city):
    return _call(nessie.link, name, city)


def balance(customer_id, account_id):
    return _call(nessie.balance, customer_id, account_id)


def charge(customer_id, account_id, amount, memo):
    return _call(nessie.charge, customer_id, account_id, amount, memo)


def payout(customer_id, account_id, amount, memo):
    return _call(nessie.payout, customer_id, account_id, amount, memo)


def _require():
    provider = os.environ.get("BANK_PROVIDER", "nessie").strip().lower() or "nessie"
    if provider != "nessie":
        raise ConfigError("This bank provider is not configured yet.")


def _call(fn, *args):
    _require()
    try:
        return fn(*args)
    except nessie.ConfigError as exc:
        raise ConfigError(str(exc)) from exc
    except nessie.ApiError as exc:
        raise ApiError(str(exc)) from exc
