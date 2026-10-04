import json

import pytest

from hedgecast import advisor, topics, weather
from support import FED_EVENT, FED_HOLD, GAS, GAS_EVENT, RAIN_TODAY, RAIN_TOMORROW, onboard


def _forecast(world):
    response = world.client.get("/api/forecast")
    assert response.status_code == 200, response.text
    return response.json()


def _watch(world, *ids):
    return world.client.put("/api/me/topics", json={"topics": list(ids)})


# Profile


def test_profile_picks_topics_for_the_business(world):
    business = onboard(world)
    assert business["industry"] == "Café or coffee shop"
    assert business["topics"] == ["weather", "fuel", "prices"]
    assert business["bad_day_dollars"] == 600
    assert business["description"].startswith("We run a small coffee shop")


def test_profile_falls_back_when_the_advisor_is_down(world):
    world.advisor.failing = True
    business = onboard(world, description="A rooftop bar in Brooklyn")
    assert business["industry"] == "Restaurant or bar"
    assert business["topics"] == ["weather", "prices", "sports"]


def test_clean_profile_keeps_only_known_values():
    raw = {"industry": "Spaceport", "topics": ["fuel", "astrology", "fuel", "rates"], "bad_day_dollars": 10**9}
    profile = advisor.clean_profile(raw, "a food truck")
    assert profile == {"industry": "Food truck", "topics": ["fuel", "rates"], "bad_day_dollars": 500}


class _Response:
    def __init__(self, status, payload):
        self.status_code = status
        self.ok = status < 400
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_gemini_client_asks_for_json_and_reads_it_back(monkeypatch):
    sent = {}

    def post(url, headers, json, timeout):
        sent.update(url=url, headers=headers, body=json)
        text = '{"industry": "Food truck", "topics": ["fuel"], "bad_day_dollars": 400}'
        return _Response(200, {"candidates": [{"content": {"parts": [{"text": "thinking", "thought": True}, {"text": text}]}}]})

    monkeypatch.setattr(advisor.requests, "post", post)
    gemini = advisor.GeminiAdvisor("key-123", "gemini-3.8-flash")
    assert gemini.profile("Tacos on wheels", "Austin, TX")["industry"] == "Food truck"
    assert sent["url"].endswith("/models/gemini-3.8-flash:generateContent")
    assert sent["headers"] == {"x-goog-api-key": "key-123"}
    config = sent["body"]["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert config["thinkingConfig"] == {"thinkingLevel": "low"}


def test_gemini_errors_become_advisor_errors(monkeypatch):
    monkeypatch.setattr(advisor.requests, "post", lambda *a, **k: _Response(429, {"error": "slow down"}))
    with pytest.raises(advisor.AdvisorError):
        advisor.GeminiAdvisor("key", "gemini-3.8-flash").curate({}, [])


def test_customer_chooses_what_to_watch(world):
    onboard(world)
    assert _watch(world, "rates").json()["topics"] == ["rates"]
    assert _watch(world).status_code == 422
    assert _watch(world, "other").status_code == 400


# Forecast


def test_forecast_mixes_weather_and_other_sectors(world):
    onboard(world)
    body = _forecast(world)
    assert body["tailored"] is True
    by_topic = {}
    for card in body["cards"]:
        by_topic.setdefault(card["topic"], []).append(card)
    assert set(by_topic) == {"weather", "fuel", "prices"}
    assert len(by_topic["weather"]) == 2, "at most two cards per topic"
    assert [card["closes_at"] for card in body["cards"]] == sorted(card["closes_at"] for card in body["cards"])

    rain = next(card for card in body["cards"] if card["id"] == "weather-rain-NYC")
    assert rain["ticker"] == RAIN_TODAY
    assert [choice["ticker"] for choice in rain["choices"]] == [RAIN_TODAY, RAIN_TOMORROW]
    assert "Central Park" in rain["catch"]
    assert rain["why"] == "Corner Cafe loses money when this happens."
    assert rain["chance"] == pytest.approx(0.305)


def test_far_station_warning_is_written_by_code(world):
    onboard(world, "ann-arbor-mi")
    _watch(world, "weather")
    rain = next(card for card in _forecast(world)["cards"] if card["id"].startswith("weather-rain"))
    assert weather.BASIS_NOTES["high"] in rain["warnings"]


def test_curation_drops_markets_the_advisor_invented(world):
    onboard(world)
    _watch(world, "rates")
    plan = {"side": "no", "title": "Fed holds in December", "why": "Your credit line stays expensive.", "catch": "Pays on the Fed decision."}
    world.advisor.plans = [
        dict(plan, group=FED_EVENT, ticker="KXMADEUP-1"),
        dict(plan, group="NOT-A-GROUP", ticker=FED_HOLD),
        dict(plan, group=FED_EVENT, ticker=FED_HOLD),
    ]
    cards = _forecast(world)["cards"]
    assert [(card["ticker"], card["side"], card["title"]) for card in cards] == [(FED_HOLD, "no", "Fed holds in December")]
    assert cards[0]["chance"] == pytest.approx(1 - 0.54), "chance is for the side that pays"


def test_forecast_still_loads_when_the_advisor_fails(world):
    onboard(world)
    world.advisor.failing = True
    body = _forecast(world)
    assert body["tailored"] is False
    assert body["cards"]
    assert all(card["why"] and card["catch"] for card in body["cards"])


def test_forecast_without_any_advisor_uses_plain_wording(world):
    onboard(world)
    world.service.advisor = None
    body = _forecast(world)
    assert body["tailored"] is False
    gas = next(card for card in body["cards"] if card["id"] == GAS_EVENT)
    assert gas["title"] == "US gas prices at the end of October"
    assert gas["why"] == topics.fallback_why("fuel")


def test_curation_is_cached_for_a_few_hours(world):
    onboard(world)
    _forecast(world)
    _forecast(world)
    assert world.advisor.curate_calls == 1
    world.clock.advance(hours=4)
    _forecast(world)
    assert world.advisor.curate_calls == 2


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


# Ask anything


def _ask(world, text):
    response = world.client.post("/api/ask", json={"text": text})
    assert response.status_code == 200, response.text
    return response.json()


def test_ask_maps_a_worry_to_a_market(world):
    onboard(world)
    body = _ask(world, "What if gas prices jump before Halloween")
    assert [card["ticker"] for card in body["cards"]] == [GAS]
    assert body["cards"][0]["topic"] == "fuel"


def test_ask_about_weather_uses_the_local_station(world):
    onboard(world)
    body = _ask(world, "a rainy weekend")
    assert body["cards"][0]["id"] == "weather-rain-NYC"


def test_ask_says_plainly_when_nothing_covers_it(world):
    onboard(world)
    body = _ask(world, "a unicorn parade")
    assert body["cards"] == []
    assert body["message"].startswith("No market covers that")


def test_ask_works_without_the_advisor(world):
    onboard(world)
    world.advisor.failing = True
    body = _ask(world, "Fed rate decision")
    assert body["cards"][0]["id"] == FED_EVENT
