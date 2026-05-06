import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from app.db import get_session, SessionLocal, Strategy, Competitor, PatternCluster
from app.agents.s1_strategy import run_s1
from app.agents.s2_signals import (
    run_market_sizing,
    run_competitors,
    run_lead_search,
    run_signals,
    score_leads,
    recognize_patterns,
)

router = APIRouter(prefix="/strategies", tags=["strategies"])


class StrategyCreate(BaseModel):
    product_name: str
    description: str
    target_market: str | None = None
    pain_points_raw: str | None = None


@router.get("")
def list_strategies(db: Session = Depends(get_session)) -> list[dict]:
    rows = db.query(Strategy).order_by(Strategy.created_at.desc()).all()
    return [_serialize(r) for r in rows]


@router.post("")
def create_strategy(body: StrategyCreate, db: Session = Depends(get_session)) -> dict:
    s = Strategy(
        product_name=body.product_name,
        description=body.description,
        target_market=body.target_market,
        pain_points_raw=body.pain_points_raw,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _serialize(s)


@router.get("/{strategy_id}")
def get_strategy(strategy_id: str, db: Session = Depends(get_session)) -> dict:
    s = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not s:
        raise HTTPException(404, "Not found")
    return _serialize(s)


@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: str, db: Session = Depends(get_session)) -> dict:
    s = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not s:
        raise HTTPException(404, "Not found")
    db.delete(s)
    db.commit()
    return {"ok": True}


@router.get("/{strategy_id}/run")
async def run_s1_stream(strategy_id: str):
    """Stream S1 generation progress via SSE."""
    async def event_gen():
        # Use a fresh session per stream to avoid leaking the request session
        db2 = SessionLocal()
        try:
            async for ev in run_s1(db2, strategy_id):
                yield {"event": ev["event"], "data": json.dumps(ev["data"])}
        finally:
            db2.close()
    return EventSourceResponse(event_gen())


@router.post("/{strategy_id}/market-sizing")
async def market_sizing(strategy_id: str, db: Session = Depends(get_session)) -> dict:
    return await run_market_sizing(db, strategy_id)


@router.post("/{strategy_id}/competitors/run")
async def run_competitor_research(strategy_id: str, db: Session = Depends(get_session)) -> list[dict]:
    return await run_competitors(db, strategy_id)


@router.get("/{strategy_id}/competitors")
def list_competitors(strategy_id: str, db: Session = Depends(get_session)) -> list[dict]:
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
async def lead_search(strategy_id: str, db: Session = Depends(get_session)) -> dict:
    return await run_lead_search(db, strategy_id)


@router.post("/{strategy_id}/signals/run")
async def signals_run(strategy_id: str, db: Session = Depends(get_session)) -> dict:
    return await run_signals(db, strategy_id)


@router.post("/{strategy_id}/score")
def score_run(strategy_id: str, db: Session = Depends(get_session)) -> dict:
    return score_leads(db, strategy_id)


@router.post("/{strategy_id}/patterns/run")
def patterns_run(strategy_id: str, db: Session = Depends(get_session)) -> dict:
    return recognize_patterns(db, strategy_id)


@router.get("/{strategy_id}/patterns")
def patterns_list(strategy_id: str, db: Session = Depends(get_session)) -> list[dict]:
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
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
