from support import FED_CUT, FED_HOLD, GAS, RAIN_TODAY, RAIN_TOMORROW, get_quote, onboard, quote_body


def test_requests_need_a_business(world):
    assert world.client.get("/api/forecast").status_code == 401


def test_quote_any_market_on_the_no_side(world):
    onboard(world, city_id=None)
    yes = get_quote(world, [FED_HOLD], payout=100, side="yes")
    no = get_quote(world, [FED_HOLD], payout=100, side="no")
    assert no["topic"] == "rates"
    assert no["title"] == "Fed rate decision in December"
    assert no["legs"][0]["side"] == "no"
    assert no["legs"][0]["avg_price"] == "0.4700"
    assert no["legs"][0]["implied_probability"] < yes["legs"][0]["implied_probability"]
    assert "settles NO" in no["terms"]
    assert no["premium_cents"] % 100 == 0


def test_quote_across_events_names_both(world):
    onboard(world, city_id=None)
    quote = get_quote(world, [FED_CUT, GAS], payout=50)
    assert quote["title"] == "Fed rate decision in December + 1 more"
    assert quote["max_payout_cents"] == 2 * 5000


def test_quote_carries_the_plan_words(world):
    onboard(world)
    plan = {"topic": "weather", "title": "Rain Sunday at the patio", "why": "Rain empties your patio.", "catch": "Pays on Central Park."}
    quote = get_quote(world, [RAIN_TODAY, RAIN_TOMORROW], payout=250, plan=plan)
    assert {key: quote[key] for key in plan} == plan
    assert quote["premium_cents"] == sum(quote["breakdown"].values())
    assert quote["max_payout_cents"] == 2 * 25000
    assert quote["thin_book"] == {"short": False, "max_payout_dollars": 5000}


def test_weather_quote_without_a_plan_is_still_a_weather_topic(world):
    onboard(world)
    assert get_quote(world)["topic"] == "weather"


def test_quote_rejects_unknown_duplicate_or_closed_markets(world):
    onboard(world)
    assert world.client.post("/api/quotes", json=quote_body(["NOPE"], 10)).status_code == 400
    assert world.client.post("/api/quotes", json=quote_body([FED_CUT, FED_CUT], 10)).status_code == 400
    world.market.settle(FED_CUT, "yes")
    assert world.client.post("/api/quotes", json=quote_body([FED_CUT], 10)).status_code == 400


def test_quote_rejects_unknown_topics(world):
    onboard(world)
    bad = quote_body([FED_CUT], 10, plan={"topic": "astrology", "title": "x"})
    assert world.client.post("/api/quotes", json=bad).status_code == 422


def test_thin_book_reports_what_the_market_can_cover(world):
    onboard(world)
    world.market.set_book(RAIN_TODAY, [["0.7000", "40"]])
    quote = get_quote(world, payout=100)
    assert quote["thin_book"] == {"short": True, "max_payout_dollars": 40}


def test_likely_outcome_gets_a_warning(world):
    onboard(world)
    world.market.set_book(RAIN_TODAY, [["0.1500", "500"]], [["0.8300", "500"]])
    quote = get_quote(world, payout=10)
    assert quote["warnings"]
