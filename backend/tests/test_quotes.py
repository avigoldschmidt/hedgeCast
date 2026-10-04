from support import FED_CUT, FED_EVENT, FED_HOLD, RAIN_TODAY, RAIN_TOMORROW, get_quote, onboard, quote_body


def test_requests_need_a_business(world):
    assert world.client.get("/api/dashboard").status_code == 401


# Market discovery


def test_search_lists_every_category_most_traded_first(world):
    body = world.client.get("/api/markets").json()
    assert {"Economics", "Financials", "Politics", "Climate and Weather"} <= set(body["categories"])
    assert body["events"][0]["category"] != "Climate and Weather"


def test_search_by_text_and_category(world):
    fed = world.client.get("/api/markets", params={"q": "fed"}).json()["events"]
    assert [event["event_ticker"] for event in fed] == [FED_EVENT]
    assert {m["ticker"] for m in fed[0]["markets"]} == {FED_CUT, FED_HOLD}
    politics = world.client.get("/api/markets", params={"category": "Politics"}).json()["events"]
    assert [event["category"] for event in politics] == ["Politics"]


def test_event_detail_and_unknown_event(world):
    body = world.client.get(f"/api/events/{FED_EVENT}").json()
    assert body["category"] == "Economics"
    assert [m["outcome"] for m in body["markets"]] == ["Cut 25bps", "Hold"]
    assert world.client.get("/api/events/NOPE").status_code == 404


def test_search_outage_is_a_503(world):
    world.market.fail("events")
    assert world.client.get("/api/markets").status_code == 503


# Quotes on any market


def test_quote_any_market_on_the_no_side(world):
    onboard(world, city_id=None)
    yes = get_quote(world, [FED_HOLD], payout=100, peril=None, side="yes")
    no = get_quote(world, [FED_HOLD], payout=100, peril=None, side="no")
    assert no["category"] == "Economics"
    assert no["title"] == "Fed rate decision in December"
    assert no["station"] is None
    assert no["legs"][0]["side"] == "no"
    assert no["legs"][0]["avg_price"] == "0.4700"
    assert no["legs"][0]["implied_probability"] < yes["legs"][0]["implied_probability"]
    assert "settles NO" in no["terms"]
    assert no["premium_cents"] % 100 == 0


def test_quote_across_events_names_both(world):
    onboard(world, city_id=None)
    quote = get_quote(world, [FED_CUT, "KXGASPRICE-26OCT31-T3.50"], payout=50, peril=None)
    assert quote["title"] == "Fed rate decision in December + 1 more"
    assert quote["max_payout_cents"] == 2 * 5000


def test_quote_rejects_unknown_duplicate_or_closed_markets(world):
    onboard(world)
    assert world.client.post("/api/quotes", json=quote_body(["NOPE"], 10, None)).status_code == 400
    assert world.client.post("/api/quotes", json=quote_body([FED_CUT, FED_CUT], 10, None)).status_code == 400
    world.market.settle(FED_CUT, "yes")
    assert world.client.post("/api/quotes", json=quote_body([FED_CUT], 10, None)).status_code == 400


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


# Optional weather shortcut


def test_new_york_rain_uses_central_park(world):
    onboard(world)
    body = world.client.get("/api/weather", params={"peril": "rain"}).json()
    assert body["station"]["code"] == "NYC"
    assert body["station"]["basis_risk"] == "low"
    assert [day["date"] for day in body["days"]] == ["2026-10-04", "2026-10-05"]
    assert body["days"][0]["triggers"][0]["ticker"] == RAIN_TODAY


def test_ann_arbor_gets_a_far_station_with_a_disclosure(world):
    onboard(world, "ann-arbor-mi")
    body = world.client.get("/api/weather", params={"peril": "rain"}).json()
    assert body["station"]["code"] == "CMH"
    assert body["station"]["basis_risk"] == "high"
    assert body["station"]["basis_note"]


def test_weather_needs_a_city(world):
    onboard(world, city_id=None)
    assert world.client.get("/api/weather", params={"peril": "rain"}).status_code == 409
    assert world.client.post("/api/quotes", json=quote_body([RAIN_TODAY], 10, "rain")).status_code == 409


def test_weather_quote_keeps_the_station_disclosure(world):
    onboard(world)
    quote = get_quote(world, [RAIN_TODAY, RAIN_TOMORROW], payout=250)
    assert quote["premium_cents"] % 100 == 0
    assert quote["premium_cents"] == sum(quote["breakdown"].values())
    assert quote["max_payout_cents"] == 2 * 25000
    assert quote["thin_book"] == {"short": False, "max_payout_dollars": 5000}
    assert quote["station"]["code"] == "NYC"
    assert quote["title"] == "Rain cover · New York City (Central Park)"
    assert quote["legs"][0]["label"] == "Sun, Oct 4 · Any measurable rain"
    assert "Central Park" in quote["terms"]


def test_weather_quote_rejects_other_stations(world):
    onboard(world)
    other = world.client.post("/api/quotes", json=quote_body(["KXRAIN-26OCT04-CHI"], 10, "rain"))
    assert other.status_code == 400


def test_weather_outage_is_a_503(world):
    onboard(world)
    world.market.fail("series")
    assert world.client.get("/api/weather", params={"peril": "rain"}).status_code == 503
