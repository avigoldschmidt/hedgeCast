from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from hedgecast import config
from hedgecast.db import Database
from hedgecast.engine.executors import PaperExecutor
from hedgecast.engine.service import Service
from hedgecast.fakes import FakeBank, FakeMarketData
from hedgecast.main import create_app

TODAY = date(2026, 10, 4)
RAIN_TODAY = "KXRAIN-26OCT04-NYC"
RAIN_TOMORROW = "KXRAIN-26OCT05-NYC"
FED_EVENT = "KXFEDDECISION-26DEC"
FED_CUT = "KXFEDDECISION-26DEC-C25"
FED_HOLD = "KXFEDDECISION-26DEC-H0"
GAS_EVENT = "KXGASPRICE-26OCT31"
GAS = "KXGASPRICE-26OCT31-T3.50"
CAFE_INDUSTRY = "Café or coffee shop"


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, **delta):
        self.now += timedelta(**delta)


@pytest.fixture
def world(tmp_path):
    clock = Clock(datetime(2026, 10, 4, 12, tzinfo=timezone.utc))
    db = Database(tmp_path / "hedgecast.db")
    market = FakeMarketData(today=TODAY)
    bank = FakeBank()
    service = Service(db, market, bank, PaperExecutor(market, config.MAX_CONTRACT_PRICE), clock=clock)
    client = TestClient(create_app(service, worker=False))
    return SimpleNamespace(clock=clock, db=db, market=market, bank=bank, service=service, client=client)


def onboard(world, city_id="new-york-ny", link=True, industry=CAFE_INDUSTRY):
    response = world.client.post(
        "/api/businesses", json={"name": "Corner Cafe", "industry": industry, "city_id": city_id}
    )
    assert response.status_code == 200, response.text
    if link:
        response = world.client.post("/api/me/bank")
        assert response.status_code == 200, response.text
    return response.json()


def quote_body(tickers, payout, side="yes", plan=None):
    body = {"legs": [{"ticker": t, "side": side} for t in tickers], "payout_dollars": payout}
    if plan:
        body["plan"] = plan
    return body


def get_quote(world, tickers=(RAIN_TODAY,), payout=100, side="yes", plan=None):
    response = world.client.post("/api/quotes", json=quote_body(tickers, payout, side, plan))
    assert response.status_code == 200, response.text
    return response.json()


def buy(world, tickers=(RAIN_TODAY,), payout=100, all_or_nothing=False, side="yes", plan=None):
    quote = get_quote(world, tickers, payout, side, plan)
    response = world.client.post("/api/policies", json={"quote_id": quote["id"], "all_or_nothing": all_or_nothing})
    assert response.status_code == 200, response.text
    return quote, response.json()
