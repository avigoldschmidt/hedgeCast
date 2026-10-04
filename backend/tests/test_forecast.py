import pytest

from hedgecast import topics, weather
from support import GAS_EVENT, RAIN_TODAY, RAIN_TOMORROW, onboard


def _forecast(world):
    response = world.client.get("/api/forecast")
    assert response.status_code == 200, response.text
    return response.json()


def _watch(world, *ids):
    return world.client.put("/api/me/topics", json={"topics": list(ids)})


# Profile


def test_profile_uses_chosen_industry(world):
    business = onboard(world)
    assert business["industry"] == "Café or coffee shop"
    assert business["topics"] == ["weather", "fuel", "prices"]
    assert business["bad_day_dollars"] == 600
    assert business["description"] == ""


def test_profile_for_restaurant(world):
    business = onboard(world, industry="Restaurant or bar")
    assert business["industry"] == "Restaurant or bar"
    assert business["topics"] == ["weather", "prices", "sports"]
    assert business["bad_day_dollars"] == 1500


def test_unknown_industry_is_rejected(world):
    response = world.client.post("/api/businesses", json={"name": "X", "industry": "Spaceport", "city_id": "new-york-ny"})
    assert response.status_code == 400


def test_industries_endpoint(world):
    response = world.client.get("/api/industries")
    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "Café or coffee shop" in names
    assert names == topics.industries()


def test_customer_chooses_what_to_watch(world):
    onboard(world)
    assert _watch(world, "rates").json()["topics"] == ["rates"]
    assert _watch(world).status_code == 422
    assert _watch(world, "other").status_code == 400


# Forecast


def test_forecast_mixes_weather_and_other_sectors(world):
    onboard(world)
    body = _forecast(world)
    by_topic = {}
    for card in body["cards"]:
        by_topic.setdefault(card["topic"], []).append(card)
    assert set(by_topic) == {"weather", "fuel", "prices"}
    assert 1 <= len(by_topic["weather"]) <= topics.PER_TOPIC
    assert [card["closes_at"] for card in body["cards"]] == sorted(card["closes_at"] for card in body["cards"])

    rain = next(card for card in body["cards"] if card["id"] == "weather-rain-NYC")
    assert rain["ticker"] == RAIN_TODAY
    assert [choice["ticker"] for choice in rain["choices"]] == [RAIN_TODAY, RAIN_TOMORROW]
    assert "Central Park" in rain["catch"]
    assert rain["why"] == topics.fallback_why("weather")
    assert rain["chance"] == pytest.approx(0.305)


def test_set_city_unlocks_weather(world):
    onboard(world, city_id=None)
    assert "weather" not in {card["topic"] for card in _forecast(world)["cards"]}
    response = world.client.put("/api/me/city", json={"city_id": "new-york-ny"})
    assert response.status_code == 200
    assert response.json()["city"]["id"] == "new-york-ny"
    assert any(card["id"] == "weather-rain-NYC" for card in _forecast(world)["cards"])


def test_kalshi_search_finds_open_markets(world):
    onboard(world)
    response = world.client.get("/api/search", params={"q": "gas"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cards"][0]["id"] == GAS_EVENT
    assert "Kalshi" in body["message"]


def test_kalshi_search_empty_query_is_rejected(world):
    onboard(world)
    assert world.client.get("/api/search", params={"q": "x"}).status_code == 400


def test_far_station_warning_is_written_by_code(world):
    onboard(world, "ann-arbor-mi")
    _watch(world, "weather")
    rain = next(card for card in _forecast(world)["cards"] if card["id"].startswith("weather-rain"))
    assert weather.BASIS_NOTES["high"] in rain["warnings"]


def test_forecast_uses_plain_wording(world):
    onboard(world)
    body = _forecast(world)
    gas = next(card for card in body["cards"] if card["id"] == GAS_EVENT)
    assert gas["title"] == "US gas prices at the end of October"
    assert gas["why"] == topics.fallback_why("fuel")


def test_forecast_asks_for_a_city_for_weather(world):
    onboard(world, city_id=None)
    body = _forecast(world)
    assert body["note"]
    assert {card["topic"] for card in body["cards"]} == {"fuel", "prices"}


def test_forecast_outage_is_a_503(world):
    onboard(world)
    world.market.fail("events", times=5)
    world.market.fail("series", times=10)
    assert world.client.get("/api/forecast").status_code == 503
