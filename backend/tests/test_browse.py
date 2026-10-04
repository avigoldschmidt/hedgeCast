from support import onboard


def test_perils_and_weather_options(world):
    onboard(world)
    perils = world.client.get("/api/perils").json()
    assert [item["id"] for item in perils] == ["rain", "heat", "cold"]

    rain = world.client.get("/api/weather?peril=rain")
    assert rain.status_code == 200
    body = rain.json()
    assert body["peril"]["id"] == "rain"
    assert body["station"]["code"]
    assert body["days"]


def test_browse_by_topic(world):
    onboard(world)
    assert world.client.get("/api/browse?topic=weather").status_code == 400
    assert world.client.get("/api/browse?topic=other").status_code == 400

    rates = world.client.get("/api/browse?topic=rates")
    assert rates.status_code == 200
    body = rates.json()
    assert body["topic"] == "rates"
    assert body["groups"]
    assert body["groups"][0]["options"]
