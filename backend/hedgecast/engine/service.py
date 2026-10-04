import sqlite3
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from .. import config, geo
from ..api import schemas as s
from ..errors import ServiceError, bad_request, conflict, not_found, unavailable
from ..integrations.market_data import MarketDataError
from ..integrations.money import BankError
from . import catalog, pricing
from .executors import HedgeError
from .money import dollars
from .settle import Settlement

OPEN_STATUSES = ("ACTIVE", "AWAITING_RESULT")
QUOTE_GRACE = timedelta(seconds=5)


class Service:
    def __init__(self, db, market_data, bank, executor, clock=None):
        self.db = db
        self.market_data = market_data
        self.bank = bank
        self.executor = executor
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.settlement = Settlement(db, market_data, bank, config.PAYOUT_MAX_ATTEMPTS, self.clock)
        self.max_price = Decimal(config.MAX_CONTRACT_PRICE)
        self.worker_enabled = False
        self.last_run_at = None
        self.last_result = None
        self._bind_lock = threading.Lock()

    # Reference data

    def cities(self):
        return [s.City(id=c.id, name=c.name, state=c.state) for c in geo.CITIES]

    def perils(self):
        return [s.Peril(id=key, **value) for key, value in catalog.PERILS.items()]

    # Businesses

    def list_businesses(self):
        return [
            s.BusinessListItem(id=row["id"], name=row["name"], industry=row["industry"], city=self._city(row["city_id"]))
            for row in self.db.list_businesses()
        ]

    def create_business(self, body):
        if geo.city(body.city_id) is None:
            raise bad_request("Choose a city from the list.")
        business_id = self.db.create_business(body.name.strip(), body.industry.strip(), body.city_id)
        return self.get_business(business_id)

    def get_business(self, business_id, with_balance=True):
        row = self._business_row(business_id)
        return self._business(row, with_balance)

    def link_bank(self, business_id):
        row = self._business_row(business_id)
        if not row["bank_account_id"]:
            place = geo.city(row["city_id"])
            try:
                customer_id, account_id = self.bank.link(row["name"], place.name)
            except BankError as exc:
                raise unavailable(f"Couldn't connect the bank: {exc}") from exc
            self.db.set_bank(business_id, customer_id, account_id)
        return self.get_business(business_id)

    # Coverage and quotes

    def coverage_options(self, business_id, peril):
        place = self._place(business_id)
        station, km = geo.nearest_station(place, peril)
        found = self._triggers(peril, station)
        days = {}
        for trigger in found:
            days.setdefault(trigger["date"], []).append(
                s.TriggerOption(
                    ticker=trigger["ticker"],
                    label=trigger["label"],
                    implied_probability=catalog.market_probability(trigger["market"]),
                )
            )
        message = None
        if not days:
            message = f"No {peril} markets are open for {station.name} right now. Kalshi lists daily weather markets about a day ahead."
        return s.CoverageOptions(
            peril=self._peril(peril),
            station=self._station(station, km),
            days=[s.CoverageDay(date=day, label=_day_label(day), triggers=items) for day, items in sorted(days.items())],
            message=message,
        )

    def quote(self, business_id, body):
        if body.payout_dollars > config.MAX_PAYOUT_DOLLARS:
            raise bad_request(f"The most a day can pay is {dollars(config.MAX_PAYOUT_DOLLARS * 100)} for now.")
        row = self._business_row(business_id)
        place = geo.city(row["city_id"])
        station, km = geo.nearest_station(place, body.peril)
        available = {t["ticker"]: t for t in self._triggers(body.peril, station)}
        chosen = []
        for ticker in body.tickers:
            if ticker not in available:
                raise bad_request("One of those days is no longer open. Pick again.")
            chosen.append(available[ticker])
        if len({t["date"] for t in chosen}) != len(chosen):
            raise bad_request("Pick one trigger per day.")
        chosen.sort(key=lambda t: t["date"])

        contracts = body.payout_dollars
        legs = []
        for trigger in chosen:
            try:
                book = self.market_data.orderbook(trigger["ticker"])
            except MarketDataError as exc:
                raise unavailable(f"Live prices are unavailable right now. {exc}") from exc
            priced = pricing.price_leg(book, contracts, self.max_price)
            priced.update(
                ticker=trigger["ticker"],
                date=trigger["date"],
                label=trigger["label"],
                close_time=trigger["close_time"],
                implied_probability=priced["implied_probability"]
                if priced["implied_probability"] is not None
                else (catalog.market_probability(trigger["market"]) or 0.0),
            )
            priced["cost_ceiling_cents"] = pricing.cost_ceiling_cents(priced, config.SLIPPAGE_BUFFER)
            legs.append(priced)

        premium_cents, breakdown = pricing.premium(legs, config.SLIPPAGE_BUFFER, config.PLATFORM_FEE, self.bank.unit_cents)
        max_fill = min(leg["depth_contracts"] for leg in legs)
        short = max_fill < contracts
        payout_cents = contracts * 100
        station_model = self._station(station, km)
        warnings = [
            f"The market already puts {_day_label(leg['date'])} at {round(leg['implied_probability'] * 100)}%. "
            "Cover costs close to what it pays."
            for leg in legs
            if leg["implied_probability"] >= 0.75
        ]
        quote_id = uuid.uuid4().hex
        expires_at = (self.clock() + timedelta(seconds=config.QUOTE_TTL_SECONDS)).isoformat()
        quote = s.Quote(
            id=quote_id,
            expires_at=expires_at,
            peril=self._peril(body.peril),
            station=station_model,
            payout_per_day_cents=payout_cents,
            max_payout_cents=payout_cents * len(legs),
            premium_cents=premium_cents,
            legs=[
                s.QuoteLeg(
                    ticker=leg["ticker"],
                    date=leg["date"],
                    label=leg["label"],
                    contracts=leg["contracts"],
                    avg_price=str(leg["avg_price"]),
                    cost_cents=leg["cost_cents"],
                    depth_contracts=leg["depth_contracts"],
                    implied_probability=leg["implied_probability"],
                )
                for leg in legs
            ],
            breakdown=s.QuoteBreakdown(**breakdown),
            terms=_terms(body.peril, station.name, payout_cents, legs),
            warnings=warnings,
            thin_book=s.ThinBook(short=short, max_payout_dollars=max_fill),
        )
        payload = {
            "quote": quote.model_dump(),
            "legs": [
                {key: leg[key] for key in ("ticker", "date", "label", "contracts", "close_time", "cost_ceiling_cents")}
                for leg in legs
            ],
            "station_code": station.code,
        }
        self.db.save_quote(quote_id, business_id, payload, premium_cents, expires_at)
        return quote

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
                        "peril": quote.peril.id,
                        "station_code": row["payload"]["station_code"],
                        "station_name": quote.station.name,
                        "basis_risk": quote.station.basis_risk,
                        "title": f"{quote.peril.name} cover · {quote.station.name}",
                        "terms": quote.terms,
                        "payout_per_day_cents": quote.payout_per_day_cents,
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
        self.db.transition(policy_id, ["PENDING"], "ACTIVE", "active", "Cover is active. We'll watch for the official result.")
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
        orphaned = getattr(error, "orphaned", [])
        if orphaned:
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

    # Policies and dashboard

    def list_policies(self, business_id):
        self._business_row(business_id)
        return [self._summary(row) for row in self.db.list_policies(business_id=business_id)]

    def get_policy(self, business_id, policy_id):
        row = self.db.get_policy(policy_id)
        if row is None or row["business_id"] != business_id:
            raise not_found("Policy not found.")
        return self._detail(row)

    def dashboard(self, business_id):
        business = self.get_business(business_id)
        rows = self.db.list_policies(business_id=business_id)
        summaries = [self._summary(row) for row in rows]
        premiums = sum(
            row["premium_cents"] for row in rows if row["status"] not in ("REFUNDED",)
        )
        return s.Dashboard(
            business=business,
            active_coverage_cents=sum(p.max_payout_cents for p in summaries if p.status in OPEN_STATUSES),
            premiums_paid_cents=premiums,
            payouts_received_cents=sum(p.paid_cents for p in summaries),
            policies=summaries,
            activity=[
                s.ActivityItem(policy_id=e["policy_id"], message=e["message"], created_at=e["created_at"])
                for e in self.db.recent_events(business_id)
            ],
        )

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
            raise ServiceError(404, "Business not found.")
        return row

    def _place(self, business_id):
        return geo.city(self._business_row(business_id)["city_id"])

    def _business(self, row, with_balance):
        bank = s.BankLink(linked=bool(row["bank_account_id"]))
        if row["bank_account_id"]:
            bank.account_mask = row["bank_account_id"][-4:]
            if with_balance:
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
            industry=row["industry"],
            city=self._city(row["city_id"]),
            bank=bank,
            created_at=row["created_at"],
        )

    @staticmethod
    def _city(city_id):
        place = geo.city(city_id)
        return s.City(id=place.id, name=place.name, state=place.state)

    @staticmethod
    def _peril(peril):
        return s.Peril(id=peril, **catalog.PERILS[peril])

    @staticmethod
    def _station(station, km):
        risk = geo.basis_risk(km)
        return s.Station(code=station.code, name=station.name, distance_km=round(km), basis_risk=risk, basis_note=geo.BASIS_NOTES[risk])

    def _triggers(self, peril, station):
        try:
            return catalog.triggers(self.market_data, peril, station, self.clock())
        except MarketDataError as exc:
            raise unavailable(f"Live market data is unavailable right now. {exc}") from exc

    def _summary(self, row, legs=None):
        legs = legs if legs is not None else self.db.legs(row["id"])
        return s.PolicySummary(
            id=row["id"],
            peril=row["peril"],
            title=row["title"],
            station_name=row["station_name"],
            basis_risk=row["basis_risk"],
            status=row["status"],
            coverage_dates=[leg["date"] for leg in legs],
            payout_per_day_cents=row["payout_per_day_cents"],
            max_payout_cents=row["max_payout_cents"],
            premium_cents=row["premium_cents"],
            paid_cents=row["paid_cents"],
            created_at=row["created_at"],
        )

    def _detail(self, row):
        legs = self.db.legs(row["id"])
        return s.PolicyDetail(
            **self._summary(row, legs).model_dump(),
            terms=row["terms"],
            legs=[
                s.PolicyLeg(
                    ticker=leg["ticker"],
                    date=leg["date"],
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


def _day_label(iso_day):
    return date.fromisoformat(iso_day).strftime("%a, %b %-d")


def _terms(peril, station_name, payout_cents, legs):
    days = "; ".join(f"{_day_label(leg['date'])}: {leg['label'].lower()}" for leg in legs)
    unit = "each covered day" if len(legs) > 1 else "the covered day"
    return (
        f"HedgeCast pays {dollars(payout_cents)} into your checking account for {unit} that the official "
        f"{station_name} reading shows the covered weather ({days}). No claim to file. "
        "Payment goes out automatically once the result is official."
    )
