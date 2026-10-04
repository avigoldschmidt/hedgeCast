from typing import Dict, List, Optional

from pydantic import BaseModel, Field
from typing_extensions import Literal

Side = Literal["yes", "no"]
TopicId = Literal["weather", "fuel", "rates", "prices", "tariffs", "sports", "jobs", "other"]
PerilId = Literal["rain", "heat", "cold"]
BasisRisk = Literal["low", "medium", "high"]
PolicyStatus = Literal["PENDING", "ACTIVE", "AWAITING_RESULT", "PAID", "EXPIRED", "REFUNDED", "NEEDS_REVIEW"]


# Businesses


class City(BaseModel):
    id: str
    name: str
    state: str


class TopicInfo(BaseModel):
    id: TopicId
    name: str
    blurb: str


class IndustryInfo(BaseModel):
    name: str


class BankLink(BaseModel):
    linked: bool
    account_mask: Optional[str] = None
    balance_cents: Optional[int] = None
    error: Optional[str] = None


class Business(BaseModel):
    id: int
    name: str
    description: str
    industry: str
    topics: List[TopicId]
    bad_day_dollars: int
    city: Optional[City] = None
    bank: BankLink
    created_at: str


class BusinessListItem(BaseModel):
    id: int
    name: str
    industry: str
    city: Optional[City] = None


class CreateBusiness(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    industry: str = Field(min_length=1, max_length=80)
    city_id: Optional[str] = None


class TopicsUpdate(BaseModel):
    topics: List[TopicId] = Field(min_length=1, max_length=7)


class CityUpdate(BaseModel):
    city_id: str = Field(min_length=1, max_length=80)


class SessionRequest(BaseModel):
    business_id: int


# Forecast


class Choice(BaseModel):
    ticker: str
    label: str
    chance: Optional[float] = None
    closes_at: str


class PlanCard(BaseModel):
    id: str
    topic: TopicId
    title: str
    group_title: str
    why: str
    catch: str
    warnings: List[str]
    side: Side
    ticker: str
    chance: Optional[float] = None
    closes_at: str
    choices: List[Choice]


class Forecast(BaseModel):
    cards: List[PlanCard]
    note: Optional[str] = None


class SearchResult(BaseModel):
    cards: List[PlanCard]
    message: str


# Weather wizard


class Peril(BaseModel):
    id: PerilId
    name: str
    description: str


class Station(BaseModel):
    code: str
    name: str
    distance_km: int
    basis_risk: BasisRisk
    basis_note: str


class TriggerOption(BaseModel):
    ticker: str
    label: str
    implied_probability: Optional[float] = None


class CoverageDay(BaseModel):
    date: str
    label: str
    triggers: List[TriggerOption]


class WeatherOptions(BaseModel):
    peril: Peril
    station: Station
    days: List[CoverageDay]
    message: Optional[str] = None


# Topic browse


class BrowseOption(BaseModel):
    ticker: str
    label: str
    chance: Optional[float] = None
    closes_at: str


class BrowseGroup(BaseModel):
    id: str
    title: str
    settles_on: str
    warning: Optional[str] = None
    options: List[BrowseOption]


class BrowseResult(BaseModel):
    topic: TopicId
    groups: List[BrowseGroup]
    message: Optional[str] = None


# Quotes


class LegRequest(BaseModel):
    ticker: str
    side: Side = "yes"


class PlanText(BaseModel):
    topic: TopicId
    title: str = Field(min_length=1, max_length=120)
    why: str = Field(default="", max_length=300)
    catch: str = Field(default="", max_length=300)


class QuoteRequest(BaseModel):
    legs: List[LegRequest] = Field(min_length=1, max_length=5)
    payout_dollars: int = Field(ge=1)
    plan: Optional[PlanText] = None


class QuoteLeg(BaseModel):
    ticker: str
    side: Side
    label: str
    close_time: str
    contracts: int
    avg_price: str
    cost_cents: int
    depth_contracts: int
    implied_probability: float


class QuoteBreakdown(BaseModel):
    hedge_cost_cents: int
    exchange_fee_cents: int
    buffer_cents: int
    platform_fee_cents: int
    rounding_cents: int


class ThinBook(BaseModel):
    short: bool
    max_payout_dollars: int


class Quote(BaseModel):
    id: str
    expires_at: str
    title: str
    topic: TopicId
    why: str
    catch: str
    payout_each_cents: int
    max_payout_cents: int
    premium_cents: int
    legs: List[QuoteLeg]
    breakdown: QuoteBreakdown
    terms: str
    warnings: List[str]
    thin_book: ThinBook


class BindRequest(BaseModel):
    quote_id: str
    all_or_nothing: bool = False


# Policies


class PolicyEvent(BaseModel):
    kind: str
    message: str
    created_at: str


class MoneyMovement(BaseModel):
    kind: Literal["premium", "refund", "payout"]
    amount_cents: int
    status: Literal["pending", "done", "failed"]
    external_id: Optional[str] = None
    created_at: str


class PolicyLeg(BaseModel):
    ticker: str
    side: Side
    label: str
    contracts: int
    fill_price: Optional[str] = None
    limit_price: Optional[str] = None
    cost_cents: int
    fee_cents: int = 0
    order_id: Optional[str] = None
    simulated: bool
    result: Optional[str] = None
    close_time: str


class PolicySummary(BaseModel):
    id: int
    topic: TopicId
    title: str
    status: PolicyStatus
    closes_at: str
    payout_each_cents: int
    max_payout_cents: int
    premium_cents: int
    paid_cents: int
    created_at: str


class PolicyDetail(PolicySummary):
    why: str
    catch: str
    terms: str
    legs: List[PolicyLeg]
    events: List[PolicyEvent]
    movements: List[MoneyMovement]


# Risk desk


class WorkerStatus(BaseModel):
    enabled: bool
    last_run_at: Optional[str] = None
    last_result: Optional[str] = None


class OpsPolicy(PolicySummary):
    business_name: str
    simulated: bool
    covered_side: Literal["yes", "no", "mixed"]
    legs: List[PolicyLeg] = []


class OpsOverview(BaseModel):
    hedge_mode: str
    data_source: str
    reserve_balance_cents: Optional[int] = None
    reserve_error: Optional[str] = None
    worker: WorkerStatus
    counts: Dict[str, int]
    policies: List[OpsPolicy]


class ResolveRequest(BaseModel):
    result: Literal["yes", "no"]
