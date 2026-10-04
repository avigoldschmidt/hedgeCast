import pytest

from support import RAIN_TODAY, RAIN_TOMORROW, get_quote, onboard
from hedgecast.engine import executors
from hedgecast.engine.executors import HedgeError, LiveExecutor, PaperExecutor
from hedgecast.fakes import FakeMarketData
from hedgecast.integrations import kalshi

LEG = {"ticker": RAIN_TODAY, "side": "yes", "contracts": 100, "cost_ceiling_cents": 10000}


def test_paper_fill_uses_the_book():
    market = FakeMarketData()
    leg = dict(LEG, ticker=next(t for t in market.markets if t.startswith("KXRAIN")))
    [fill] = PaperExecutor(market, "0.97").execute([leg])
    assert fill["fill_price"] == "0.3100"
    assert fill["limit_price"] == "0.3200"  # worst level walked; avg fill can be tighter
    assert fill["fee_cents"] > 0
    assert fill["cost_cents"] > fill["fee_cents"]
    assert fill["order_id"].startswith("paper-")


def test_paper_is_all_or_nothing_across_legs(world):
    with pytest.raises(HedgeError):
        PaperExecutor(world.market, "0.97").execute(
            [LEG, dict(LEG, ticker=RAIN_TOMORROW, cost_ceiling_cents=1)],
        )


def test_live_reports_unfunded_account(monkeypatch, world):
    def broke(*_args):
        raise kalshi.ApiError("Kalshi 400: insufficient balance")

    monkeypatch.setattr(executors.kalshi, "buy", broke)
    with pytest.raises(HedgeError) as caught:
        LiveExecutor(world.market, "0.97").execute([LEG])
    assert caught.value.orphaned == []


def test_live_partial_fill_is_flagged(monkeypatch, world):
    monkeypatch.setattr(
        executors.kalshi, "buy", lambda *_a: {"order_id": "o-1", "fill_count": "60.00", "remaining_count": "40.00"}
    )
    with pytest.raises(HedgeError) as caught:
        LiveExecutor(world.market, "0.97").execute([LEG])
    assert caught.value.orphaned == [{"ticker": RAIN_TODAY, "order_id": "o-1"}]


def test_live_mode_with_unfunded_account_refunds_the_customer(monkeypatch, world):
    def broke(*_args):
        raise kalshi.ApiError("Kalshi 400: insufficient balance")

    monkeypatch.setattr(executors.kalshi, "buy", broke)
    world.service.executor = LiveExecutor(world.market, "0.97")
    onboard(world)
    quote = get_quote(world)
    policy = world.client.post("/api/policies", json={"quote_id": quote["id"]}).json()
    assert policy["status"] == "REFUNDED"
    assert "insufficient balance" in " ".join(e["message"] for e in policy["events"])
