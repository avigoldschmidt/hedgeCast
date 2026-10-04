"""In-memory stand-ins for Kalshi market data and the Nessie bank. Used by tests and HEDGECAST_FAKES=1."""

import itertools
from datetime import datetime, time, timedelta, timezone

from . import geo
from .engine.catalog import RAIN_SERIES, date_stamp
from .integrations.market_data import MarketDataError
from .integrations.money import BankError

RAIN_BOOK = {"no_dollars": [["0.6800", "3000"], ["0.6900", "2000"]], "yes_dollars": [["0.2900", "1500"]]}
HEAT_BOOK = {"no_dollars": [["0.8700", "2500"], ["0.8800", "1500"]], "yes_dollars": [["0.1000", "800"]]}
COLD_BOOK = {"no_dollars": [["0.8100", "2500"], ["0.8200", "1500"]], "yes_dollars": [["0.1600", "800"]]}


class FakeMarketData:
    source = "fake markets"

    def __init__(self, today=None, days=2):
        self.today = today or datetime.now(timezone.utc).date()
        self.markets = {}
        self.books = {}
        self.errors = {}
        for offset in range(days):
            self._add_day(self.today + timedelta(days=offset))

    def _add_day(self, day):
        stamp = date_stamp(day)
        close = datetime.combine(day + timedelta(days=1), time(5), tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        for station in geo.STATIONS:
            self._add(RAIN_SERIES, f"{RAIN_SERIES}-{stamp}", f"{RAIN_SERIES}-{stamp}-{station.code}", "greater", station.name, close, RAIN_BOOK)
            if station.high_series:
                event = f"{station.high_series}-{stamp}"
                self._add(station.high_series, event, f"{event}-T85", "greater", "86° or above", close, HEAT_BOOK)
                self._add(station.high_series, event, f"{event}-T60", "less", "59° or below", close, COLD_BOOK)
            if station.low_series:
                event = f"{station.low_series}-{stamp}"
                self._add(station.low_series, event, f"{event}-T65", "greater", "66° or above", close, HEAT_BOOK)
                self._add(station.low_series, event, f"{event}-T45", "less", "44° or below", close, COLD_BOOK)

    def _add(self, series, event, ticker, strike_type, subtitle, close, book):
        self.markets[ticker] = {
            "ticker": ticker,
            "event_ticker": event,
            "series": series,
            "strike_type": strike_type,
            "yes_sub_title": subtitle,
            "close_time": close,
            "status": "active",
            "result": "",
            "yes_ask_dollars": f"{1 - float(book['no_dollars'][0][0]):.4f}",
            "yes_bid_dollars": book["yes_dollars"][0][0],
        }
        self.books[ticker] = {"no_dollars": [list(level) for level in book["no_dollars"]], "yes_dollars": list(book["yes_dollars"])}

    def series_markets(self, series_ticker):
        self._maybe_fail("series")
        return [dict(m) for m in self.markets.values() if m["series"] == series_ticker and m["status"] == "active"]

    def market(self, ticker):
        self._maybe_fail("market")
        if ticker not in self.markets:
            raise MarketDataError(f"Kalshi returned no market for {ticker}.")
        return dict(self.markets[ticker])

    def orderbook(self, ticker):
        self._maybe_fail("orderbook")
        return self.books.get(ticker, {})

    def set_book(self, ticker, no_levels, yes_levels=()):
        self.books[ticker] = {"no_dollars": [list(level) for level in no_levels], "yes_dollars": [list(level) for level in yes_levels]}

    def settle(self, ticker, result):
        self.markets[ticker].update(status="finalized", result=result)

    def close(self, ticker, when):
        self.markets[ticker]["close_time"] = when.isoformat()

    def fail(self, kind, times=1):
        self.errors[kind] = times

    def _maybe_fail(self, kind):
        if self.errors.get(kind):
            self.errors[kind] -= 1
            raise MarketDataError(f"Simulated {kind} outage.")


class FakeBank:
    unit_cents = 100
    name = "Fake bank"

    def __init__(self, opening_cents=100000, reserve_cents=10000000):
        self.opening_cents = opening_cents
        self.balances = {"reserve": reserve_cents}
        self.transfers = []
        self.failures = {}
        self._ids = itertools.count(1)

    def configured(self):
        return True

    def link(self, name, city):
        n = next(self._ids)
        account = f"fake-acct-{n}"
        self.balances[account] = self.opening_cents
        return f"fake-cust-{n}", account

    def balance_cents(self, customer_id, account_id):
        self._maybe_fail("balance")
        return account_id, self.balances.setdefault(account_id, self.opening_cents)

    def charge(self, customer_id, account_id, cents, memo):
        return self._move("charge", account_id, "reserve", cents, memo)

    def pay(self, customer_id, account_id, cents, memo):
        return self._move("pay", "reserve", account_id, cents, memo)

    def reserve_balance_cents(self):
        return self.balances["reserve"]

    def fail(self, kind, times=1):
        self.failures[kind] = times

    def _maybe_fail(self, kind):
        if self.failures.get(kind):
            self.failures[kind] -= 1
            raise BankError(f"Simulated {kind} failure.")

    def _move(self, kind, source, target, cents, memo):
        self._maybe_fail(kind)
        if cents <= 0 or cents % self.unit_cents:
            raise BankError("The bank only moves whole dollars.")
        for account in (source, target):
            self.balances.setdefault(account, self.opening_cents)
        self.balances[source] -= cents
        self.balances[target] += cents
        transfer_id = f"fake-transfer-{next(self._ids)}"
        self.transfers.append({"kind": kind, "from": source, "to": target, "cents": cents, "memo": memo, "id": transfer_id})
        account = target if kind == "pay" else source
        return account, transfer_id, cents
