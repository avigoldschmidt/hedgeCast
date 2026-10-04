import threading
import time

import requests


class MarketDataError(Exception):
    pass


class MarketNotFound(MarketDataError):
    pass


class KalshiMarketData:
    """Read-only Kalshi market data. Public endpoints, so no account balance is involved."""

    def __init__(self, base_url, list_ttl=30.0, events_ttl=300.0, event_pages=5, retries=3, timeout=15):
        self.base_url = base_url.rstrip("/")
        self.list_ttl = list_ttl
        self.events_ttl = events_ttl
        self.event_pages = event_pages
        self.retries = retries
        self.timeout = timeout
        self._cache = {}
        self._lock = threading.Lock()

    @property
    def source(self):
        return self.base_url.split("//", 1)[-1].split("/", 1)[0]

    def open_events(self):
        """Open events with their markets nested. Kalshi has no search endpoint, so we cache a few pages and filter locally."""
        return self._cached(("events",), self.events_ttl, self._fetch_open_events)

    def event(self, event_ticker):
        return self._cached(("event", event_ticker), self.events_ttl, lambda: self._fetch_event(event_ticker))

    def series_markets(self, series_ticker):
        return self._cached(
            ("series", series_ticker),
            self.list_ttl,
            lambda: self._get("/markets", {"series_ticker": series_ticker, "status": "open", "limit": 200}).get("markets") or [],
        )

    def market(self, ticker):
        market = self._get(f"/markets/{ticker}").get("market")
        if not isinstance(market, dict):
            raise MarketNotFound(f"Kalshi returned no market for {ticker}.")
        return market

    def orderbook(self, ticker):
        return self._get(f"/markets/{ticker}/orderbook").get("orderbook_fp") or {}

    def _fetch_open_events(self):
        events, cursor = [], None
        for _page in range(self.event_pages):
            params = {"status": "open", "with_nested_markets": "true", "limit": 200}
            if cursor:
                params["cursor"] = cursor
            payload = self._get("/events", params)
            events.extend(payload.get("events") or [])
            cursor = payload.get("cursor")
            if not cursor:
                break
        return events

    def _fetch_event(self, event_ticker):
        payload = self._get(f"/events/{event_ticker}", {"with_nested_markets": "true"})
        event = payload.get("event")
        if not isinstance(event, dict):
            raise MarketNotFound(f"Kalshi returned no event for {event_ticker}.")
        if not event.get("markets"):
            event["markets"] = payload.get("markets") or []
        return event

    def _cached(self, key, ttl, fetch):
        with self._lock:
            hit = self._cache.get(key)
            if hit and time.monotonic() - hit[0] < ttl:
                return hit[1]
        value = fetch()
        with self._lock:
            self._cache[key] = (time.monotonic(), value)
        return value

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
            if response.status_code == 404:
                raise MarketNotFound(f"Kalshi has no {path.rsplit('/', 1)[-1]}.")
            if not response.ok:
                raise MarketDataError(f"Market data error {response.status_code}: {response.text[:200]}")
            return response.json()
        raise MarketDataError("The market is busy. Try again in a moment.")
