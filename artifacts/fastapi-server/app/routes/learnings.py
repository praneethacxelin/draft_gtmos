"""Centralized learnings API — durable GTM memory with semantic recall.

Two surfaces:
  * Global ``/learnings`` — list, search, create, delete learnings across all
    strategies (the "what we've learned" knowledge base).
  * Strategy-scoped capture endpoints under ``/strategies/{id}/learnings`` that
    distill insights out of analyzed experiments and persona intelligence.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_session, User
from app.auth import current_user
from app.scoping import own_strategy
from app.agents.learnings import (
    record_learning,
    list_learnings,
    search_learnings,
    delete_learning,
    capture_from_experiment_batch,
    capture_from_persona,
)

router = APIRouter(tags=["learnings"])


class LearningCreate(BaseModel):
    content: str
    category: str = "general"
    title: str | None = None
    strategy_id: str | None = None
    source: str = "manual"
    source_ref: str | None = None
    metrics: dict | None = None
    tags: list[str] | None = None
    confidence: str = "Moderate"


# --------------------------------------------------------------------------- #
# Global knowledge base
# --------------------------------------------------------------------------- #

@router.get("/learnings")
def get_learnings(
    strategy_id: str | None = Query(default=None),
    category: str | None = Query(default=None),
    source: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    # Scope to the user's own strategies if not admin and no specific filter
    effective_strategy_id = strategy_id
    user_strategy_ids = None
    if not strategy_id and not getattr(user, "is_admin", False):
        from app.db import Strategy
        user_strategy_ids = [
            r[0] for r in db.query(Strategy.id).filter(Strategy.user_id == user.id).all()
        ]
    if q:
        return search_learnings(
            db, query=q, strategy_id=effective_strategy_id, category=category, limit=limit,
            user_strategy_ids=user_strategy_ids,
        )
    return list_learnings(
        db, strategy_id=effective_strategy_id, category=category, source=source, limit=limit,
        user_strategy_ids=user_strategy_ids,
    )


@router.post("/learnings")
def create_learning(
    body: LearningCreate,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    if body.strategy_id:
        own_strategy(db, body.strategy_id, user)
    rec = record_learning(
        db,
        content=body.content,
        category=body.category,
        title=body.title,
        strategy_id=body.strategy_id,
        source=body.source,
        source_ref=body.source_ref,
        metrics=body.metrics,
        tags=body.tags,
        confidence=body.confidence,
    )
    if rec is None:
        raise HTTPException(status_code=400, detail="content is required")
    return rec


@router.delete("/learnings/{learning_id}")
def remove_learning(
    learning_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    if not delete_learning(db, learning_id):
        raise HTTPException(status_code=404, detail="Learning not found")
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Strategy-scoped auto-capture
# --------------------------------------------------------------------------- #

@router.post("/strategies/{strategy_id}/learnings/capture-experiment/{batch_id}")
def capture_experiment(
    strategy_id: str,
    batch_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    own_strategy(db, strategy_id, user)
    captured = capture_from_experiment_batch(db, batch_id)
    return {"captured": captured, "count": len(captured)}


@router.post("/strategies/{strategy_id}/learnings/capture-persona")
def capture_persona(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    own_strategy(db, strategy_id, user)
    captured = capture_from_persona(db, strategy_id)
    return {"captured": captured, "count": len(captured)}
