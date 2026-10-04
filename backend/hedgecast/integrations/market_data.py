import threading
import time

import requests


class MarketDataError(Exception):
    pass


class KalshiMarketData:
    """Read-only Kalshi market data. Public endpoints, so no account balance is involved."""

    def __init__(self, base_url, list_ttl=30.0, retries=3, timeout=15):
        self.base_url = base_url.rstrip("/")
        self.list_ttl = list_ttl
        self.retries = retries
        self.timeout = timeout
        self._cache = {}
        self._lock = threading.Lock()

    @property
    def source(self):
        return self.base_url.split("//", 1)[-1].split("/", 1)[0]

    def series_markets(self, series_ticker):
        key = ("series", series_ticker)
        with self._lock:
            hit = self._cache.get(key)
            if hit and time.monotonic() - hit[0] < self.list_ttl:
                return hit[1]
        payload = self._get("/markets", {"series_ticker": series_ticker, "status": "open", "limit": 200})
        markets = payload.get("markets") or []
        with self._lock:
            self._cache[key] = (time.monotonic(), markets)
        return markets

    def market(self, ticker):
        market = self._get(f"/markets/{ticker}").get("market")
        if not isinstance(market, dict):
            raise MarketDataError(f"Kalshi returned no market for {ticker}.")
        return market

    def orderbook(self, ticker):
        return self._get(f"/markets/{ticker}/orderbook").get("orderbook_fp") or {}

    def _get(self, path, params=None):
        delay = 0.5
        for attempt in range(self.retries + 1):
            try:
                response = requests.get(self.base_url + path, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                raise MarketDataError(f"Couldn't reach the market: {exc}") from exc
            if response.status_code == 429 and attempt < self.retries:
                time.sleep(delay)
                delay *= 2
                continue
            if not response.ok:
                raise MarketDataError(f"Market data error {response.status_code}: {response.text[:200]}")
            return response.json()
        raise MarketDataError("The market is busy. Try again in a moment.")
