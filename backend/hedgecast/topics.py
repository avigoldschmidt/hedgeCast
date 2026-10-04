"""The curated topics a business can watch, and how each one finds its open Kalshi markets.

Finding markets is deterministic: a topic only ever shows markets its own rules match. The advisor
picks among these candidates and writes the words; it never adds a market.
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

_INDUSTRY_HINTS = [
    ("Food truck", r"food truck|truck"),
    ("Café or coffee shop", r"caf[eé]|coffee|espresso|bakery|tea house"),
    ("Restaurant or bar", r"restaurant|\bbar\b|pub|diner|brewery|kitchen|bistro|pizz"),
    ("Farm or market stand", r"farm|orchard|market stand|crops?|vineyard|nursery"),
    ("Outdoor events", r"event|wedding|festival|concert|venue|catering"),
    ("Landscaping or construction", r"landscap|construct|roof|contractor|builder|paving"),
    ("Recreation or rentals", r"rental|kayak|bike|golf|recreation|tours?\b|surf|ski"),
    ("Retail shop", r"shop|store|boutique|retail"),
]

MAX_OPTIONS = 6
GROUPS_PER_TOPIC = 4
LIKELY = 0.75
CLOSING_SOON = timedelta(days=1)


def get(topic_id):
    return _BY_ID.get(topic_id)


def valid_ids(ids):
    """Known topic ids from `ids`, in catalog order, without duplicates."""
    wanted = set(ids or [])
    return [topic.id for topic in TOPICS if topic.id in wanted]


def guess_industry(description):
    text = (description or "").lower()
    for industry, pattern in _INDUSTRY_HINTS:
        if re.search(pattern, text):
            return industry
    return "Other"


def default_profile(description):
    industry = guess_industry(description)
    topic_ids, bad_day = INDUSTRIES[industry]
    return {"industry": industry, "topics": list(topic_ids), "bad_day_dollars": bad_day}


def topic_for_event(event):
    if event.get("category") == weather.CATEGORY:
        return "weather"
    for topic in TOPICS:
        if topic.id != "weather" and _matches(topic, event):
            return topic.id
    return OTHER.id


# Candidate groups: a set of sibling markets the customer can choose between (days for rain,
# thresholds for gas, outcomes for the Fed). Each group becomes at most one forecast card.


def groups_for(topic_id, market_data, place, now, events=None):
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
    return [group for _local, _volume, group in found[:GROUPS_PER_TOPIC]]


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


def search_groups(events, text, now, limit=12):
    """Groups whose event text shares the most words with `text`. Used by the ask bar."""
    words = {w for w in re.findall(r"[a-z0-9$.]+", text.lower()) if len(w) > 2 and w not in _STOPWORDS}
    if not words:
        return []
    scored = []
    for event in events:
        topic_id = topic_for_event(event)
        if topic_id == "weather":
            continue  # weather comes from the business's own station instead, see weather_groups
        haystack = " ".join(
            [event.get("title") or "", event.get("sub_title") or "", event.get("category") or ""]
            + [catalog.market_label(m) + " " + (m.get("yes_sub_title") or "") for m in event.get("markets") or []]
        ).lower()
        score = sum(1 for word in words if re.search(rf"\b{re.escape(word)}", haystack))
        if not score:
            continue
        group = event_group(event, topic_id, now)
        if group:
            scored.append((score, group["volume"], group))
    scored.sort(key=lambda item: (-item[0], -item[1]))
    return [group for _score, _volume, group in scored[:limit]]


def mentions_weather(text):
    return bool(re.search(r"\b(rain|rainy|storm|snow|heat|hot|cold|freeze|frost|weather|temperature)\b", text.lower()))


def warnings_for(group, option, side, now):
    """Plain facts a buyer should see before protecting. Written by code, never by the advisor."""
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


_STOPWORDS = {
    "the", "and", "for", "our", "my", "will", "that", "this", "with", "from", "what", "when", "into", "about",
    "would", "could", "might", "if", "they", "them", "their", "your", "you", "are", "was", "has", "have", "had",
    "pulls", "away", "lose", "money", "cost", "costs", "business", "worried", "happens", "get", "gets", "too",
    "much", "more", "less", "than", "over", "under", "any", "all", "not", "but", "just", "next", "week", "month",
}
