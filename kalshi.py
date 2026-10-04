import base64
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

BASE_URL = (
    os.environ.get("KALSHI_BASE_URL", "https://external-api.demo.kalshi.co/trade-api/v2").strip().rstrip("/")
)
RESTING_BID = "0.0100"
_WEATHER_SERIES = []
_MARKET_CACHE = {"at": 0, "markets": []}


class ConfigError(Exception):
    pass


class ApiError(Exception):
    pass


def has_credentials():
    path = _key_file()
    return bool(os.environ.get("KALSHI_API_KEY_ID", "").strip() and path is not None and path.is_file())


def list_open_markets(limit=20):
    now = time.time()
    if _MARKET_CACHE["markets"] and now - _MARKET_CACHE["at"] < 30:
        return _MARKET_CACHE["markets"][:limit]
    markets = _weather_markets()
    if not markets:
        markets = _page_of_markets()
    summarized = [summarize_market(market) for market in markets if market.get("ticker")]
    summarized.sort(key=_quote_rank)
    _MARKET_CACHE["at"] = now
    _MARKET_CACHE["markets"] = summarized
    return summarized[:limit]


def portfolio_balance():
    if not has_credentials():
        raise ConfigError("Add KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH to .env to read the balance.")
    response = _signed("GET", "/portfolio/balance")
    payload = _payload(response)
    if not response.ok:
        raise ApiError(f"Kalshi {response.status_code}: {_error_text(payload, response)}")
    raw = payload.get("balance_dollars")
    if raw in (None, ""):
        cents = _decimal(payload.get("balance")) or Decimal("0")
        raw = cents / Decimal("100")
    return f"{Decimal(str(raw)):.2f}"


def _quote_rank(summary):
    value = _decimal(summary.get("yes_ask")) or Decimal("0")
    if Decimal("0") < value < Decimal("1"):
        return 0
    if value > 0:
        return 1
    return 2


def get_market(ticker):
    payload = _public_get(f"/markets/{ticker}")
    market = payload.get("market")
    if not isinstance(market, dict):
        raise ApiError(f"Kalshi returned no market for {ticker}.")
    return market


def summarize_market(market):
    price, crosses = order_price(market)
    title = market.get("title") or market.get("yes_sub_title") or market["ticker"]
    return {
        "ticker": market["ticker"],
        "title": title,
        "yes_subtitle": market.get("yes_sub_title") or "",
        "yes_ask": market.get("yes_ask_dollars") or "",
        "yes_bid": market.get("yes_bid_dollars") or "",
        "order_price": price,
        "crosses": crosses,
        "ask_label": price_label(market.get("yes_ask_dollars"), empty="No ask"),
        "bid_label": price_label(market.get("yes_bid_dollars")),
        "status": market.get("status") or "",
        "result": market.get("result") or "",
    }


def order_price(market):
    value = _decimal(market.get("yes_ask_dollars"))
    if value is not None and value > 0:
        return f"{value:.4f}", True
    return RESTING_BID, False


def price_label(raw, empty="—"):
    value = _decimal(raw)
    if value is None or value <= 0:
        return empty
    cents = (value * 100).quantize(Decimal("1"))
    return f"{cents}¢"


def classify_fill(fill_count, remaining_count, contract_count):
    filled = _decimal(fill_count) or Decimal("0")
    remaining = _decimal(remaining_count) or Decimal("0")
    if filled <= 0:
        return "resting", "Resting. No contracts have filled, so this hedge cannot be paid yet."
    if remaining > 0:
        return (
            "filled",
            f"Filled {fill_count} of {contract_count}. Payout uses the filled contracts.",
        )
    return "filled", ""


def settled_result(market):
    result = (market.get("result") or "").lower()
    if result in ("yes", "no"):
        return result
    return None


def buy_yes(ticker, count, limit_price):
    if not has_credentials():
        raise ConfigError(
            "Add KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH to .env to place an order."
        )
    client_order_id = str(uuid.uuid4())
    body = {
        "ticker": ticker,
        "side": "bid",
        "count": f"{Decimal(count):.2f}",
        "price": f"{Decimal(limit_price):.4f}",
        "time_in_force": "good_till_canceled",
        "self_trade_prevention_type": "taker_at_cross",
        "client_order_id": client_order_id,
    }
    response = _signed("POST", "/portfolio/events/orders", json_body=body)
    payload = _payload(response)
    if response.status_code != 201:
        raise ApiError(f"Kalshi {response.status_code}: {_error_text(payload, response)}")
    order = payload.get("order") if isinstance(payload, dict) and isinstance(payload.get("order"), dict) else payload
    if not isinstance(order, dict):
        raise ApiError(f"Kalshi order response was not an object: {payload}")
    return {
        "client_order_id": client_order_id,
        "order_id": order.get("order_id", ""),
        "fill_count": order.get("fill_count") or "0.00",
        "remaining_count": order.get("remaining_count") or "0.00",
    }


def _decimal(raw):
    if raw in (None, ""):
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def _key_file():
    raw = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "").strip().strip('"').strip("'")
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path


def _load_private_key():
    path = _key_file()
    if path is None or not path.is_file():
        raise ConfigError(
            "Set KALSHI_PRIVATE_KEY_PATH in .env to the Kalshi PEM file."
        )
    try:
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    except (ValueError, TypeError) as exc:
        raise ConfigError("The Kalshi private key file could not be read. It should be a PEM file.") from exc


def _sign(private_key, timestamp, method, path):
    message = f"{timestamp}{method}{path.split('?')[0]}".encode()
    if isinstance(private_key, Ed25519PrivateKey):
        signature = private_key.sign(message)
    else:
        signature = private_key.sign(
            message,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
    return base64.b64encode(signature).decode()


def _signed(method, path, params=None, json_body=None):
    private_key = _load_private_key()
    timestamp = str(int(time.time() * 1000))
    sign_path = urlparse(BASE_URL + path).path
    headers = {
        "KALSHI-ACCESS-KEY": os.environ["KALSHI_API_KEY_ID"].strip(),
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": _sign(private_key, timestamp, method, sign_path),
        "Content-Type": "application/json",
    }
    try:
        return requests.request(
            method,
            BASE_URL + path,
            params=params,
            json=json_body,
            headers=headers,
            timeout=20,
        )
    except requests.RequestException as exc:
        raise ApiError(f"Kalshi request failed: {exc}") from exc


def _public_get(path, params=None):
    try:
        response = requests.get(BASE_URL + path, params=params, timeout=20)
    except requests.RequestException as exc:
        raise ApiError(f"Kalshi request failed: {exc}") from exc
    if response.status_code == 401 and has_credentials():
        response = _signed("GET", path, params=params)
    payload = _payload(response)
    if not response.ok:
        raise ApiError(f"Kalshi {response.status_code}: {_error_text(payload, response)}")
    return payload


def _payload(response):
    try:
        return response.json()
    except ValueError:
        return {"message": response.text[:400]}


def _error_text(payload, response):
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])[:400]
        if payload.get("message"):
            return str(payload["message"])[:400]
    return response.text[:400]


def _page_of_markets():
    try:
        payload = _public_get("/markets", {"status": "open", "limit": 200, "mve_filter": "exclude"})
    except ApiError:
        payload = _public_get("/markets", {"status": "open", "limit": 200})
    return [market for market in payload.get("markets", []) if not _is_sports(market.get("ticker", ""))]


def _weather_markets():
    tickers = _weather_series()
    if not tickers:
        return []
    found = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for batch in pool.map(_open_series_markets, tickers):
            found.extend(batch)
    return found


def _weather_series():
    global _WEATHER_SERIES
    if _WEATHER_SERIES:
        return _WEATHER_SERIES
    cursor = None
    ranked = []
    for _ in range(12):
        params = {"limit": 200}
        if cursor:
            params["cursor"] = cursor
        payload = _public_get("/series", params)
        for series in payload.get("series", []):
            category = series.get("category") or ""
            title = (series.get("title") or "").lower()
            ticker = series.get("ticker") or ""
            if category != "Climate and Weather" or not ticker:
                continue
            if ticker.startswith("KXHIGHT"):
                rank = 0
            elif ticker.startswith("KXHIGH") or "high" in title:
                rank = 1
            elif "temperature" in title:
                rank = 2
            else:
                continue
            ranked.append((rank, ticker))
        cursor = payload.get("cursor")
        if not cursor:
            break
    ranked.sort()
    highs = [ticker for rank, ticker in ranked if rank == 0]
    _WEATHER_SERIES = (highs or [ticker for _rank, ticker in ranked])[:10]
    return _WEATHER_SERIES


def _open_series_markets(series_ticker):
    try:
        payload = _public_get(
            "/markets",
            {"status": "open", "limit": 12, "series_ticker": series_ticker, "mve_filter": "exclude"},
        )
    except ApiError:
        return []
    return payload.get("markets", [])


def _is_sports(ticker):
    prefix = ticker.split("-")[0]
    tokens = ("ATP", "WTA", "ITF", "NFL", "NBA", "MLB", "NHL", "UFC", "CS2", "LOL", "MATCH", "GAME", "MAP", "SPREAD", "TOTAL", "BTTS", "DART", "SOCCER")
    return any(token in prefix for token in tokens)
