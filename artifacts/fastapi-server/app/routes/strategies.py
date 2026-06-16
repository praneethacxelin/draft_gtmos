import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from app.db import get_session, SessionLocal, Strategy, Competitor, PatternCluster, User
from app.auth import current_user
from app.scoping import own_strategy
from app.services import audit_service
from app.agents.s1_strategy import run_s1
from app.agents.s1_graph import stream_s1
from app.agents.s2_signals import (
    run_market_sizing,
    run_competitors,
    run_lead_search,
    run_signals,
    score_leads,
    recognize_patterns,
    fetch_contact_emails,
    fetch_contact_phones,
)
from app.agents.roi_validator import validate_roi

router = APIRouter(prefix="/strategies", tags=["strategies"])


class StrategyCreate(BaseModel):
    product_name: str
    description: str = ""
    target_market: str | None = None
    pain_points_raw: str | None = None


@router.get("")
def list_strategies(
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    rows = (
        db.query(Strategy)
        .order_by(Strategy.created_at.desc())
        .all()
    )
    return [_serialize(r) for r in rows]


@router.post("")
def create_strategy(
    body: StrategyCreate,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    s = Strategy(
        user_id=user.id,
        product_name=body.product_name,
        description=body.description,
        target_market=body.target_market,
        pain_points_raw=body.pain_points_raw,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    audit_service.log_pipeline_event(
        stage="strategy_created",
        service="s1_strategy",
        strategy_id=s.id,
        strategy_name=s.product_name,
        inputs={
            "product_name": body.product_name,
            "description": body.description,
            "target_market": body.target_market,
            "pain_points_raw": body.pain_points_raw,
        },
        actor="user",
        summary=f"Strategy Created: \"{s.product_name}\" — user entered initial brief",
    )
    return _serialize(s)


@router.get("/{strategy_id}")
def get_strategy(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    return _serialize(own_strategy(db, strategy_id, user))


@router.delete("/{strategy_id}")
def delete_strategy(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    s = own_strategy(db, strategy_id, user)
    db.delete(s)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# PATCH endpoints — inline editing from the frontend
# ---------------------------------------------------------------------------

class StrategyPatch(BaseModel):
    product_name: str | None = None
    description: str | None = None
    target_market: str | None = None
    pain_points_raw: str | None = None


class IcpSectionPatch(BaseModel):
    industries: list | None = None
    employee_size_range: str | None = None
    revenue_range: str | None = None
    geographies: list | None = None
    tech_stack_signals: list | None = None
    segments: list | None = None


class PersonasSectionPatch(BaseModel):
    champion: dict | None = None
    economic_buyer: dict | None = None
    blocker: dict | None = None


class ProblemsSectionPatch(BaseModel):
    problems: list


class UseCasesSectionPatch(BaseModel):
    use_cases: list


@router.patch("/{strategy_id}")
def patch_strategy(
    strategy_id: str,
    body: StrategyPatch,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    s = own_strategy(db, strategy_id, user)
    changes = body.model_dump(exclude_unset=True)
    before = {k: getattr(s, k) for k in changes}
    for field, val in changes.items():
        setattr(s, field, val)
    db.commit()
    db.refresh(s)
    for field, old_val in before.items():
        audit_service.log_change(
            event_type="strategy_change",
            entity_type="strategy",
            entity_id=s.id,
            strategy_id=s.id,
            strategy_name=s.product_name,
            change_field=field,
            change_before=old_val,
            change_after=getattr(s, field),
            actor="user",
            summary=f"Strategy \"{s.product_name}\" · {field} updated",
        )
    return _serialize(s)


@router.patch("/{strategy_id}/icp")
def patch_icp(
    strategy_id: str,
    body: IcpSectionPatch,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    s = own_strategy(db, strategy_id, user)
    before = dict(s.icp_json or {})
    current = dict(s.icp_json or {})
    current.update(body.model_dump(exclude_unset=True))
    s.icp_json = current
    db.commit()
    db.refresh(s)
    audit_service.log_change(
        event_type="strategy_change",
        entity_type="strategy",
        entity_id=s.id,
        strategy_id=s.id,
        strategy_name=s.product_name,
        change_field="icp",
        change_before=before,
        change_after=dict(s.icp_json or {}),
        actor="user",
        summary=f"Strategy \"{s.product_name}\" · ICP updated",
    )
    return _serialize(s)


@router.patch("/{strategy_id}/discovery")
def patch_discovery(
    strategy_id: str,
    body: dict,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    s = own_strategy(db, strategy_id, user)
    before = dict(s.discovery_data or {})
    current = dict(s.discovery_data or {})
    current.update(body)
    s.discovery_data = current
    # Mirror key discovery answers onto the top-level columns so list views,
    # exports, and the S1 gate stay in sync (the questionnaire is the source of
    # truth, but `description`/`pain_points_raw` are what the UI reads).
    product_desc = _discovery_value(current.get("product_description"))
    if product_desc:
        s.description = product_desc
    pain_points = _discovery_value(current.get("pain_points"))
    if pain_points:
        s.pain_points_raw = pain_points
    db.commit()
    db.refresh(s)
    audit_service.log_change(
        event_type="strategy_change",
        entity_type="strategy",
        entity_id=s.id,
        strategy_id=s.id,
        strategy_name=s.product_name,
        change_field="discovery_data",
        change_before=before,
        change_after=dict(s.discovery_data or {}),
        actor="user",
        summary=f"Strategy \"{s.product_name}\" · Discovery data updated",
    )
    return _serialize(s)


@router.patch("/{strategy_id}/personas")
def patch_personas(
    strategy_id: str,
    body: PersonasSectionPatch,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    s = own_strategy(db, strategy_id, user)
    before = dict(s.personas_json or {})
    current = dict(s.personas_json or {})
    current.update(body.model_dump(exclude_unset=True))
    s.personas_json = current
    db.commit()
    db.refresh(s)
    audit_service.log_change(
        event_type="strategy_change",
        entity_type="strategy",
        entity_id=s.id,
        strategy_id=s.id,
        strategy_name=s.product_name,
        change_field="personas",
        change_before=before,
        change_after=dict(s.personas_json or {}),
        actor="user",
        summary=f"Strategy \"{s.product_name}\" · Personas updated",
    )
    return _serialize(s)


@router.patch("/{strategy_id}/problems")
def patch_problems(
    strategy_id: str,
    body: ProblemsSectionPatch,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    s = own_strategy(db, strategy_id, user)
    before = dict(s.problems_json or {})
    current = dict(s.problems_json or {})
    current["problems"] = body.problems
    s.problems_json = current
    db.commit()
    db.refresh(s)
    audit_service.log_change(
        event_type="strategy_change",
        entity_type="strategy",
        entity_id=s.id,
        strategy_id=s.id,
        strategy_name=s.product_name,
        change_field="problems",
        change_before=before,
        change_after=dict(s.problems_json or {}),
        actor="user",
        summary=f"Strategy \"{s.product_name}\" · Problems updated",
    )
    return _serialize(s)


@router.patch("/{strategy_id}/use-cases")
def patch_use_cases(
    strategy_id: str,
    body: UseCasesSectionPatch,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    s = own_strategy(db, strategy_id, user)
    before = dict(s.use_cases_json or {})
    current = dict(s.use_cases_json or {})
    current["use_cases"] = body.use_cases
    s.use_cases_json = current
    db.commit()
    db.refresh(s)
    audit_service.log_change(
        event_type="strategy_change",
        entity_type="strategy",
        entity_id=s.id,
        strategy_id=s.id,
        strategy_name=s.product_name,
        change_field="use_cases",
        change_before=before,
        change_after=dict(s.use_cases_json or {}),
        actor="user",
        summary=f"Strategy \"{s.product_name}\" · Use Cases updated",
    )
    return _serialize(s)


def _discovery_value(val):
    """Clean a discovery field into a non-empty string, or '' if blank."""
    if val is None:
        return ""
    if isinstance(val, list):
        clean = [v for v in val if v and v != "__other__"]
        return ", ".join(clean)
    if isinstance(val, str) and val.strip() and val != "__other__":
        return val.strip()
    return ""


def discovery_core_ready(strategy) -> tuple[bool, list[str]]:
    """Has the user supplied enough discovery to run S1 on real data?

    Core fields: a product description, the pain points it solves, and at
    least one buyer role (economic buyer or champion). Without these, S1 would
    hallucinate from the product name alone — wasting tokens and producing
    fake results. Falls back to the legacy ``description``/``pain_points_raw``
    columns so older profiles still qualify.
    """
    dd = strategy.discovery_data or {}
    missing = []
    if not (_discovery_value(dd.get("product_description")) or (strategy.description or "").strip()):
        missing.append("product description")
    if not (_discovery_value(dd.get("pain_points")) or (strategy.pain_points_raw or "").strip()):
        missing.append("pain points")
    if not (_discovery_value(dd.get("economic_buyer")) or _discovery_value(dd.get("champion"))):
        missing.append("economic buyer or champion")
    return (len(missing) == 0, missing)


def _s1_event_gen(strategy_id: str):
    async def event_gen():
        db2 = SessionLocal()
        try:
            strategy = db2.query(Strategy).filter(Strategy.id == strategy_id).first()
            if strategy is not None:
                ready, missing = discovery_core_ready(strategy)
                if not ready:
                    yield {
                        "event": "error",
                        "data": json.dumps({
                            "status": 422,
                            "code": "discovery_incomplete",
                            "missing": missing,
                            "message": (
                                "Fill in the discovery form first ("
                                + ", ".join(missing)
                                + ") so S1 runs on your real inputs instead of guessing."
                            ),
                        }),
                    }
                    return
            async for ev in stream_s1(db2, strategy_id):
                yield {"event": ev["event"], "data": json.dumps(ev["data"])}
        finally:
            db2.close()
    return event_gen



@router.post("/{strategy_id}/run")
async def run_s1_stream_post(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """Trigger and stream the S1 LangGraph pipeline via SSE (POST)."""
    own_strategy(db, strategy_id, user)
    return EventSourceResponse(_s1_event_gen(strategy_id)())


@router.get("/{strategy_id}/run")
async def run_s1_stream_get(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """Backwards-compatible GET variant for browsers using EventSource()."""
    own_strategy(db, strategy_id, user)
    return EventSourceResponse(_s1_event_gen(strategy_id)())


def _sse(coro_or_value, label: str):
    """Wrap a coroutine or sync value in a 3-event SSE stream
    (stage_start → stage_complete → complete) using a fresh DB session.

    Rate-limit hits propagate as a typed ``error`` event with
    ``status: 429`` and ``retry_after_seconds`` so the frontend
    ``streamSse`` helper can surface the same friendly toast as the
    JSON ``apiFetch`` path.
    """
    from app.services.rate_limit import RateLimitExceeded

    async def gen():
        yield {"event": "stage_start", "data": json.dumps({"stage": label})}
        db2 = SessionLocal()
        try:
            result = await coro_or_value(db2)
            yield {"event": "stage_complete", "data": json.dumps({"stage": label, "result": result})}
            yield {"event": "complete", "data": json.dumps({"stage": label})}
        except RateLimitExceeded as rle:
            yield {"event": "error", "data": json.dumps({
                "status": 429,
                "integration": rle.name,
                "retry_after_seconds": int(rle.retry_after),
                "message": str(rle),
            })}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"message": str(e)})}
        finally:
            db2.close()
    return EventSourceResponse(gen())


class RoiValidateRequest(BaseModel):
    investment_usd: float
    expected_revenue_usd: float
    timeframe_months: int = 12
    market_segment: str | None = None
    notes: str | None = None


@router.post("/{strategy_id}/roi/validate")
async def roi_validate(
    strategy_id: str,
    body: RoiValidateRequest,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    own_strategy(db, strategy_id, user)
    result = await validate_roi(
        db,
        strategy_id,
        investment_usd=body.investment_usd,
        expected_revenue_usd=body.expected_revenue_usd,
        timeframe_months=body.timeframe_months,
        market_segment=body.market_segment,
        notes=body.notes,
    )
    if isinstance(result, dict) and "_error" in result:
        raise HTTPException(status_code=502, detail=result["_error"])
    return result


@router.post("/{strategy_id}/market-sizing")
async def market_sizing(
    strategy_id: str,
    limit: int | None = Query(None, ge=1, le=10),
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    own_strategy(db, strategy_id, user)
    return _sse(lambda d: run_market_sizing(d, strategy_id, limit=limit), "market_sizing")


@router.post("/{strategy_id}/competitors/run")
async def run_competitor_research(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    own_strategy(db, strategy_id, user)
    return _sse(lambda d: run_competitors(d, strategy_id), "competitors")


@router.get("/{strategy_id}/competitors")
def list_competitors(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    own_strategy(db, strategy_id, user)
    rows = db.query(Competitor).filter(Competitor.strategy_id == strategy_id).all()
    return [{
        "id": r.id,
        "name": r.name,
        "website": r.website,
        "positioning": r.positioning,
        "features": r.features_json,
        "pricing_info": r.pricing_info,
        "weaknesses": r.weaknesses_json,
        "g2_rating": r.g2_rating,
    } for r in rows]


@router.post("/{strategy_id}/leads/search")
async def lead_search(
    strategy_id: str,
    limit: int | None = Query(None, ge=1, le=25),
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    own_strategy(db, strategy_id, user)
    return _sse(lambda d: run_lead_search(d, strategy_id, limit=limit), "leads")


@router.post("/{strategy_id}/signals/run")
async def signals_run(
    strategy_id: str,
    limit: int | None = Query(None, ge=1, le=10),
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    own_strategy(db, strategy_id, user)
    return _sse(lambda d: run_signals(d, strategy_id, limit=limit), "signals")


@router.post("/{strategy_id}/score")
def score_run(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    own_strategy(db, strategy_id, user)
    async def _run(d):
        return score_leads(d, strategy_id)
    return _sse(_run, "score")


@router.post("/{strategy_id}/contacts/fetch-emails")
async def contacts_fetch_emails(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """Reveal emails for contacts missing one via Apollo /v1/people/match.
    Each successful reveal costs an Apollo email credit."""
    own_strategy(db, strategy_id, user)
    return _sse(lambda d: fetch_contact_emails(d, strategy_id), "fetch_emails")


@router.post("/{strategy_id}/contacts/fetch-phones")
async def contacts_fetch_phones(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """Reveal phone numbers for contacts missing one via Apollo /v1/people/match.
    Each successful reveal costs an Apollo phone credit."""
    own_strategy(db, strategy_id, user)
    return _sse(lambda d: fetch_contact_phones(d, strategy_id), "fetch_phones")


@router.post("/{strategy_id}/patterns/run")
def patterns_run(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    own_strategy(db, strategy_id, user)
    async def _run(d):
        return recognize_patterns(d, strategy_id)
    return _sse(_run, "patterns")


@router.get("/{strategy_id}/patterns")
def patterns_list(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    own_strategy(db, strategy_id, user)
    rows = db.query(PatternCluster).filter(PatternCluster.strategy_id == strategy_id).all()
    return [{
        "id": r.id,
        "pattern_name": r.pattern_name,
        "signal_combination": r.signal_combination_json,
        "conversion_rate": r.conversion_rate,
    } for r in rows]


def _serialize(s: Strategy) -> dict:
    return {
        "id": s.id,
        "product_name": s.product_name,
        "description": s.description,
        "target_market": s.target_market,
        "pain_points_raw": s.pain_points_raw,
        "icp": s.icp_json,
        "personas": s.personas_json,
        "problems": s.problems_json,
        "naics": s.naics_json,
        "stakeholder_map": s.stakeholder_map_json,
        "use_cases": s.use_cases_json,
        "tam_sam_som": s.tam_sam_som_json,
        "roi": s.roi_json,
        "status": s.status,
        "discovery_data": s.discovery_data,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
