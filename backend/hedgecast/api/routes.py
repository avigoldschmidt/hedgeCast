from typing import List, Optional

from fastapi import APIRouter, Cookie, Depends, Request, Response

from ..errors import ServiceError
from . import schemas as s

SESSION_COOKIE = "hc_business"

router = APIRouter(prefix="/api")


def service(request: Request):
    return request.app.state.service


def business_id(hc_business: Optional[str] = Cookie(default=None)) -> int:
    try:
        return int(hc_business or "")
    except ValueError:
        raise ServiceError(401, "Set up your business first.") from None


def _remember(response: Response, value: int):
    response.set_cookie(SESSION_COOKIE, str(value), httponly=True, samesite="lax", max_age=60 * 60 * 24 * 90)


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/cities", response_model=List[s.City])
def cities(svc=Depends(service)):
    return svc.cities()


@router.get("/topics", response_model=List[s.TopicInfo])
def topic_list(svc=Depends(service)):
    return svc.topic_list()


@router.get("/businesses", response_model=List[s.BusinessListItem])
def businesses(svc=Depends(service)):
    return svc.list_businesses()


@router.post("/businesses", response_model=s.Business)
def create_business(body: s.CreateBusiness, response: Response, svc=Depends(service)):
    business = svc.create_business(body)
    _remember(response, business.id)
    return business


@router.post("/session", response_model=s.Business)
def start_session(body: s.SessionRequest, response: Response, svc=Depends(service)):
    business = svc.get_business(body.business_id)
    _remember(response, business.id)
    return business


@router.delete("/session")
def end_session(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me", response_model=s.Business)
def me(bid: int = Depends(business_id), svc=Depends(service)):
    return svc.get_business(bid)


@router.post("/me/bank", response_model=s.Business)
def link_bank(bid: int = Depends(business_id), svc=Depends(service)):
    return svc.link_bank(bid)


@router.put("/me/topics", response_model=s.Business)
def set_topics(body: s.TopicsUpdate, bid: int = Depends(business_id), svc=Depends(service)):
    return svc.set_topics(bid, body)


@router.get("/forecast", response_model=s.Forecast)
def forecast(bid: int = Depends(business_id), svc=Depends(service)):
    return svc.forecast(bid)


@router.post("/ask", response_model=s.AskResult)
def ask(body: s.AskRequest, bid: int = Depends(business_id), svc=Depends(service)):
    return svc.ask(bid, body)


@router.post("/quotes", response_model=s.Quote)
def quote(body: s.QuoteRequest, bid: int = Depends(business_id), svc=Depends(service)):
    return svc.quote(bid, body)


@router.post("/policies", response_model=s.PolicyDetail)
def bind(body: s.BindRequest, bid: int = Depends(business_id), svc=Depends(service)):
    return svc.bind(bid, body)


@router.get("/policies", response_model=List[s.PolicySummary])
def policies(bid: int = Depends(business_id), svc=Depends(service)):
    return svc.list_policies(bid)


@router.get("/policies/{policy_id}", response_model=s.PolicyDetail)
def policy(policy_id: int, bid: int = Depends(business_id), svc=Depends(service)):
    return svc.get_policy(bid, policy_id)


@router.get("/ops", response_model=s.OpsOverview)
def ops(svc=Depends(service)):
    return svc.ops_overview()


@router.post("/ops/policies/{policy_id}/resolve", response_model=s.PolicyDetail)
def ops_resolve(policy_id: int, body: s.ResolveRequest, svc=Depends(service)):
    return svc.demo_resolve(policy_id, body.result)


@router.post("/ops/settle", response_model=s.OpsOverview)
def ops_settle(svc=Depends(service)):
    svc.run_settlement()
    return svc.ops_overview()
