"""In-memory stand-ins for Kalshi market data and the Nessie bank. Used by tests and HEDGECAST_FAKES=1."""

import itertools
from datetime import datetime, time, timedelta, timezone

from . import weather
from .integrations.market_data import MarketDataError, MarketNotFound
from .integrations.money import BankError

RAIN_BOOK = {"no_dollars": [["0.6800", "3000"], ["0.6900", "2000"]], "yes_dollars": [["0.2900", "1500"]]}
HEAT_BOOK = {"no_dollars": [["0.8700", "2500"], ["0.8800", "1500"]], "yes_dollars": [["0.1000", "800"]]}
COLD_BOOK = {"no_dollars": [["0.8100", "2500"], ["0.8200", "1500"]], "yes_dollars": [["0.1600", "800"]]}


def _book(yes_ask, size="4000"):
    """A two-sided book whose YES ask is `yes_ask` with a two-cent spread."""
    ask = float(yes_ask)
    return {"no_dollars": [[f"{1 - ask:.4f}", size]], "yes_dollars": [[f"{ask - 0.02:.4f}", size]]}


# (event ticker, category, event title, [(market ticker, question, outcome, yes ask)])
GENERAL_EVENTS = [
    (
        "KXFEDDECISION-26DEC",
        "Economics",
        "Fed rate decision in December",
        [
            ("KXFEDDECISION-26DEC-C25", "Will the Fed cut rates by 25bps in December?", "Cut 25bps", "0.40"),
            ("KXFEDDECISION-26DEC-H0", "Will the Fed hold rates in December?", "Hold", "0.55"),
        ],
    ),
    (
        "KXGASPRICE-26OCT31",
        "Financials",
        "US gas prices at the end of October",
        [("KXGASPRICE-26OCT31-T3.50", "Will US gas average above $3.50 on Oct 31?", "Above $3.50", "0.30")],
    ),
    (
        "KXTARIFFLUMBER-26",
        "Politics",
        "New tariffs on Canadian lumber",
        [("KXTARIFFLUMBER-26", "Will the US raise tariffs on Canadian lumber this year?", "Yes", "0.20")],
    ),
    (
        "KXCPI-26OCT",
        "Economics",
        "CPI in October",
        [("KXCPI-26OCT-T0.3", "Will October CPI rise more than 0.3%?", "Above 0.3%", "0.35")],
    ),
    (
        "KXNBAGAME-26OCT10NYKBOS",
        "Sports",
        "Knicks vs Celtics in New York",
        [("KXNBAGAME-26OCT10NYKBOS-NYK", "Will the Knicks beat the Celtics?", "Knicks win", "0.55")],
    ),
]


class FakeMarketData:
    source = "fake markets"

    def __init__(self, today=None, days=2):
        self.today = today or datetime.now(timezone.utc).date()
        self.events = {}
        self.markets = {}
        self.books = {}
        self.errors = {}
        for offset in range(days):
            self._add_weather_day(self.today + timedelta(days=offset))
        later = _iso(datetime.combine(self.today + timedelta(days=30), time(20), tzinfo=timezone.utc))
        for event_ticker, category, title, markets in GENERAL_EVENTS:
            self._add_event(event_ticker, event_ticker.split("-")[0], category, title)
            for ticker, question, outcome, yes_ask in markets:
                self._add_market(event_ticker, ticker, question, outcome, later, _book(yes_ask), volume=50000)

    def _add_weather_day(self, day):
        stamp = weather.date_stamp(day)
        close = _iso(datetime.combine(day + timedelta(days=1), time(5), tzinfo=timezone.utc))
        when = day.strftime("%b %-d")
        rain_event = f"{weather.RAIN_SERIES}-{stamp}"
        self._add_event(rain_event, weather.RAIN_SERIES, weather.CATEGORY, f"Rain on {when}?")
        for station in weather.STATIONS:
            self._add_market(
                rain_event, f"{rain_event}-{station.code}", f"Will it rain in {station.name} on {when}?", station.name, close, RAIN_BOOK
            )
            for series, kind in ((station.high_series, "High"), (station.low_series, "Low")):
                if not series:
                    continue
                event = f"{series}-{stamp}"
                self._add_event(event, series, weather.CATEGORY, f"{kind} temperature in {station.name} on {when}")
                warm, cool = ("85", "60") if kind == "High" else ("65", "45")
                self._add_market(event, f"{event}-T{warm}", f"{kind} above {warm}° in {station.name}?", f"{int(warm) + 1}° or above", close, HEAT_BOOK, "greater")
                self._add_market(event, f"{event}-T{cool}", f"{kind} below {cool}° in {station.name}?", f"{int(cool) - 1}° or below", close, COLD_BOOK, "less")

    def _add_event(self, event_ticker, series, category, title):
        self.events[event_ticker] = {
            "event_ticker": event_ticker,
            "series_ticker": series,
            "category": category,
            "title": title,
            "sub_title": "",
        }

    def _add_market(self, event_ticker, ticker, title, outcome, close, book, strike_type=None, volume=1000):
        self.markets[ticker] = {
            "ticker": ticker,
            "event_ticker": event_ticker,
            "series": self.events[event_ticker]["series_ticker"],
            "title": title,
            "yes_sub_title": outcome,
            "strike_type": strike_type,
            "close_time": close,
            "status": "active",
            "result": "",
            "volume_fp": str(volume),
            "yes_ask_dollars": f"{1 - float(book['no_dollars'][0][0]):.4f}",
            "yes_bid_dollars": book["yes_dollars"][0][0],
        }
        self.books[ticker] = {"no_dollars": [list(level) for level in book["no_dollars"]], "yes_dollars": [list(level) for level in book["yes_dollars"]]}

    def open_events(self):
        self._maybe_fail("events")
        return [self._with_markets(ticker) for ticker in self.events]

    def event(self, event_ticker):
        self._maybe_fail("events")
        if event_ticker not in self.events:
            raise MarketNotFound(f"Kalshi has no {event_ticker}.")
        return self._with_markets(event_ticker)

    def series_markets(self, series_ticker):
        self._maybe_fail("series")
        return [dict(m) for m in self.markets.values() if m["series"] == series_ticker and m["status"] == "active"]

    def market(self, ticker):
        self._maybe_fail("market")
        if ticker not in self.markets:
            raise MarketNotFound(f"Kalshi returned no market for {ticker}.")
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

    def _with_markets(self, event_ticker):
        markets = [dict(m) for m in self.markets.values() if m["event_ticker"] == event_ticker]
        return dict(self.events[event_ticker], markets=markets)

    def _maybe_fail(self, kind):
        if self.errors.get(kind):
            self.errors[kind] -= 1
            raise MarketDataError(f"Simulated {kind} outage.")


def _iso(moment):
    return moment.isoformat().replace("+00:00", "Z")


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
