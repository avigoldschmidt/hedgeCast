"""Maps a business location and a peril to the Kalshi markets that can back it."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

RAIN_SERIES = "KXRAIN"
CUTOFF = timedelta(minutes=10)

PERILS = {
    "rain": {"name": "Rain", "description": "Pays when measurable rain falls on a covered day."},
    "heat": {"name": "Heat", "description": "Pays when the daily high climbs past a threshold."},
    "cold": {"name": "Cold", "description": "Pays when the overnight low drops below a threshold."},
}

_MONTHS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def event_date(event_ticker):
    """KXHIGHNY-26OCT04 -> 2026-10-04."""
    stamp = event_ticker.rsplit("-", 1)[-1]
    return date(2000 + int(stamp[:2]), _MONTHS[stamp[2:5]], int(stamp[5:7]))


def date_stamp(day):
    return day.strftime("%y%b%d").upper()


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def series_for(peril, station):
    if peril == "rain":
        return RAIN_SERIES
    return station.high_series if peril == "heat" else station.low_series


def trigger_label(peril, market):
    if peril == "rain":
        return "Any measurable rain"
    subtitle = market.get("yes_sub_title") or ""
    return f"High of {subtitle}" if peril == "heat" else f"Low of {subtitle}"


def matches(peril, station, market):
    if peril == "rain":
        return market.get("ticker", "").endswith(f"-{station.code}")
    wanted = "greater" if peril == "heat" else "less"
    return market.get("strike_type") == wanted


def triggers(market_data, peril, station, now=None):
    """Open, bookable markets for this peril at this station: [{ticker, date, label, close_time, market}]."""
    now = now or datetime.now(timezone.utc)
    series = series_for(peril, station)
    if not series:
        return []
    found = []
    for market in market_data.series_markets(series):
        if not matches(peril, station, market) or market.get("status") not in (None, "active", "open"):
            continue
        close_time = parse_time(market["close_time"])
        if close_time - CUTOFF <= now:
            continue
        found.append(
            {
                "ticker": market["ticker"],
                "date": event_date(market["event_ticker"]).isoformat(),
                "label": trigger_label(peril, market),
                "close_time": close_time.isoformat(),
                "market": market,
            }
        )
    found.sort(key=lambda item: (item["date"], item["ticker"]))
    return found


def market_probability(market):
    ask = Decimal(market.get("yes_ask_dollars") or "0")
    bid = Decimal(market.get("yes_bid_dollars") or "0")
    if ask > 0 and bid > 0:
        return float((ask + bid) / 2)
    if ask > 0:
        return float(ask)
    return None
