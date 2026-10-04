import sqlite3

import pytest

from hedgecast.db import Database

POLICY = {
    "quote_id": "q-1",
    "category": "Economics",
    "title": "Fed decision in December",
    "terms": "Pays if the Fed holds.",
    "payout_each_cents": 100000,
    "max_payout_cents": 100000,
    "premium_cents": 40000,
}
LEG = {
    "ticker": "KXFED-26DEC-H0",
    "side": "no",
    "label": "Will the Fed hold rates in December?",
    "contracts": 1000,
    "cost_ceiling_cents": 35000,
    "close_time": "2026-10-05T05:00:00+00:00",
}


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    business_id = database.create_business("Peach", "Cafe", "new-york-ny")
    database.save_quote("q-1", business_id, {"legs": []}, 40000, "2030-01-01T00:00:00+00:00")
    database.business_id = business_id
    return database


def _policy(db):
    return db.create_policy(dict(POLICY, business_id=db.business_id), [LEG], "Created.")


def test_policy_starts_pending_with_legs_and_event(db):
    policy_id = _policy(db)
    assert db.get_policy(policy_id)["status"] == "PENDING"
    assert [leg["ticker"] for leg in db.legs(policy_id)] == [LEG["ticker"]]
    assert [event["kind"] for event in db.events(policy_id)] == ["created"]


def test_quote_can_only_bind_once(db):
    _policy(db)
    with pytest.raises(sqlite3.IntegrityError):
        _policy(db)


def test_transition_is_compare_and_set(db):
    policy_id = _policy(db)
    assert db.transition(policy_id, ["PENDING"], "ACTIVE", "active", "Active.")
    assert not db.transition(policy_id, ["PENDING"], "REFUNDED", "refunded", "Refunded.")
    assert db.get_policy(policy_id)["status"] == "ACTIVE"
    assert [event["kind"] for event in db.events(policy_id)] == ["created", "active"]


def test_transition_sets_extra_fields(db):
    policy_id = _policy(db)
    db.transition(policy_id, ["PENDING"], "PAID", "paid", "Paid.", paid_cents=100000)
    assert db.get_policy(policy_id)["paid_cents"] == 100000


def test_claim_movement_is_idempotent(db):
    policy_id = _policy(db)
    first = db.claim_movement(policy_id, "payout", 100000, f"payout:{policy_id}")
    db.finish_movement(f"payout:{policy_id}", "done", "t-1")
    second = db.claim_movement(policy_id, "payout", 100000, f"payout:{policy_id}")
    assert first["id"] == second["id"]
    assert second["status"] == "done"
    assert len(db.movements(policy_id)) == 1


def test_delete_policy_cascades(db):
    policy_id = _policy(db)
    db.claim_movement(policy_id, "premium", 40000, f"premium:{policy_id}")
    db.delete_policy(policy_id)
    assert db.get_policy(policy_id) is None
    assert db.legs(policy_id) == []
    assert db.movements(policy_id) == []


def test_settings_round_trip(db):
    db.set_setting("reserve_account_id", "abc")
    db.set_setting("reserve_account_id", "def")
    assert db.get_setting("reserve_account_id") == "def"


def test_old_schema_is_rebuilt_but_settings_survive(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);"
        "INSERT INTO settings VALUES ('reserve_account_id', 'r-1');"
        "CREATE TABLE policies (id INTEGER PRIMARY KEY, peril TEXT);"
    )
    conn.close()
    db = Database(path)
    assert db.get_setting("reserve_account_id") == "r-1"
    assert "category" in {row["name"] for row in db.all("PRAGMA table_info(policies)")}
