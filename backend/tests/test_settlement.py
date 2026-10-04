import threading
import time

from fastapi.testclient import TestClient

from hedgecast.main import create_app
from support import FED_HOLD, RAIN_TODAY, RAIN_TOMORROW, buy, onboard

OPENING = 100000


def _policy(world, policy_id):
    return world.client.get(f"/api/policies/{policy_id}").json()


def _settle(world):
    return world.service.run_settlement()


def _paid_to_customer(world):
    return sum(t["cents"] for t in world.bank.transfers if t["kind"] == "pay")


def test_nothing_happens_before_the_window_closes(world):
    onboard(world)
    _quote, policy = buy(world)
    _settle(world)
    assert _policy(world, policy["id"])["status"] == "ACTIVE"


def test_closed_window_waits_for_the_official_result(world):
    onboard(world)
    _quote, policy = buy(world)
    world.clock.advance(hours=18)
    _settle(world)
    assert _policy(world, policy["id"])["status"] == "AWAITING_RESULT"


def test_yes_pays_exactly_once(world):
    onboard(world)
    _quote, policy = buy(world, payout=100)
    world.clock.advance(hours=18)
    world.market.settle(RAIN_TODAY, "yes")
    _settle(world)
    _settle(world)
    detail = _policy(world, policy["id"])
    assert detail["status"] == "PAID"
    assert detail["paid_cents"] == 10000
    assert _paid_to_customer(world) == 10000
    assert [m["kind"] for m in detail["movements"]] == ["premium", "payout"]
    assert detail["legs"][0]["result"] == "yes"


def test_no_expires_without_paying(world):
    onboard(world)
    _quote, policy = buy(world)
    world.clock.advance(hours=18)
    world.market.settle(RAIN_TODAY, "no")
    _settle(world)
    assert _policy(world, policy["id"])["status"] == "EXPIRED"
    assert _paid_to_customer(world) == 0


def test_no_side_pays_when_the_market_settles_no(world):
    onboard(world, city_id=None)
    _quote, policy = buy(world, tickers=(FED_HOLD,), payout=100, peril=None, side="no")
    world.clock.advance(days=31)
    world.market.settle(FED_HOLD, "no")
    _settle(world)
    detail = _policy(world, policy["id"])
    assert detail["status"] == "PAID"
    assert _paid_to_customer(world) == 10000


def test_no_side_expires_when_the_market_settles_yes(world):
    onboard(world, city_id=None)
    _quote, policy = buy(world, tickers=(FED_HOLD,), payout=100, peril=None, side="no")
    world.clock.advance(days=31)
    world.market.settle(FED_HOLD, "yes")
    _settle(world)
    assert _policy(world, policy["id"])["status"] == "EXPIRED"
    assert _paid_to_customer(world) == 0


def test_multi_day_pays_for_each_day_that_hit(world):
    onboard(world)
    _quote, policy = buy(world, tickers=(RAIN_TODAY, RAIN_TOMORROW), payout=50)
    world.clock.advance(hours=18)
    world.market.settle(RAIN_TODAY, "yes")
    _settle(world)
    midway = _policy(world, policy["id"])
    assert midway["status"] == "ACTIVE"
    assert [leg["result"] for leg in midway["legs"]] == ["yes", None]
    world.clock.advance(days=1)
    world.market.settle(RAIN_TOMORROW, "no")
    _settle(world)
    detail = _policy(world, policy["id"])
    assert detail["status"] == "PAID"
    assert detail["paid_cents"] == 5000


def test_payout_retries_then_goes_to_review(world):
    onboard(world)
    _quote, policy = buy(world)
    world.clock.advance(hours=18)
    world.market.settle(RAIN_TODAY, "yes")
    world.bank.fail("pay", times=5)
    _settle(world)
    _settle(world)
    assert world.bank.failures["pay"] == 4, "second run must wait for the backoff"
    world.clock.advance(minutes=3)
    _settle(world)
    world.clock.advance(minutes=5)
    _settle(world)
    detail = _policy(world, policy["id"])
    assert detail["status"] == "NEEDS_REVIEW"
    assert _paid_to_customer(world) == 0
    assert detail["movements"][-1]["status"] == "failed"


def test_payout_recovers_after_a_failure(world):
    onboard(world)
    _quote, policy = buy(world)
    world.clock.advance(hours=18)
    world.market.settle(RAIN_TODAY, "yes")
    world.bank.fail("pay")
    _settle(world)
    world.clock.advance(minutes=3)
    _settle(world)
    detail = _policy(world, policy["id"])
    assert detail["status"] == "PAID"
    assert _paid_to_customer(world) == 10000
    assert [(m["kind"], m["status"]) for m in detail["movements"]] == [("premium", "done"), ("payout", "done")]


def test_concurrent_runs_never_double_pay(world):
    onboard(world)
    _quote, policy = buy(world)
    world.clock.advance(hours=18)
    world.market.settle(RAIN_TODAY, "yes")
    threads = [threading.Thread(target=_settle, args=(world,)) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert _paid_to_customer(world) == 10000


def test_market_outage_keeps_policies_open(world):
    onboard(world)
    _quote, policy = buy(world)
    world.clock.advance(hours=18)
    world.market.fail("market", times=3)
    summary = _settle(world)
    assert summary["errors"] == 1
    assert _policy(world, policy["id"])["status"] == "AWAITING_RESULT"


def test_voided_market_needs_review(world):
    onboard(world)
    _quote, policy = buy(world)
    world.clock.advance(hours=18)
    world.market.settle(RAIN_TODAY, "void")
    _settle(world)
    assert _policy(world, policy["id"])["status"] == "NEEDS_REVIEW"


def test_demo_resolve_pays_immediately_and_only_once(world):
    onboard(world)
    _quote, policy = buy(world)
    response = world.client.post(f"/api/ops/policies/{policy['id']}/resolve", json={"result": "yes"})
    assert response.status_code == 200
    assert response.json()["status"] == "PAID"
    again = world.client.post(f"/api/ops/policies/{policy['id']}/resolve", json={"result": "yes"})
    assert again.status_code == 409
    _settle(world)
    assert _paid_to_customer(world) == 10000


def test_worker_starts_with_the_app_and_settles(world):
    onboard(world)
    _quote, policy = buy(world)
    world.clock.advance(hours=18)
    world.market.settle(RAIN_TODAY, "yes")
    with TestClient(create_app(world.service, worker=True)) as client:
        deadline = time.monotonic() + 5
        while world.service.last_run_at is None and time.monotonic() < deadline:
            time.sleep(0.02)
        ops = client.get("/api/ops").json()
    assert ops["worker"]["enabled"] is True
    assert ops["worker"]["last_result"]
    assert _policy(world, policy["id"])["status"] == "PAID"


def test_ops_overview_and_manual_settle(world):
    onboard(world)
    buy(world)
    body = world.client.post("/api/ops/settle").json()
    assert body["hedge_mode"] == "paper"
    assert body["counts"] == {"ACTIVE": 1}
    assert body["worker"]["last_run_at"]
    assert body["policies"][0]["simulated"] is True
    assert body["reserve_balance_cents"] > 0
