from typing import Dict, List, Optional

from pydantic import BaseModel, Field
from typing_extensions import Literal

PerilId = Literal["rain", "heat", "cold"]
BasisRisk = Literal["low", "medium", "high"]
PolicyStatus = Literal["PENDING", "ACTIVE", "AWAITING_RESULT", "PAID", "EXPIRED", "REFUNDED", "NEEDS_REVIEW"]


class City(BaseModel):
    id: str
    name: str
    state: str


class Peril(BaseModel):
    id: PerilId
    name: str
    description: str


class BankLink(BaseModel):
    linked: bool
    account_mask: Optional[str] = None
    balance_cents: Optional[int] = None
    error: Optional[str] = None


class Business(BaseModel):
    id: int
    name: str
    industry: str
    city: City
    bank: BankLink
    created_at: str


class BusinessListItem(BaseModel):
    id: int
    name: str
    industry: str
    city: City


class CreateBusiness(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    industry: str = Field(min_length=1, max_length=80)
    city_id: str


class SessionRequest(BaseModel):
    business_id: int


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


class CoverageOptions(BaseModel):
    peril: Peril
    station: Optional[Station] = None
    days: List[CoverageDay]
    message: Optional[str] = None


class QuoteRequest(BaseModel):
    peril: PerilId
    tickers: List[str] = Field(min_length=1, max_length=5)
    payout_dollars: int = Field(ge=1)


class QuoteLeg(BaseModel):
    ticker: str
    date: str
    label: str
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
    peril: Peril
    station: Station
    payout_per_day_cents: int
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
    date: str
    label: str
    contracts: int
    fill_price: Optional[str] = None
    cost_cents: int
    simulated: bool
    result: Optional[str] = None
    close_time: str


class PolicySummary(BaseModel):
    id: int
    peril: PerilId
    title: str
    station_name: str
    basis_risk: BasisRisk
    status: PolicyStatus
    coverage_dates: List[str]
    payout_per_day_cents: int
    max_payout_cents: int
    premium_cents: int
    paid_cents: int
    created_at: str


class PolicyDetail(PolicySummary):
    terms: str
    legs: List[PolicyLeg]
    events: List[PolicyEvent]
    movements: List[MoneyMovement]


class ActivityItem(BaseModel):
    policy_id: int
    message: str
    created_at: str


class Dashboard(BaseModel):
    business: Business
    active_coverage_cents: int
    premiums_paid_cents: int
    payouts_received_cents: int
    policies: List[PolicySummary]
    activity: List[ActivityItem]


class WorkerStatus(BaseModel):
    enabled: bool
    last_run_at: Optional[str] = None
    last_result: Optional[str] = None


class OpsPolicy(PolicySummary):
    business_name: str
    simulated: bool


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
