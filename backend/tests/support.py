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


def onboard(world, city_id="new-york-ny", link=True):
    response = world.client.post("/api/businesses", json={"name": "Corner Cafe", "industry": "Cafe", "city_id": city_id})
    assert response.status_code == 200, response.text
    if link:
        response = world.client.post("/api/me/bank")
        assert response.status_code == 200, response.text
    return response.json()


def get_quote(world, tickers=(RAIN_TODAY,), payout=100, peril="rain"):
    response = world.client.post("/api/quotes", json={"peril": peril, "tickers": list(tickers), "payout_dollars": payout})
    assert response.status_code == 200, response.text
    return response.json()


def buy(world, tickers=(RAIN_TODAY,), payout=100, all_or_nothing=False):
    quote = get_quote(world, tickers, payout)
    response = world.client.post("/api/policies", json={"quote_id": quote["id"], "all_or_nothing": all_or_nothing})
    assert response.status_code == 200, response.text
    return quote, response.json()
