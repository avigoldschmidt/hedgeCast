import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get("HEDGECAST_DB", Path(__file__).resolve().with_name("hedgecast.db")))


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS businesses (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    city TEXT NOT NULL,
    bank_customer_id TEXT,
    bank_account_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hedges (
    id INTEGER PRIMARY KEY,
    business_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    title TEXT NOT NULL,
    side TEXT NOT NULL,
    contract_count TEXT NOT NULL,
    limit_price TEXT NOT NULL,
    client_order_id TEXT,
    kalshi_order_id TEXT,
    fill_count TEXT,
    status TEXT NOT NULL,
    result TEXT,
    settlement_source TEXT,
    bank_transfer_id TEXT,
    detail TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (business_id) REFERENCES businesses(id)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def init_db():
    with connect() as conn:
        conn.executescript(_SCHEMA)
        _migrate(conn)


def _columns(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _migrate(conn):
    business_cols = _columns(conn, "businesses")
    if "nessie_customer_id" in business_cols:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript(
            """
            CREATE TABLE businesses_next (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                city TEXT NOT NULL,
                bank_customer_id TEXT,
                bank_account_id TEXT,
                created_at TEXT NOT NULL
            );
            INSERT INTO businesses_next (
                id, name, description, city, bank_customer_id, bank_account_id, created_at
            )
            SELECT id, name, description, city, nessie_customer_id, nessie_account_id, created_at
            FROM businesses;
            DROP TABLE businesses;
            ALTER TABLE businesses_next RENAME TO businesses;
            """
        )
        conn.execute("PRAGMA foreign_keys = ON")
    hedge_cols = _columns(conn, "hedges")
    if "nessie_transfer_id" in hedge_cols:
        conn.execute("ALTER TABLE hedges RENAME COLUMN nessie_transfer_id TO bank_transfer_id")
    conn.execute(
        """
        UPDATE hedges
        SET detail = REPLACE(detail, 'Demo settlement. This market is still open on Kalshi. ', '')
        WHERE detail LIKE 'Demo settlement. This market is still open on Kalshi. %'
        """
    )


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_setting(key):
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(key, value):
    with connect() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def create_business(name, description, city):
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO businesses (name, description, city, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (name, description, city, _now()),
        )
        return cursor.lastrowid


def list_businesses():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM businesses ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


def set_business_bank(business_id, bank_customer_id, bank_account_id):
    with connect() as conn:
        conn.execute(
            """
            UPDATE businesses
            SET bank_customer_id = ?, bank_account_id = ?
            WHERE id = ?
            """,
            (bank_customer_id, bank_account_id, business_id),
        )


def set_business_account(business_id, bank_account_id):
    with connect() as conn:
        conn.execute(
            "UPDATE businesses SET bank_account_id = ? WHERE id = ?",
            (bank_account_id, business_id),
        )


def get_business(business_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()
    return dict(row) if row else None


def create_hedge(
    business_id,
    ticker,
    title,
    contract_count,
    limit_price,
    client_order_id,
    kalshi_order_id,
    fill_count,
    status,
    detail="",
):
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO hedges (
                business_id, ticker, title, side, contract_count, limit_price,
                client_order_id, kalshi_order_id, fill_count, status, detail, created_at
            ) VALUES (?, ?, ?, 'yes', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                business_id,
                ticker,
                title,
                contract_count,
                limit_price,
                client_order_id,
                kalshi_order_id,
                fill_count,
                status,
                detail,
                _now(),
            ),
        )
        return cursor.lastrowid


def list_hedges(business_id):
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM hedges WHERE business_id = ? ORDER BY id DESC",
            (business_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_hedge(hedge_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM hedges WHERE id = ?", (hedge_id,)).fetchone()
    return dict(row) if row else None


def settle_hedge(hedge_id, status, result, settlement_source, detail, bank_transfer_id=None):
    with connect() as conn:
        conn.execute(
            """
            UPDATE hedges
            SET status = ?, result = ?, settlement_source = ?, detail = ?, bank_transfer_id = ?
            WHERE id = ?
            """,
            (status, result, settlement_source, detail, bank_transfer_id, hedge_id),
        )
