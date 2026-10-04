"""Gemini tailors the app to each business: its profile, which candidate markets matter, and the words on each plan.

It never produces a number anyone pays or gets paid on, and anything it returns is checked against the
candidates code gave it. Warnings are written by code, not here.
"""

import json

import requests

from . import topics

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
PER_TOPIC = 2


class AdvisorError(Exception):
    pass


class GeminiAdvisor:
    name = "Gemini"

    def __init__(self, api_key, model, timeout=30):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def profile(self, description, city):
        industries = list(topics.INDUSTRIES)
        topic_ids = [topic.id for topic in topics.TOPICS]
        prompt = f"""You set up protection on HedgeCast, which pays small businesses automatically when real, forecastable events happen.
From the owner's description, choose:
- industry: exactly one of {json.dumps(industries)}
- topics: the 2 to 4 topics most likely to cost this business money, from:
{_topic_lines()}
- bad_day_dollars: whole dollars this business would plausibly lose on one bad day or event, between 100 and 25000.

Description: {description}
Location: {city or "not given"}"""
        schema = {
            "type": "object",
            "properties": {
                "industry": {"type": "string", "enum": industries},
                "topics": {"type": "array", "items": {"type": "string", "enum": topic_ids}},
                "bad_day_dollars": {"type": "integer"},
            },
            "required": ["industry", "topics", "bad_day_dollars"],
        }
        return self._generate(prompt, schema)

    def curate(self, business, groups):
        prompt = f"""You write the personal forecast for a small business on HedgeCast. Each candidate is a group of real, open Kalshi markets.
Pick the groups that would actually cost this business money: at most {PER_TOPIC} per topic, and skip groups that don't fit.
{_PLAN_RULES}

Business: {json.dumps(business)}
Candidates: {json.dumps(_compact(groups))}"""
        return self._generate(prompt, {"type": "object", "properties": {"plans": _PLANS_SCHEMA}, "required": ["plans"]}).get("plans")

    def ask(self, business, text, groups):
        prompt = f"""A small business owner on HedgeCast described something that could cost them money. Each candidate is a group of real, open Kalshi markets.
Pick up to 3 groups that genuinely cover this worry. If none do, return no plans.
{_PLAN_RULES}
message: one short sentence to the owner saying what you found, or plainly that no market covers it.

Business: {json.dumps(business)}
The owner asked: {text}
Candidates: {json.dumps(_compact(groups))}"""
        schema = {
            "type": "object",
            "properties": {"plans": _PLANS_SCHEMA, "message": {"type": "string"}},
            "required": ["plans", "message"],
        }
        return self._generate(prompt, schema)

    def _generate(self, prompt, schema):
        thinking = {"thinkingBudget": 0} if self.model.startswith("gemini-2") else {"thinkingLevel": "low"}
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema, "thinkingConfig": thinking},
        }
        try:
            response = requests.post(
                URL.format(model=self.model), headers={"x-goog-api-key": self.api_key}, json=body, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise AdvisorError(f"Couldn't reach Gemini: {exc}") from exc
        if not response.ok:
            raise AdvisorError(f"Gemini error {response.status_code}: {response.text[:200]}")
        try:
            parts = response.json()["candidates"][0]["content"]["parts"]
            return json.loads("".join(part.get("text", "") for part in parts if not part.get("thought")))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AdvisorError(f"Gemini returned something unreadable: {exc}") from exc


_PLAN_RULES = """For each pick:
- group: the candidate id
- ticker: one option ticker from that group, the trigger that best matches this business's real risk
- side: "yes" if the business loses money when that option happens, "no" if it loses money when it doesn't
- title: at most 8 plain words saying what happens and when, e.g. "Rain Saturday in Brooklyn" or "Gas above $3.50 by Oct 31"
- why: one sentence, at most 20 words, to the owner, on why this hits their business
- catch: one sentence, at most 25 words, on what it actually settles on and how that could differ from their real loss
Never state chances, prices, premiums, or payouts. Only use ids and tickers from the candidates."""

_PLANS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "group": {"type": "string"},
            "ticker": {"type": "string"},
            "side": {"type": "string", "enum": ["yes", "no"]},
            "title": {"type": "string"},
            "why": {"type": "string"},
            "catch": {"type": "string"},
        },
        "required": ["group", "ticker", "side", "title", "why", "catch"],
    },
}


def _topic_lines():
    return "\n".join(f"  {topic.id}: {topic.name} ({topic.blurb})" for topic in topics.TOPICS)


def _compact(groups):
    return [
        {
            "id": group["id"],
            "topic": group["topic"],
            "title": group["title"],
            "settles_on": group["settles_on"],
            "options": [
                {
                    "ticker": option["ticker"],
                    "label": option["label"],
                    "chance_yes": None if option["chance"] is None else round(option["chance"], 2),
                    "closes": option["close_time"][:10],
                }
                for option in group["options"]
            ],
        }
        for group in groups
    ]


# Checking what comes back


def clean_profile(raw, description):
    fallback = topics.default_profile(description)
    if not isinstance(raw, dict):
        return fallback
    industry = raw.get("industry") if raw.get("industry") in topics.INDUSTRIES else fallback["industry"]
    chosen = topics.valid_ids(raw.get("topics") if isinstance(raw.get("topics"), list) else [])[:4]
    bad_day = raw.get("bad_day_dollars")
    if not isinstance(bad_day, int) or not 100 <= bad_day <= 25000:
        bad_day = topics.INDUSTRIES[industry][1]
    return {"industry": industry, "topics": chosen or list(topics.INDUSTRIES[industry][0]), "bad_day_dollars": bad_day}


def clean_plans(raw, groups, per_topic=PER_TOPIC):
    """Keeps plans that point at a candidate group and one of its own tickers. Everything else is dropped."""
    by_id = {group["id"]: group for group in groups}
    plans, seen, counts = [], set(), {}
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        group = by_id.get(item.get("group"))
        if group is None or group["id"] in seen:
            continue
        if item.get("ticker") not in {option["ticker"] for option in group["options"]}:
            continue
        if counts.get(group["topic"], 0) >= per_topic:
            continue
        seen.add(group["id"])
        counts[group["topic"]] = counts.get(group["topic"], 0) + 1
        plans.append(
            {
                "group": group["id"],
                "ticker": item["ticker"],
                "side": item.get("side") if item.get("side") in ("yes", "no") else "yes",
                "title": _text(item.get("title"), 80) or group["title"],
                "why": _text(item.get("why"), 200) or topics.fallback_why(group["topic"]),
                "catch": _text(item.get("catch"), 220) or group["settles_on"],
            }
        )
    return plans


def fallback_plans(groups, per_topic=PER_TOPIC):
    """Plain plans written by code, used when Gemini is off or fails."""
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
                "why": topics.fallback_why(group["topic"]),
                "catch": group["settles_on"],
            }
        )
    return plans


def _text(value, limit):
    if not isinstance(value, str):
        return ""
    value = " ".join(value.split())
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"
