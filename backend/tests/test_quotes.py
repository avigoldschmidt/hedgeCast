from support import RAIN_TODAY, RAIN_TOMORROW, get_quote, onboard


def test_requests_need_a_business(world):
    assert world.client.get("/api/dashboard").status_code == 401


def test_new_york_rain_coverage_uses_central_park(world):
    onboard(world)
    body = world.client.get("/api/coverage", params={"peril": "rain"}).json()
    assert body["station"]["code"] == "NYC"
    assert body["station"]["basis_risk"] == "low"
    assert [day["date"] for day in body["days"]] == ["2026-10-04", "2026-10-05"]
    assert body["days"][0]["triggers"][0]["ticker"] == RAIN_TODAY


def test_ann_arbor_gets_a_far_station_with_a_disclosure(world):
    onboard(world, "ann-arbor-mi")
    body = world.client.get("/api/coverage", params={"peril": "rain"}).json()
    assert body["station"]["code"] == "CMH"
    assert body["station"]["basis_risk"] == "high"
    assert body["station"]["basis_note"]


def test_quote_premium_is_whole_dollars_and_adds_up(world):
    onboard(world)
    quote = get_quote(world, [RAIN_TODAY, RAIN_TOMORROW], payout=250)
    assert quote["premium_cents"] % 100 == 0
    assert quote["premium_cents"] == sum(quote["breakdown"].values())
    assert quote["max_payout_cents"] == 2 * 25000
    assert [leg["contracts"] for leg in quote["legs"]] == [250, 250]
    assert quote["thin_book"] == {"short": False, "max_payout_dollars": 5000}
    assert "Central Park" in quote["terms"] or "New York" in quote["terms"]


def test_quote_rejects_unknown_or_duplicate_days(world):
    onboard(world)
    bad = world.client.post("/api/quotes", json={"peril": "rain", "tickers": ["NOPE"], "payout_dollars": 10})
    assert bad.status_code == 400
    twice = world.client.post("/api/quotes", json={"peril": "rain", "tickers": [RAIN_TODAY, RAIN_TODAY], "payout_dollars": 10})
    assert twice.status_code == 400


def test_thin_book_reports_what_the_market_can_cover(world):
    onboard(world)
    world.market.set_book(RAIN_TODAY, [["0.7000", "40"]])
    quote = get_quote(world, payout=100)
    assert quote["thin_book"] == {"short": True, "max_payout_dollars": 40}


def test_likely_weather_gets_a_warning(world):
    onboard(world)
    world.market.set_book(RAIN_TODAY, [["0.1500", "500"]], [["0.8300", "500"]])
    quote = get_quote(world, payout=10)
    assert quote["warnings"]


def test_market_outage_is_a_503(world):
    onboard(world)
    world.market.fail("series")
    assert world.client.get("/api/coverage", params={"peril": "rain"}).status_code == 503
