import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .. import config, topics, weather
from ..advisor import AdvisorError, clean_plans, clean_profile, fallback_plans
from ..api import schemas as s
from ..errors import ServiceError, bad_request, conflict, not_found, unavailable
from ..integrations.market_data import MarketDataError, MarketNotFound
from ..integrations.money import BankError
from . import catalog, pricing
from .executors import HedgeError
from .money import dollars
from .settle import Settlement

OPEN_STATUSES = ("ACTIVE", "AWAITING_RESULT")
QUOTE_GRACE = timedelta(seconds=5)
LIKELY = 0.75
ASK_LIMIT = 3


class Service:
    def __init__(self, db, market_data, bank, executor, clock=None, advisor=None):
        self.db = db
        self.market_data = market_data
        self.bank = bank
        self.executor = executor
        self.advisor = advisor
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.settlement = Settlement(db, market_data, bank, config.PAYOUT_MAX_ATTEMPTS, self.clock)
        self.max_price = Decimal(config.MAX_CONTRACT_PRICE)
        self.worker_enabled = False
        self.last_run_at = None
        self.last_result = None
        self._bind_lock = threading.Lock()
        self._advice = {}

    # Reference data

    def cities(self):
        return [s.City(id=c.id, name=c.name, state=c.state) for c in weather.CITIES]

    def topic_list(self):
        return [s.TopicInfo(id=t.id, name=t.name, blurb=t.blurb) for t in topics.TOPICS]

    # Businesses

    def list_businesses(self):
        return [
            s.BusinessListItem(id=row["id"], name=row["name"], industry=row["industry"], city=_city(row["city_id"]))
            for row in self.db.list_businesses()
        ]

    def create_business(self, body):
        place = None
        if body.city_id:
            place = weather.city(body.city_id)
            if place is None:
                raise bad_request("Choose a city from the list.")
        description = " ".join(body.description.split())
        profile = None
        if self.advisor:
            try:
                raw = self.advisor.profile(description, f"{place.name}, {place.state}" if place else None)
                profile = clean_profile(raw, description)
            except AdvisorError:
                profile = None
        profile = profile or topics.default_profile(description)
        business_id = self.db.create_business(
            body.name.strip(), description, profile["industry"], body.city_id or None, profile["topics"], profile["bad_day_dollars"]
        )
        return self.get_business(business_id)

    def set_topics(self, business_id, body):
        self._business_row(business_id)
        chosen = topics.valid_ids(body.topics)
        if not chosen:
            raise bad_request("Pick at least one thing to watch.")
        self.db.set_topics(business_id, chosen)
        return self.get_business(business_id)

    def get_business(self, business_id):
        return self._business(self._business_row(business_id))

    def link_bank(self, business_id):
        row = self._business_row(business_id)
        if not row["bank_account_id"]:
            place = weather.city(row["city_id"]) if row["city_id"] else None
            try:
                customer_id, account_id = self.bank.link(row["name"], place.name if place else "Main Street")
            except BankError as exc:
                raise unavailable(f"Couldn't connect the bank: {exc}") from exc
            self.db.set_bank(business_id, customer_id, account_id)
        return self.get_business(business_id)

    # Forecast

    def forecast(self, business_id):
        row = self._business_row(business_id)
        place = weather.city(row["city_id"]) if row["city_id"] else None
        groups = self._candidate_groups(row["topics"], place)
        plans, tailored = self._curated(row, groups)
        by_id = {group["id"]: group for group in groups}
        cards = sorted((self._card(by_id[plan["group"]], plan) for plan in plans), key=lambda card: card.closes_at)
        note = None
        if "weather" in row["topics"] and place is None:
            note = "Add your city to see the weather where you are."
        elif not cards:
            note = "Nothing is open for what you watch right now. Try watching something else or ask below."
        return s.Forecast(cards=cards, tailored=tailored, note=note)

    def ask(self, business_id, body):
        row = self._business_row(business_id)
        place = weather.city(row["city_id"]) if row["city_id"] else None
        text = " ".join(body.text.split())
        now = self.clock()
        try:
            groups = topics.search_groups(self.market_data.open_events(), text, now)
            if place and topics.mentions_weather(text):
                groups = topics.weather_groups(self.market_data, place, now) + groups
        except MarketDataError as exc:
            raise unavailable(f"Live market data is unavailable right now. {exc}") from exc

        plans, message = None, ""
        if self.advisor and groups:
            try:
                raw = self.advisor.ask(_advisor_view(row, place), text, groups)
                plans = clean_plans(raw.get("plans"), groups, per_topic=ASK_LIMIT)[:ASK_LIMIT]
                message = raw.get("message") if isinstance(raw.get("message"), str) else ""
            except AdvisorError:
                plans = None
        if plans is None:
            plans = fallback_plans(groups, per_topic=ASK_LIMIT)[:ASK_LIMIT]
        if not message.strip():
            message = (
                "Here's what Kalshi lists for that."
                if plans
                else "No market covers that yet. Try naming the event, like rain, gas prices, or a Fed decision."
            )
        by_id = {group["id"]: group for group in groups}
        return s.AskResult(cards=[self._card(by_id[plan["group"]], plan) for plan in plans], message=" ".join(message.split())[:240])

    def _candidate_groups(self, topic_ids, place):
        now = self.clock()
        events, groups, errors = None, [], []
        for topic_id in topic_ids:
            try:
                if topic_id != "weather" and events is None:
                    events = self.market_data.open_events()
                groups.extend(topics.groups_for(topic_id, self.market_data, place, now, events))
            except MarketDataError as exc:
                errors.append(exc)
        if errors and not groups:
            raise unavailable(f"Live market data is unavailable right now. {errors[0]}")
        return groups

    def _curated(self, row, groups):
        """The advisor's picks for these candidates, cached per business. Falls back to plain plans written by code."""
        if not groups:
            return [], self.advisor is not None
        now = self.clock()
        key = (row["id"], tuple(sorted(group["id"] for group in groups)))
        cached = self._advice.get(key)
        raw = None
        if cached and (now - cached[0]).total_seconds() < config.FORECAST_CACHE_SECONDS:
            raw = cached[1]
        elif self.advisor:
            try:
                raw = self.advisor.curate(_advisor_view(row, weather.city(row["city_id"]) if row["city_id"] else None), groups)
                self._advice[key] = (now, raw)
            except AdvisorError:
                raw = None
        plans = clean_plans(raw, groups) if raw is not None else []
        if not plans:
            return fallback_plans(groups), False
        return plans, True

    def _card(self, group, plan):
        option = next(o for o in group["options"] if o["ticker"] == plan["ticker"])
        return s.PlanCard(
            id=group["id"],
            topic=group["topic"],
            title=plan["title"],
            group_title=group["title"],
            why=plan["why"],
            catch=plan["catch"],
            warnings=topics.warnings_for(group, option, plan["side"], self.clock()),
            side=plan["side"],
            ticker=option["ticker"],
            chance=topics.chance_of(option, plan["side"]),
            closes_at=option["close_time"],
            choices=[s.Choice(ticker=o["ticker"], label=o["label"], chance=o["chance"], closes_at=o["close_time"]) for o in group["options"]],
        )

    # Quotes

    def quote(self, business_id, body):
        if body.payout_dollars > config.MAX_PAYOUT_DOLLARS:
            raise bad_request(f"The most a market can pay is {dollars(config.MAX_PAYOUT_DOLLARS * 100)} for now.")
        if len({leg.ticker for leg in body.legs}) != len(body.legs):
            raise bad_request("Each market can only be picked once.")
        self._business_row(business_id)

        legs, events = [], []
        for request in body.legs:
            market = self._bookable_market(request.ticker)
            events.append(self._event_info(market["event_ticker"]))
            legs.append(self._price(market, request.side, body.payout_dollars))
        legs.sort(key=lambda leg: leg["close_time"])

        premium_cents, breakdown = pricing.premium(legs, config.SLIPPAGE_BUFFER, config.PLATFORM_FEE, self.bank.unit_cents)
        max_fill = min(leg["depth_contracts"] for leg in legs)
        payout_cents = body.payout_dollars * 100
        if body.plan:
            title, topic = body.plan.title.strip(), body.plan.topic
            why, catch = body.plan.why.strip(), body.plan.catch.strip()
        else:
            title, topic, why, catch = _title(events), topics.topic_for_event(events[0]), "", ""

        quote_id = uuid.uuid4().hex
        expires_at = (self.clock() + timedelta(seconds=config.QUOTE_TTL_SECONDS)).isoformat()
        quote = s.Quote(
            id=quote_id,
            expires_at=expires_at,
            title=title,
            topic=topic,
            why=why,
            catch=catch,
            payout_each_cents=payout_cents,
            max_payout_cents=payout_cents * len(legs),
            premium_cents=premium_cents,
            legs=[
                s.QuoteLeg(
                    ticker=leg["ticker"],
                    side=leg["side"],
                    label=leg["label"],
                    close_time=leg["close_time"],
                    contracts=leg["contracts"],
                    avg_price=str(leg["avg_price"]),
                    cost_cents=leg["cost_cents"],
                    depth_contracts=leg["depth_contracts"],
                    implied_probability=leg["implied_probability"],
                )
                for leg in legs
            ],
            breakdown=s.QuoteBreakdown(**breakdown),
            terms=_terms(payout_cents, legs),
            warnings=[
                f"The market already gives “{leg['label']}” a {round(leg['implied_probability'] * 100)}% chance. "
                "Cover costs close to what it pays."
                for leg in legs
                if leg["implied_probability"] >= LIKELY
            ],
            thin_book=s.ThinBook(short=max_fill < body.payout_dollars, max_payout_dollars=max_fill),
        )
        payload = {
            "quote": quote.model_dump(),
            "legs": [
                {key: leg[key] for key in ("ticker", "side", "label", "contracts", "close_time", "cost_ceiling_cents")}
                for leg in legs
            ],
        }
        self.db.save_quote(quote_id, business_id, payload, premium_cents, expires_at)
        return quote

    def _bookable_market(self, ticker):
        try:
            market = self.market_data.market(ticker)
        except MarketNotFound:
            raise bad_request(f"{ticker} isn't a Kalshi market.") from None
        except MarketDataError as exc:
            raise unavailable(f"Live prices are unavailable right now. {exc}") from exc
        if not catalog.is_bookable(market, self.clock()):
            raise bad_request(f"{catalog.market_label(market)} has closed for trading. Pick again.")
        return market

    def _event_info(self, event_ticker):
        try:
            return self.market_data.event(event_ticker)
        except MarketDataError:
            return {"event_ticker": event_ticker, "title": event_ticker, "category": "Other"}

    def _price(self, market, side, contracts):
        try:
            book = self.market_data.orderbook(market["ticker"])
        except MarketDataError as exc:
            raise unavailable(f"Live prices are unavailable right now. {exc}") from exc
        leg = pricing.price_leg(book, side, contracts, self.max_price)
        probability = leg["implied_probability"]
        if probability is None:
            probability = catalog.market_probability(market, side) or 0.0
        leg.update(
            ticker=market["ticker"],
            side=side,
            label=catalog.market_label(market),
            close_time=catalog.parse_time(market["close_time"]).isoformat(),
            implied_probability=probability,
        )
        leg["cost_ceiling_cents"] = pricing.cost_ceiling_cents(leg, config.SLIPPAGE_BUFFER)
        return leg

    # Binding

    def bind(self, business_id, body):
        business = self._business_row(business_id)
        if not business["bank_account_id"]:
            raise conflict("Connect checking before buying cover.")
        row = self.db.get_quote(body.quote_id)
        if row is None or row["business_id"] != business_id:
            raise not_found("That quote doesn't exist. Get a new price.")
        if catalog.parse_time(row["expires_at"]) + QUOTE_GRACE < self.clock():
            raise conflict("That price lock expired. Refresh the quote.")
        quote = s.Quote(**row["payload"]["quote"])
        if quote.thin_book.short and not body.all_or_nothing:
            raise conflict("The market can't cover the full amount. Lower the payout or choose all-or-nothing.")

        with self._bind_lock:
            try:
                policy_id = self.db.create_policy(
                    {
                        "business_id": business_id,
                        "quote_id": quote.id,
                        "topic": quote.topic,
                        "title": quote.title,
                        "why": quote.why,
                        "catch": quote.catch,
                        "terms": quote.terms,
                        "payout_each_cents": quote.payout_each_cents,
                        "max_payout_cents": quote.max_payout_cents,
                        "premium_cents": quote.premium_cents,
                    },
                    row["payload"]["legs"],
                    f"Quote accepted at {dollars(quote.premium_cents)}.",
                )
            except sqlite3.IntegrityError:
                raise conflict("This quote was already used to buy cover.") from None

        if not self._charge_premium(policy_id, business, quote.premium_cents):
            raise ServiceError(402, "Your bank declined the premium. Nothing was charged.")

        legs = self.db.legs(policy_id)
        try:
            fills = self.executor.execute(legs)
        except (HedgeError, MarketDataError) as exc:
            self._unwind(policy_id, business, quote.premium_cents, exc)
            return self.get_policy(business_id, policy_id)

        by_ticker = {fill["ticker"]: fill for fill in fills}
        for leg in legs:
            fill = by_ticker[leg["ticker"]]
            self.db.update_leg(
                leg["id"],
                fill_price=fill["fill_price"],
                cost_cents=fill["cost_cents"],
                order_id=fill["order_id"],
                simulated=1 if self.executor.simulated else 0,
            )
        how = "simulated against the live order book" if self.executor.simulated else "on Kalshi"
        self.db.add_event(policy_id, "hedged", f"Backing contracts bought {how}.")
        self.db.transition(policy_id, ["PENDING"], "ACTIVE", "active", "Cover is active. We'll watch for Kalshi's official result.")
        return self.get_policy(business_id, policy_id)

    def _charge_premium(self, policy_id, business, cents):
        key = f"premium:{policy_id}"
        self.db.claim_movement(policy_id, "premium", cents, key)
        try:
            account_id, transfer_id, moved = self.bank.charge(
                business["bank_customer_id"], business["bank_account_id"], cents, f"HedgeCast premium policy {policy_id}"
            )
        except BankError:
            self.db.delete_policy(policy_id)
            return False
        if account_id != business["bank_account_id"]:
            self.db.set_bank(business["id"], business["bank_customer_id"], account_id)
            business["bank_account_id"] = account_id
        self.db.finish_movement(key, "done", transfer_id)
        self.db.add_event(policy_id, "premium_charged", f"Premium of {dollars(moved)} charged to checking.")
        return True

    def _unwind(self, policy_id, business, cents, error):
        if getattr(error, "orphaned", []):
            self.db.transition(
                policy_id,
                ["PENDING"],
                "NEEDS_REVIEW",
                "hedge_partial",
                f"Only part of the cover could be placed ({error}). The risk desk will finish or unwind it.",
            )
            return
        self.db.add_event(policy_id, "hedge_failed", f"Couldn't place the backing contracts: {error}")
        key = f"refund:{policy_id}"
        self.db.claim_movement(policy_id, "refund", cents, key)
        try:
            _account, transfer_id, moved = self.bank.pay(
                business["bank_customer_id"], business["bank_account_id"], cents, f"HedgeCast refund policy {policy_id}"
            )
        except BankError as exc:
            self.db.finish_movement(key, "failed", detail=str(exc))
            self.db.transition(
                policy_id, ["PENDING"], "NEEDS_REVIEW", "refund_failed", f"Refund failed ({exc}). The risk desk will send it by hand."
            )
            return
        self.db.finish_movement(key, "done", transfer_id)
        self.db.transition(policy_id, ["PENDING"], "REFUNDED", "refunded", f"Premium of {dollars(moved)} refunded to checking.")

    # Policies

    def list_policies(self, business_id):
        self._business_row(business_id)
        return [self._summary(row) for row in self.db.list_policies(business_id=business_id)]

    def get_policy(self, business_id, policy_id):
        row = self.db.get_policy(policy_id)
        if row is None or row["business_id"] != business_id:
            raise not_found("Policy not found.")
        return self._detail(row)

    # Risk desk

    def ops_overview(self):
        reserve, reserve_error = None, None
        try:
            reserve = self.bank.reserve_balance_cents()
        except BankError as exc:
            reserve_error = str(exc)
        businesses = {row["id"]: row["name"] for row in self.db.list_businesses()}
        policies = []
        for row in self.db.list_policies():
            legs = self.db.legs(row["id"])
            policies.append(
                s.OpsPolicy(
                    **self._summary(row, legs).model_dump(),
                    business_name=businesses.get(row["business_id"], ""),
                    simulated=any(leg["simulated"] for leg in legs),
                )
            )
        return s.OpsOverview(
            hedge_mode=self.executor.mode,
            data_source=self.market_data.source,
            advisor=self.advisor.name if self.advisor else "Off · plain wording",
            reserve_balance_cents=reserve,
            reserve_error=reserve_error,
            worker=s.WorkerStatus(enabled=self.worker_enabled, last_run_at=self.last_run_at, last_result=self.last_result),
            counts=self.db.status_counts(),
            policies=policies,
        )

    def demo_resolve(self, policy_id, result):
        policy = self.db.get_policy(policy_id)
        if policy is None:
            raise not_found("Policy not found.")
        if policy["status"] not in OPEN_STATUSES:
            raise conflict("Only active policies can be resolved.")
        self.settlement.demo_resolve(policy_id, result)
        return self._detail(self.db.get_policy(policy_id))

    def run_settlement(self):
        summary = self.settlement.run_cycle()
        self.last_run_at = self.clock().replace(microsecond=0).isoformat()
        self.last_result = ", ".join(f"{count} {name}" for name, count in summary.items() if count)
        return summary

    # Mapping helpers

    def _business_row(self, business_id):
        row = self.db.get_business(business_id)
        if row is None:
            raise not_found("Business not found.")
        return row

    def _business(self, row):
        bank = s.BankLink(linked=bool(row["bank_account_id"]))
        if row["bank_account_id"]:
            bank.account_mask = row["bank_account_id"][-4:]
            try:
                account_id, cents = self.bank.balance_cents(row["bank_customer_id"], row["bank_account_id"])
                if account_id != row["bank_account_id"]:
                    self.db.set_bank(row["id"], row["bank_customer_id"], account_id)
                    bank.account_mask = account_id[-4:]
                bank.balance_cents = cents
            except BankError as exc:
                bank.error = str(exc)
        return s.Business(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            industry=row["industry"],
            topics=topics.valid_ids(row["topics"]),
            bad_day_dollars=row["bad_day_dollars"],
            city=_city(row["city_id"]),
            bank=bank,
            created_at=row["created_at"],
        )

    def _summary(self, row, legs=None):
        legs = legs if legs is not None else self.db.legs(row["id"])
        return s.PolicySummary(
            id=row["id"],
            topic=row["topic"],
            title=row["title"],
            status=row["status"],
            closes_at=max((leg["close_time"] for leg in legs), default=row["created_at"]),
            payout_each_cents=row["payout_each_cents"],
            max_payout_cents=row["max_payout_cents"],
            premium_cents=row["premium_cents"],
            paid_cents=row["paid_cents"],
            created_at=row["created_at"],
        )

    def _detail(self, row):
        legs = self.db.legs(row["id"])
        return s.PolicyDetail(
            **self._summary(row, legs).model_dump(),
            why=row["why"],
            catch=row["catch"],
            terms=row["terms"],
            legs=[
                s.PolicyLeg(
                    ticker=leg["ticker"],
                    side=leg["side"],
                    label=leg["label"],
                    contracts=leg["contracts"],
                    fill_price=leg["fill_price"],
                    cost_cents=leg["cost_cents"],
                    simulated=bool(leg["simulated"]),
                    result=leg["result"],
                    close_time=leg["close_time"],
                )
                for leg in legs
            ],
            events=[s.PolicyEvent(kind=e["kind"], message=e["message"], created_at=e["created_at"]) for e in self.db.events(row["id"])],
            movements=[
                s.MoneyMovement(
                    kind=m["kind"], amount_cents=m["amount_cents"], status=m["status"], external_id=m["external_id"], created_at=m["created_at"]
                )
                for m in self.db.movements(row["id"])
            ],
        )


def _city(city_id):
    place = weather.city(city_id) if city_id else None
    return s.City(id=place.id, name=place.name, state=place.state) if place else None


def _advisor_view(row, place):
    return {
        "name": row["name"],
        "description": row["description"],
        "industry": row["industry"],
        "location": f"{place.name}, {place.state}" if place else None,
    }


def _title(events):
    titles = list(dict.fromkeys(event.get("title") or event["event_ticker"] for event in events))
    return titles[0] if len(titles) == 1 else f"{titles[0]} + {len(titles) - 1} more"


def _terms(payout_cents, legs):
    outcomes = "; ".join(f"“{leg['label']}” settles {leg['side'].upper()}" for leg in legs)
    scope = "for each of these that goes your way" if len(legs) > 1 else "if this goes your way"
    return (
        f"HedgeCast pays {dollars(payout_cents)} into your checking account {scope}, "
        f"according to Kalshi's official result: {outcomes}. No claim to file. Payment goes out automatically."
    )
