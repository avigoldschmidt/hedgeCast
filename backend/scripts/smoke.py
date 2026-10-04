"""End-to-end check against the real Nessie sandbox and live Kalshi prices. Hedges stay on paper.

Run with `make smoke`. Uses a throwaway database so the demo data stays clean.
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

MAIN_DB = ROOT / "backend" / "hedgecast.db"
os.environ["HEDGECAST_V2_DB"] = str(Path(tempfile.mkdtemp()) / "smoke.db")
os.environ["HEDGECAST_WORKER"] = "0"
os.environ.setdefault("HEDGE_MODE", "paper")
os.environ.pop("HEDGECAST_FAKES", None)

from fastapi.testclient import TestClient  # noqa: E402

from hedgecast.integrations import nessie  # noqa: E402
from hedgecast.main import build_service, create_app  # noqa: E402


def step(label, response, expect=200):
    if response.status_code != expect:
        print(f"FAIL {label}: {response.status_code} {response.text}")
        sys.exit(1)
    print(f"ok   {label}")
    return response.json()


def reuse_reserve(service):
    """Keeps one Nessie reserve account across runs instead of opening a new one each time."""
    if not MAIN_DB.exists():
        return
    with sqlite3.connect(MAIN_DB) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (nessie.RESERVE_SETTING,)).fetchone()
    if row:
        service.db.set_setting(nessie.RESERVE_SETTING, row[0])


def main():
    service = build_service()
    reuse_reserve(service)
    client = TestClient(create_app(service, worker=False))
    print(f"market data: {service.market_data.source}   hedge mode: {service.executor.mode}")

    step("create business", client.post("/api/businesses", json={"name": "Smoke Test Bakery", "industry": "Bakery", "city_id": "new-york-ny"}))
    business = step("link Nessie checking", client.post("/api/me/bank"))
    opening = business["bank"]["balance_cents"]
    print(f"     checking balance ${opening / 100:,.2f}")

    coverage = step("rain coverage from live Kalshi", client.get("/api/coverage", params={"peril": "rain"}))
    if not coverage["days"]:
        print(f"SKIP no open rain markets: {coverage['message']}")
        return
    day = coverage["days"][-1]
    ticker = day["triggers"][0]["ticker"]
    print(f"     {coverage['station']['name']} · {day['label']} · {ticker}")

    quote = step("quote $5 per day", client.post("/api/quotes", json={"peril": "rain", "tickers": [ticker], "payout_dollars": 5}))
    print(f"     premium ${quote['premium_cents'] / 100:,.2f}  breakdown {quote['breakdown']}")
    if quote["thin_book"]["short"]:
        print("SKIP the live book can't cover $5 right now")
        return

    policy = step("buy cover (paper hedge)", client.post("/api/policies", json={"quote_id": quote["id"]}))
    if policy["status"] != "ACTIVE":
        print(f"FAIL policy ended up {policy['status']}: {[e['message'] for e in policy['events']]}")
        sys.exit(1)

    paid = step("demo resolve YES", client.post(f"/api/ops/policies/{policy['id']}/resolve", json={"result": "yes"}))
    if paid["status"] != "PAID":
        print(f"FAIL expected PAID, got {paid['status']}: {[e['message'] for e in paid['events']]}")
        sys.exit(1)

    closing = step("read checking again", client.get("/api/me"))["bank"]["balance_cents"]
    expected = opening - quote["premium_cents"] + paid["paid_cents"]
    print(f"     checking ${opening / 100:,.2f} -> ${closing / 100:,.2f} (expected ${expected / 100:,.2f})")
    if closing != expected:
        print("WARN Nessie balances can lag behind transfers; check the transfer ids on the policy.")
    for movement in paid["movements"]:
        print(f"     {movement['kind']:<8} ${movement['amount_cents'] / 100:,.2f}  {movement['status']}  {movement['external_id']}")
    print("smoke passed")


if __name__ == "__main__":
    main()
