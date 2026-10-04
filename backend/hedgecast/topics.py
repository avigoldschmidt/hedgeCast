"""The curated topics a business can watch, and how each one finds its open Kalshi markets.

Finding markets is deterministic: a topic only ever shows markets its own rules match.
"""

import re
from collections import namedtuple
from datetime import date, timedelta

from . import weather
from .engine import catalog

Topic = namedtuple("Topic", "id name blurb series categories pattern")

TOPICS = [
    Topic("weather", "Weather", "Rain, heat, or a cold snap at your nearest official station.", (), (), None),
    Topic(
        "fuel",
        "Fuel and gas",
        "What you pay at the pump and for deliveries.",
        ("KXAAAGAS", "KXGAS", "KXOIL", "KXWTI"),
        (),
        r"\b(gas prices?|gasoline|diesel|crude|oil prices?)\b",
    ),
    Topic(
        "rates",
        "Interest rates",
        "What your loans and credit lines cost.",
        ("KXFED", "KXFEDDECISION", "KXRATECUT"),
        (),
        r"\b(fed|fomc|interest rates?|rate cuts?|rate hikes?)\b",
    ),
    Topic(
        "prices",
        "Prices and inflation",
        "What you pay for supplies and ingredients.",
        ("KXCPI", "KXCPIYOY", "KXEGGS"),
        (),
        r"\b(cpi|inflation|egg prices?|food prices?|grocery)\b",
    ),
    Topic(
        "tariffs",
        "Trade and tariffs",
        "Import costs on the goods you buy.",
        ("KXTARIFF",),
        (),
        r"\b(tariffs?|trade deal|trade war)\b",
    ),
    Topic("sports", "Sports and big events", "Game days that fill or empty your place.", (), ("Sports",), None),
    Topic(
        "jobs",
        "Jobs and wages",
        "Hiring, payroll, and minimum wage.",
        ("KXPAYROLLS", "KXU3", "KXJOBLESS"),
        (),
        r"\b(unemployment|jobs report|payrolls?|jobless|minimum wage)\b",
    ),
]
OTHER = Topic("other", "Something else", "Anything else Kalshi lists.", (), (), None)

_BY_ID = {topic.id: topic for topic in TOPICS + [OTHER]}
_PATTERNS = {topic.id: re.compile(topic.pattern) for topic in TOPICS if topic.pattern}

# Industry -> (default topics, rough cost of a bad day in dollars)
INDUSTRIES = {
    "Café or coffee shop": (("weather", "fuel", "prices"), 600),
    "Restaurant or bar": (("weather", "sports", "prices"), 1500),
    "Food truck": (("weather", "fuel", "prices"), 500),
    "Farm or market stand": (("weather", "prices", "tariffs"), 1000),
    "Outdoor events": (("weather", "sports"), 3000),
    "Retail shop": (("prices", "rates", "tariffs"), 1000),
    "Recreation or rentals": (("weather", "fuel"), 800),
    "Landscaping or construction": (("weather", "rates", "tariffs", "fuel"), 2000),
    "Other": (("weather", "rates", "prices"), 1000),
}

MAX_OPTIONS = 6
GROUPS_PER_TOPIC = 4
PER_TOPIC = 4
LIKELY = 0.75
CLOSING_SOON = timedelta(days=1)


def get(topic_id):
    return _BY_ID.get(topic_id)


def valid_ids(ids):
    """Known topic ids from `ids`, in catalog order, without duplicates."""
    wanted = set(ids or [])
    return [topic.id for topic in TOPICS if topic.id in wanted]


def industries():
    return list(INDUSTRIES)


def profile_for(industry):
    if industry not in INDUSTRIES:
        return None
    topic_ids, bad_day = INDUSTRIES[industry]
    return {"industry": industry, "topics": list(topic_ids), "bad_day_dollars": bad_day}


def fallback_plans(groups, per_topic=PER_TOPIC):
    """Plain coverage cards from open market groups, capped per topic."""
    plans, counts = [], {}
    for group in groups:
        if counts.get(group["topic"], 0) >= per_topic:
            continue
        counts[group["topic"]] = counts.get(group["topic"], 0) + 1
        plans.append(
            {
                "group": group["id"],
                "ticker": group["options"][0]["ticker"],
                "side": "yes",
                "title": group["title"],
                "why": fallback_why(group["topic"]),
                "catch": group["settles_on"],
            }
        )
    return plans


def topic_for_event(event):
    if event.get("category") == weather.CATEGORY:
        return "weather"
    for topic in TOPICS:
        if topic.id != "weather" and _matches(topic, event):
            return topic.id
    return OTHER.id


# Candidate groups: a set of sibling markets the customer can choose between (days for rain,
# thresholds for gas, outcomes for the Fed). Each group becomes at most one forecast card.


def groups_for(topic_id, market_data, place, now, events=None, limit=GROUPS_PER_TOPIC):
    if topic_id == "weather":
        return weather_groups(market_data, place, now)
    topic = _BY_ID[topic_id]
    events = market_data.open_events() if events is None else events
    found = []
    for event in events:
        if not _matches(topic, event):
            continue
        group = event_group(event, topic.id, now)
        if group:
            found.append((_local_first(event, place), group["volume"], group))
    found.sort(key=lambda item: (item[0], -item[1]))
    return [group for _local, _volume, group in found[:limit]]


def weather_groups(market_data, place, now):
    if place is None:
        return []
    groups = []
    for peril, info in weather.PERILS.items():
        station, km = weather.nearest_station(place, peril)
        found = weather.triggers(market_data, peril, station, now)[:MAX_OPTIONS]
        if not found:
            continue
        risk = weather.basis_risk(km)
        options = [
            _option(t["ticker"], f"{_day_label(t['date'])} · {t['label']}", catalog.market_probability(t["market"]), t["close_time"])
            for t in found
        ]
        groups.append(
            {
                "id": f"weather-{peril}-{station.code}",
                "topic": "weather",
                "title": f"{info['name']} at {station.name}",
                "settles_on": f"The official reading at {station.name}, {round(km)} km from {place.name}.",
                "warning": weather.BASIS_NOTES[risk] if risk != "low" else None,
                "options": options,
                "volume": 0,
            }
        )
    return groups


def event_group(event, topic_id, now):
    markets = [m for m in event.get("markets") or [] if catalog.is_bookable(m, now)]
    if not markets:
        return None
    markets.sort(key=_volume, reverse=True)
    title = event.get("title") or event["event_ticker"]
    return {
        "id": event["event_ticker"],
        "topic": topic_id,
        "title": title,
        "settles_on": f"Kalshi's official result for “{title}”.",
        "warning": None,
        "options": [
            _option(m["ticker"], m.get("yes_sub_title") or catalog.market_label(m), catalog.market_probability(m), m["close_time"])
            for m in markets[:MAX_OPTIONS]
        ],
        "volume": sum(_volume(m) for m in markets),
    }


def warnings_for(group, option, side, now):
    """Plain facts a buyer should see before protecting."""
    notes = []
    chance = chance_of(option, side)
    if chance is not None and chance >= LIKELY:
        notes.append(f"The market already gives this a {round(chance * 100)}% chance, so cover costs close to what it pays.")
    if catalog.parse_time(option["close_time"]) - now < CLOSING_SOON:
        notes.append("This closes for cover within a day.")
    if group.get("warning"):
        notes.append(group["warning"])
    return notes


def chance_of(option, side):
    yes = option["chance"]
    if yes is None:
        return None
    return yes if side == "yes" else 1 - yes


def fallback_why(topic_id):
    return {
        "weather": "A bad-weather day can keep customers away or stop work.",
        "fuel": "Higher fuel prices raise what you pay to run and restock.",
        "rates": "Rate moves change what your loans and credit lines cost.",
        "prices": "Rising prices squeeze the margin on what you sell.",
        "tariffs": "New tariffs can raise the cost of the goods you buy.",
        "sports": "Big game days change how busy you are.",
        "jobs": "Shifts in jobs and wages change your payroll costs.",
    }.get(topic_id, "This could cost your business money.")


def _matches(topic, event):
    if topic.categories and event.get("category") in topic.categories:
        return True
    series = event.get("series_ticker") or event["event_ticker"].split("-")[0]
    if topic.series and any(series.startswith(prefix) for prefix in topic.series):
        return True
    pattern = _PATTERNS.get(topic.id)
    if pattern is None:
        return False
    return bool(pattern.search(f"{event.get('title') or ''} {event.get('sub_title') or ''}".lower()))


def _local_first(event, place):
    """0 when the event mentions the business's city or state, so local games sort first."""
    if place is None:
        return 1
    text = f"{event.get('title') or ''} {event.get('sub_title') or ''}"
    return 0 if place.name in text else 1


def _option(ticker, label, chance, close_time):
    return {"ticker": ticker, "label": label, "chance": chance, "close_time": catalog.parse_time(close_time).isoformat()}


def _volume(market):
    return float(market.get("volume_fp") or market.get("volume") or 0)


def _day_label(iso_day):
    return date.fromisoformat(iso_day).strftime("%a, %b %-d")
