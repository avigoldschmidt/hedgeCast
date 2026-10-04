import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _env(name, default):
    value = os.environ.get(name, "").strip()
    return value or default


def db_path():
    return Path(_env("HEDGECAST_V2_DB", str(ROOT / "backend" / "hedgecast.db")))


def hedge_mode():
    return _env("HEDGE_MODE", "paper").lower()


def use_fakes():
    return _env("HEDGECAST_FAKES", "0") == "1"


def kalshi_data_url():
    return _env("KALSHI_DATA_URL", "https://external-api.kalshi.com/trade-api/v2").rstrip("/")


def worker_enabled():
    return _env("HEDGECAST_WORKER", "1") == "1"


QUOTE_TTL_SECONDS = 90
SLIPPAGE_BUFFER = "0.02"
PLATFORM_FEE = "0.10"
EXCHANGE_FEE_RATE = "0.07"
MAX_CONTRACT_PRICE = "0.97"
MAX_PAYOUT_DOLLARS = 25000
WORKER_INTERVAL_SECONDS = 60
PAYOUT_MAX_ATTEMPTS = 3
