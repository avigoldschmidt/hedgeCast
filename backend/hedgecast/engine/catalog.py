"""Turns raw Kalshi events and markets into what the app shows: searchable event cards and bookable markets."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

CUTOFF = timedelta(minutes=10)
OPEN = (None, "active", "open")


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def market_probability(market, side="yes"):
    """Odds that `side` wins from the market's top-of-book quotes."""
    ask = Decimal(market.get("yes_ask_dollars") or "0")
    bid = Decimal(market.get("yes_bid_dollars") or "0")
    if ask > 0 and bid > 0:
        yes = (ask + bid) / 2
    elif ask > 0:
        yes = ask
    else:
        return None
    return float(yes if side == "yes" else 1 - yes)


def is_bookable(market, now):
    return market.get("status") in OPEN and parse_time(market["close_time"]) - CUTOFF > now


def market_label(market):
    return market.get("title") or market.get("yes_sub_title") or market["ticker"]


def _volume(market):
    return float(market.get("volume_fp") or market.get("volume") or 0)


def _option(market):
    return {
        "ticker": market["ticker"],
        "title": market_label(market),
        "outcome": market.get("yes_sub_title") or "",
        "yes_probability": market_probability(market),
        "close_time": parse_time(market["close_time"]).isoformat(),
    }


def _matches(event, words):
    text = " ".join(
        [event.get("title") or "", event.get("sub_title") or "", event.get("category") or ""]
        + [market_label(m) + " " + (m.get("yes_sub_title") or "") for m in event.get("markets") or []]
    ).lower()
    return all(word in text for word in words)


def search(events, query="", category=None, now=None, limit=40):
    """Event cards with at least one bookable market, most traded first, plus every category on offer."""
    now = now or datetime.now(timezone.utc)
    words = query.lower().split()
    categories = {}
    cards = []
    for event in events:
        markets = [m for m in event.get("markets") or [] if is_bookable(m, now)]
        if not markets:
            continue
        name = event.get("category") or "Other"
        categories[name] = categories.get(name, 0) + 1
        if category and name != category:
            continue
        if words and not _matches(event, words):
            continue
        markets.sort(key=_volume, reverse=True)
        cards.append(
            (
                sum(_volume(m) for m in markets),
                {
                    "event_ticker": event["event_ticker"],
                    "title": event.get("title") or event["event_ticker"],
                    "sub_title": event.get("sub_title") or "",
                    "category": name,
                    "market_count": len(markets),
                    "closes_at": min(parse_time(m["close_time"]) for m in markets).isoformat(),
                    "markets": [_option(m) for m in markets[:3]],
                },
            )
        )
    cards.sort(key=lambda item: item[0], reverse=True)
    ordered = sorted(categories, key=lambda name: -categories[name])
    return ordered, [card for _volume_total, card in cards[:limit]]


def event_detail(event, now=None):
    now = now or datetime.now(timezone.utc)
    markets = [m for m in event.get("markets") or [] if is_bookable(m, now)]
    return {
        "event_ticker": event["event_ticker"],
        "title": event.get("title") or event["event_ticker"],
        "sub_title": event.get("sub_title") or "",
        "category": event.get("category") or "Other",
        "markets": [_option(m) for m in markets],
    }
