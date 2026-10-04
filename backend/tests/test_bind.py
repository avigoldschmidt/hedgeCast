from support import RAIN_TODAY, buy, get_quote, onboard

OPENING = 100000


def _bind(world, quote, all_or_nothing=False):
    return world.client.post("/api/policies", json={"quote_id": quote["id"], "all_or_nothing": all_or_nothing})


def _checking(world):
    business = world.client.get("/api/me").json()
    return business["bank"]["balance_cents"]


def test_happy_path_charges_once_and_hedges(world):
    onboard(world)
    quote, policy = buy(world, payout=100)
    assert policy["status"] == "ACTIVE"
    assert _checking(world) == OPENING - quote["premium_cents"]
    leg = policy["legs"][0]
    assert leg["simulated"] and leg["fill_price"] and leg["cost_cents"] > 0
    assert [(m["kind"], m["status"]) for m in policy["movements"]] == [("premium", "done")]
    kinds = [e["kind"] for e in policy["events"]]
    assert kinds == ["created", "premium_charged", "hedged", "active"]


def test_bank_must_be_linked(world):
    onboard(world, link=False)
    quote = get_quote(world)
    assert _bind(world, quote).status_code == 409


def test_a_quote_buys_only_once(world):
    onboard(world)
    quote = get_quote(world)
    assert _bind(world, quote).status_code == 200
    again = _bind(world, quote)
    assert again.status_code == 409
    assert _checking(world) == OPENING - quote["premium_cents"]
    assert len(world.client.get("/api/policies").json()) == 1


def test_expired_quote_is_refused(world):
    onboard(world)
    quote = get_quote(world)
    world.clock.advance(seconds=60)
    assert _bind(world, quote).status_code == 409
    assert _checking(world) == OPENING


def test_other_businesses_cannot_use_my_quote(world):
    onboard(world)
    quote = get_quote(world)
    onboard(world)
    assert _bind(world, quote).status_code == 404


def test_declined_charge_leaves_nothing_behind(world):
    onboard(world)
    quote = get_quote(world)
    world.bank.fail("charge")
    response = _bind(world, quote)
    assert response.status_code == 402
    assert world.client.get("/api/policies").json() == []
    assert _checking(world) == OPENING


def test_price_move_refunds_the_premium(world):
    onboard(world)
    quote = get_quote(world)
    world.market.set_book(RAIN_TODAY, [["0.2000", "5000"]])
    response = _bind(world, quote)
    assert response.status_code == 200
    policy = response.json()
    assert policy["status"] == "REFUNDED"
    assert [(m["kind"], m["status"]) for m in policy["movements"]] == [("premium", "done"), ("refund", "done")]
    assert _checking(world) == OPENING


def test_failed_refund_goes_to_review(world):
    onboard(world)
    quote = get_quote(world)
    world.market.set_book(RAIN_TODAY, [])
    world.bank.fail("pay")
    policy = _bind(world, quote).json()
    assert policy["status"] == "NEEDS_REVIEW"
    assert policy["movements"][-1] == {**policy["movements"][-1], "kind": "refund", "status": "failed"}


def test_short_book_needs_explicit_all_or_nothing(world):
    onboard(world)
    world.market.set_book(RAIN_TODAY, [["0.6900", "40"]])
    quote = get_quote(world, payout=100)
    assert _bind(world, quote).status_code == 409
    assert _checking(world) == OPENING


def test_all_or_nothing_buys_if_the_book_refills(world):
    onboard(world)
    world.market.set_book(RAIN_TODAY, [["0.6900", "40"]])
    quote = get_quote(world, payout=100)
    world.market.set_book(RAIN_TODAY, [["0.6900", "500"]])
    policy = _bind(world, quote, all_or_nothing=True).json()
    assert policy["status"] == "ACTIVE"


def test_all_or_nothing_refunds_if_the_book_stays_short(world):
    onboard(world)
    world.market.set_book(RAIN_TODAY, [["0.6900", "40"]])
    quote = get_quote(world, payout=100)
    policy = _bind(world, quote, all_or_nothing=True).json()
    assert policy["status"] == "REFUNDED"
    assert _checking(world) == OPENING


def test_dashboard_totals(world):
    onboard(world)
    quote, _policy = buy(world, payout=100)
    body = world.client.get("/api/dashboard").json()
    assert body["active_coverage_cents"] == 10000
    assert body["premiums_paid_cents"] == quote["premium_cents"]
    assert body["payouts_received_cents"] == 0
    assert body["activity"]
