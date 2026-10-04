import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS businesses (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    industry TEXT NOT NULL,
    topics TEXT NOT NULL DEFAULT '[]',
    bad_day_dollars INTEGER NOT NULL DEFAULT 1000,
    city_id TEXT,
    bank_customer_id TEXT,
    bank_account_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quotes (
    id TEXT PRIMARY KEY,
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    payload TEXT NOT NULL,
    premium_cents INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policies (
    id INTEGER PRIMARY KEY,
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    quote_id TEXT NOT NULL UNIQUE REFERENCES quotes(id),
    topic TEXT NOT NULL,
    title TEXT NOT NULL,
    why TEXT NOT NULL DEFAULT '',
    catch TEXT NOT NULL DEFAULT '',
    terms TEXT NOT NULL,
    payout_each_cents INTEGER NOT NULL,
    max_payout_cents INTEGER NOT NULL,
    premium_cents INTEGER NOT NULL,
    paid_cents INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    payout_attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policy_legs (
    id INTEGER PRIMARY KEY,
    policy_id INTEGER NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    label TEXT NOT NULL,
    contracts INTEGER NOT NULL,
    cost_ceiling_cents INTEGER NOT NULL,
    fill_price TEXT,
    limit_price TEXT,
    cost_cents INTEGER NOT NULL DEFAULT 0,
    fee_cents INTEGER NOT NULL DEFAULT 0,
    simulated INTEGER NOT NULL DEFAULT 1,
    order_id TEXT,
    close_time TEXT NOT NULL,
    result TEXT,
    forced INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS policy_events (
    id INTEGER PRIMARY KEY,
    policy_id INTEGER NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS money_movements (
    id INTEGER PRIMARY KEY,
    policy_id INTEGER NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    status TEXT NOT NULL,
    external_id TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    detail TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_policies_business ON policies(business_id);
CREATE INDEX IF NOT EXISTS idx_policies_status ON policies(status);
CREATE INDEX IF NOT EXISTS idx_legs_policy ON policy_legs(policy_id);
CREATE INDEX IF NOT EXISTS idx_events_policy ON policy_events(policy_id);
"""


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


SCHEMA_VERSION = 4
DATA_TABLES = ("money_movements", "policy_events", "policy_legs", "policies", "quotes", "businesses")


class Database:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            if conn.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                # Hackathon-grade migration: rebuild data tables, keep settings (the Nessie reserve account).
                for table in DATA_TABLES:
                    conn.execute(f"DROP TABLE IF EXISTS {table}")
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def one(self, sql, params=()):
        with self.connect() as conn:
            row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def all(self, sql, params=()):
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def run(self, sql, params=()):
        with self.connect() as conn:
            cursor = conn.execute(sql, params)
            return cursor.lastrowid if cursor.lastrowid else cursor.rowcount

    def get_setting(self, key):
        row = self.one("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else None

    def set_setting(self, key, value):
        self.run(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def create_business(self, name, description, industry, city_id, topics, bad_day_dollars):
        return self.run(
            """
            INSERT INTO businesses (name, description, industry, city_id, topics, bad_day_dollars, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, description, industry, city_id, json.dumps(topics), bad_day_dollars, now_iso()),
        )

    def get_business(self, business_id):
        return _business(self.one("SELECT * FROM businesses WHERE id = ?", (business_id,)))

    def list_businesses(self):
        return [_business(row) for row in self.all("SELECT * FROM businesses ORDER BY id DESC")]

    def set_topics(self, business_id, topics):
        self.run("UPDATE businesses SET topics = ? WHERE id = ?", (json.dumps(topics), business_id))

    def set_city(self, business_id, city_id):
        self.run("UPDATE businesses SET city_id = ? WHERE id = ?", (city_id, business_id))

    def set_bank(self, business_id, customer_id, account_id):
        self.run(
            "UPDATE businesses SET bank_customer_id = ?, bank_account_id = ? WHERE id = ?",
            (customer_id, account_id, business_id),
        )

    def save_quote(self, quote_id, business_id, payload, premium_cents, expires_at):
        self.run(
            "INSERT INTO quotes (id, business_id, payload, premium_cents, expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (quote_id, business_id, json.dumps(payload), premium_cents, expires_at, now_iso()),
        )

    def get_quote(self, quote_id):
        row = self.one("SELECT * FROM quotes WHERE id = ?", (quote_id,))
        if row:
            row["payload"] = json.loads(row["payload"])
        return row

    def create_policy(self, policy, legs, event_message):
        """Inserts a PENDING policy. Raises sqlite3.IntegrityError if the quote was already used."""
        stamp = now_iso()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO policies (
                    business_id, quote_id, topic, title, why, catch, terms,
                    payout_each_cents, max_payout_cents, premium_cents, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
                """,
                (
                    policy["business_id"],
                    policy["quote_id"],
                    policy["topic"],
                    policy["title"],
                    policy.get("why", ""),
                    policy.get("catch", ""),
                    policy["terms"],
                    policy["payout_each_cents"],
                    policy["max_payout_cents"],
                    policy["premium_cents"],
                    stamp,
                    stamp,
                ),
            )
            policy_id = cursor.lastrowid
            for leg in legs:
                conn.execute(
                    """
                    INSERT INTO policy_legs (policy_id, ticker, side, label, contracts, cost_ceiling_cents, close_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        policy_id,
                        leg["ticker"],
                        leg["side"],
                        leg["label"],
                        leg["contracts"],
                        leg["cost_ceiling_cents"],
                        leg["close_time"],
                    ),
                )
            conn.execute(
                "INSERT INTO policy_events (policy_id, kind, message, created_at) VALUES (?, 'created', ?, ?)",
                (policy_id, event_message, stamp),
            )
        return policy_id

    def delete_policy(self, policy_id):
        self.run("DELETE FROM policies WHERE id = ?", (policy_id,))

    def get_policy(self, policy_id):
        return self.one("SELECT * FROM policies WHERE id = ?", (policy_id,))

    def list_policies(self, business_id=None, statuses=None):
        sql = "SELECT * FROM policies"
        clauses, params = [], []
        if business_id is not None:
            clauses.append("business_id = ?")
            params.append(business_id)
        if statuses:
            clauses.append(f"status IN ({','.join('?' for _ in statuses)})")
            params.extend(statuses)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        return self.all(sql + " ORDER BY id DESC", params)

    def legs(self, policy_id):
        return self.all("SELECT * FROM policy_legs WHERE policy_id = ? ORDER BY close_time, id", (policy_id,))

    def update_leg(self, leg_id, **fields):
        names = ", ".join(f"{name} = ?" for name in fields)
        self.run(f"UPDATE policy_legs SET {names} WHERE id = ?", (*fields.values(), leg_id))

    def events(self, policy_id):
        return self.all("SELECT * FROM policy_events WHERE policy_id = ? ORDER BY id", (policy_id,))

    def add_event(self, policy_id, kind, message):
        self.run(
            "INSERT INTO policy_events (policy_id, kind, message, created_at) VALUES (?, ?, ?, ?)",
            (policy_id, kind, message, now_iso()),
        )

    def transition(self, policy_id, from_statuses, to_status, kind, message, **fields):
        """Compare-and-set a policy's status. Returns False if another writer moved it first."""
        sets = ["status = ?", "updated_at = ?"] + [f"{name} = ?" for name in fields]
        params = [to_status, now_iso(), *fields.values(), policy_id, *from_statuses]
        stamp = now_iso()
        with self.connect() as conn:
            cursor = conn.execute(
                f"UPDATE policies SET {', '.join(sets)} WHERE id = ? AND status IN ({','.join('?' for _ in from_statuses)})",
                params,
            )
            if cursor.rowcount != 1:
                return False
            conn.execute(
                "INSERT INTO policy_events (policy_id, kind, message, created_at) VALUES (?, ?, ?, ?)",
                (policy_id, kind, message, stamp),
            )
        return True

    def update_policy(self, policy_id, **fields):
        names = ", ".join(f"{name} = ?" for name in fields)
        self.run(f"UPDATE policies SET {names}, updated_at = ? WHERE id = ?", (*fields.values(), now_iso(), policy_id))

    def movements(self, policy_id):
        return self.all("SELECT * FROM money_movements WHERE policy_id = ? ORDER BY id", (policy_id,))

    def get_movement(self, key):
        return self.one("SELECT * FROM money_movements WHERE idempotency_key = ?", (key,))

    def claim_movement(self, policy_id, kind, amount_cents, key):
        """Returns the movement row for this key, creating it as pending if it does not exist."""
        stamp = now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO money_movements
                    (policy_id, kind, amount_cents, status, idempotency_key, created_at, updated_at)
                VALUES (?, ?, ?, 'pending', ?, ?, ?)
                """,
                (policy_id, kind, amount_cents, key, stamp, stamp),
            )
            row = conn.execute("SELECT * FROM money_movements WHERE idempotency_key = ?", (key,)).fetchone()
        return dict(row)

    def finish_movement(self, key, status, external_id=None, detail=None):
        self.run(
            "UPDATE money_movements SET status = ?, external_id = ?, detail = ?, updated_at = ? WHERE idempotency_key = ?",
            (status, external_id, detail, now_iso(), key),
        )

    def status_counts(self):
        rows = self.all("SELECT status, COUNT(*) AS n FROM policies GROUP BY status")
        return {row["status"]: row["n"] for row in rows}


def _business(row):
    if row:
        row["topics"] = json.loads(row["topics"])
    return row
