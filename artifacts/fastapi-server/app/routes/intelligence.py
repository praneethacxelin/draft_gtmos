"""M3 endpoints — engagement, intent, feedback, attribution, qualification, loop-back."""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import (
    get_session,
    EngagementEvent,
    AttributionEvent,
    QualificationRecord,
    GtmLoopUpdate,
    FeedbackEntry,
    IntentScore,
    Account,
    Contact,
    User,
)
from app.auth import current_user
from app.scoping import own_strategy, own_contact
from app.llm import MODEL_NAME
from app.agents.m3_intent import (
    score_intent,
    capture_feedback_with_ai,
    qualify_contact,
    loop_back,
    apply_loop_back,
)

router = APIRouter(prefix="/m3", tags=["intelligence"])


class EngagementBody(BaseModel):
    strategy_id: str
    contact_id: str | None = None
    account_id: str | None = None
    channel: str
    event_type: str
    intent_contribution_score: float | None = None
    metadata: dict | None = None


class FeedbackBody(BaseModel):
    strategy_id: str
    source: str
    raw_text: str
    contact_id: str | None = None


class AttributionBody(BaseModel):
    strategy_id: str
    contact_id: str | None = None
    source_channel: str
    touchpoint_type: str | None = None
    conversion_event: str
    conversion_value: float = 0.0


@router.post("/events")
def post_event(
    body: EngagementBody,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    own_strategy(db, body.strategy_id, user)
    weights = {
        "page_view": 2,
        "pricing_view": 8,
        "demo_request": 12,
        "case_study_view": 6,
        "ad_click": 3,
        "video_view": 4,
        "form_fill": 7,
        "email_open": 1,
    }
    score = body.intent_contribution_score or weights.get(body.event_type, 1)
    ev = EngagementEvent(
        strategy_id=body.strategy_id,
        contact_id=body.contact_id,
        account_id=body.account_id,
        channel=body.channel,
        event_type=body.event_type,
        intent_contribution_score=score,
        metadata_json=body.metadata,
    )
    db.add(ev)
    db.commit()
    return {"ok": True}


@router.get("/events")
def list_events(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    own_strategy(db, strategy_id, user)
    rows = (
        db.query(EngagementEvent)
        .filter(EngagementEvent.strategy_id == strategy_id)
        .order_by(EngagementEvent.occurred_at.desc())
        .limit(100)
        .all()
    )
    return [{
        "id": e.id,
        "channel": e.channel,
        "event_type": e.event_type,
        "intent_contribution_score": e.intent_contribution_score,
        "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
        "account_id": e.account_id,
        "contact_id": e.contact_id,
    } for e in rows]


@router.post("/score-intent")
def post_score_intent(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    own_strategy(db, strategy_id, user)
    return score_intent(db, strategy_id)


@router.get("/intent")
def get_intent(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    own_strategy(db, strategy_id, user)
    accounts = {a.id: a for a in db.query(Account).filter(Account.strategy_id == strategy_id).all()}
    rows = (
        db.query(IntentScore)
        .filter(IntentScore.strategy_id == strategy_id)
        .order_by(IntentScore.score.desc())
        .all()
    )
    return [{
        "account_id": r.account_id,
        "company_name": accounts[r.account_id].company_name if r.account_id in accounts else None,
        "score": r.score,
        "classification": r.classification,
        "computed_at": r.computed_at.isoformat() if r.computed_at else None,
    } for r in rows]


@router.post("/feedback")
async def post_feedback(
    body: FeedbackBody,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    own_strategy(db, body.strategy_id, user)
    f = await capture_feedback_with_ai(db, body.strategy_id, body.source, body.raw_text, body.contact_id)
    return {
        "id": f.id,
        "sentiment": f.sentiment,
        "themes": f.themes_json,
        "provenance": {
            "source": "ai_generated",
            "logic": "Sentiment + themes extracted by the model from the verbatim feedback text.",
            "steps": [
                "Send raw feedback to the model",
                "Parse JSON: sentiment + themes[]",
                "Persist FeedbackEntry",
            ],
            "model": MODEL_NAME,
            "counts": {"themes": len(f.themes_json or [])},
        },
    }


@router.get("/feedback")
def list_feedback(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    own_strategy(db, strategy_id, user)
    rows = (
        db.query(FeedbackEntry)
        .filter(FeedbackEntry.strategy_id == strategy_id)
        .order_by(FeedbackEntry.captured_at.desc())
        .all()
    )
    return [{
        "id": r.id,
        "source": r.source,
        "sentiment": r.sentiment,
        "themes": r.themes_json,
        "raw_text": r.raw_text,
        "captured_at": r.captured_at.isoformat() if r.captured_at else None,
    } for r in rows]


@router.post("/attribution")
def post_attribution(
    body: AttributionBody,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    own_strategy(db, body.strategy_id, user)
    a = AttributionEvent(
        strategy_id=body.strategy_id,
        contact_id=body.contact_id,
        source_channel=body.source_channel,
        touchpoint_type=body.touchpoint_type,
        conversion_event=body.conversion_event,
        conversion_value=body.conversion_value,
    )
    db.add(a)
    db.commit()
    return {"id": a.id}


@router.get("/attribution/summary")
def attribution_summary(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    own_strategy(db, strategy_id, user)
    rows = (
        db.query(
            AttributionEvent.source_channel,
            func.count().label("count"),
            func.sum(AttributionEvent.conversion_value).label("value"),
        )
        .filter(AttributionEvent.strategy_id == strategy_id)
        .group_by(AttributionEvent.source_channel)
        .all()
    )
    return [{"channel": r[0], "count": int(r[1]), "value": float(r[2] or 0)} for r in rows]


@router.post("/qualify/{contact_id}")
def post_qualify(
    contact_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    own_contact(db, contact_id, user)
    return qualify_contact(db, contact_id)


@router.get("/qualification-summary")
def qualification_summary(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    own_strategy(db, strategy_id, user)
    counts = {"sql": 0, "mql": 0, "nurture": 0}
    for r in db.query(QualificationRecord.status, func.count()).filter(
        QualificationRecord.strategy_id == strategy_id
    ).group_by(QualificationRecord.status).all():
        counts[r[0]] = int(r[1])
    return counts


@router.post("/loop-back")
async def post_loop_back(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    own_strategy(db, strategy_id, user)
    return await loop_back(db, strategy_id)


@router.get("/loop-back")
def list_loop_back(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    own_strategy(db, strategy_id, user)
    rows = (
        db.query(GtmLoopUpdate)
        .filter(GtmLoopUpdate.strategy_id == strategy_id)
        .order_by(GtmLoopUpdate.created_at.desc())
        .all()
    )
    return [{
        "id": r.id,
        "delta": r.suggested_icp_delta_json,
        "trigger_summary": r.trigger_summary,
        "applied": r.applied,
        "applied_at": r.applied_at.isoformat() if r.applied_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]


@router.post("/loop-back/{update_id}/apply")
def post_apply(
    update_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    upd = db.query(GtmLoopUpdate).filter(GtmLoopUpdate.id == update_id).first()
    if not upd:
        raise HTTPException(404, "Update not found")
    own_strategy(db, upd.strategy_id, user)
    return apply_loop_back(db, update_id)
