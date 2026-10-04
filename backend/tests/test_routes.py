from support import onboard


def test_reference_data(world):
    assert any(city["id"] == "ann-arbor-mi" for city in world.client.get("/api/cities").json())
    topic_ids = [topic["id"] for topic in world.client.get("/api/topics").json()]
    assert topic_ids == ["weather", "fuel", "rates", "prices", "tariffs", "sports", "jobs"]


def test_sessions_switch_between_businesses(world):
    first = onboard(world)
    second = onboard(world, "chicago-il", link=False)
    names = [item["id"] for item in world.client.get("/api/businesses").json()]
    assert names == [second["id"], first["id"]]
    assert world.client.get("/api/me").json()["id"] == second["id"]

    assert world.client.post("/api/session", json={"business_id": first["id"]}).status_code == 200
    assert world.client.get("/api/me").json()["id"] == first["id"]

    world.client.delete("/api/session")
    assert world.client.get("/api/me").status_code == 401


def test_unknown_business_and_city(world):
    assert world.client.post("/api/session", json={"business_id": 999}).status_code == 404
    bad = world.client.post("/api/businesses", json={"name": "X", "description": "A shop", "city_id": "atlantis"})
    assert bad.status_code == 400


def test_linking_twice_keeps_the_same_account(world):
    business = onboard(world)
    again = world.client.post("/api/me/bank").json()
    assert again["bank"]["account_mask"] == business["bank"]["account_mask"]
    assert again["bank"]["balance_cents"] == 100000


def test_bank_outage_shows_on_the_business_not_as_a_crash(world):
    onboard(world)
    world.bank.fail("balance")
    body = world.client.get("/api/me").json()
    assert body["bank"]["linked"] is True
    assert body["bank"]["error"]
