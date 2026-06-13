from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, nullslast
from datetime import datetime, timedelta
from typing import Optional
from app.db import (
    get_session,
    Strategy,
    Contact,
    Sequence,
    Signal,
    Account,
    IntentScore,
    User,
)
from app.auth import current_user
from app.services import settings_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    user_strategy_ids = [
        r[0] for r in db.query(Strategy.id).all()
    ]
    strategies = len(user_strategy_ids)
    ready_strategies = (
        db.query(Strategy)
        .filter(Strategy.status == "ready")
        .count()
    )
    if user_strategy_ids:
        total_contacts = (
            db.query(Contact).count()
        )
        tier_1 = (
            db.query(Contact)
            .filter(Contact.tier == 1)
            .count()
        )
        sequences = (
            db.query(Sequence)
            .filter(
                Sequence.strategy_id.in_(user_strategy_ids),
                Sequence.status.in_(["active", "simulated"]),
            )
            .count()
        )
        top_intent = (
            db.query(IntentScore, Account)
            .join(Account, Account.id == IntentScore.account_id)
            .filter(IntentScore.strategy_id.in_(user_strategy_ids))
            .order_by(IntentScore.score.desc())
            .first()
        )
    else:
        total_contacts = tier_1 = sequences = 0
        top_intent = None
    top = None
    if top_intent:
        score, acct = top_intent
        top = {"company_name": acct.company_name, "score": score.score, "classification": score.classification}
    return {
        "strategies": strategies,
        "ready_strategies": ready_strategies,
        "total_contacts": total_contacts,
        "tier_1_contacts": tier_1,
        "active_sequences": sequences,
        "top_intent_account": top,
    }


@router.get("/activity")
def activity(
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    user_strategy_ids = [
        r[0] for r in db.query(Strategy.id).all()
    ]
    out = []
    if user_strategy_ids:
        for s in (
            db.query(Signal)
            .filter(Signal.strategy_id.in_(user_strategy_ids))
            .order_by(Signal.detected_at.desc())
            .limit(8)
            .all()
        ):
            out.append({
                "type": "signal",
                "title": f"{s.signal_type.title()} signal",
                "detail": s.summary[:120],
                "at": s.detected_at.isoformat() if s.detected_at else None,
            })
    for st in (
        db.query(Strategy)
        # auth removed — show all strategies
        .order_by(Strategy.created_at.desc())
        .limit(5)
        .all()
    ):
        out.append({
            "type": "strategy",
            "title": f"Strategy: {st.product_name}",
            "detail": st.status,
            "at": st.created_at.isoformat() if st.created_at else None,
        })
    out.sort(key=lambda x: x["at"] or "", reverse=True)
    return out[:12]


@router.get("/signal-pulse")
def signal_pulse(
    strategy_id: Optional[str] = None,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Today's fresh signals + biggest rank movers for the Signal Pulse card.

    The daily summary is written by the background signal cron
    (``app/services/signal_cron.py``). If no SerpAPI key is configured we
    surface a hint instead of stale/empty data.
    """
    if strategy_id:
        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    else:
        # Most recently scanned ready strategy, else most recent ready one.
        strategy = (
            db.query(Strategy)
            .filter(Strategy.status == "ready")
            .order_by(nullslast(Strategy.last_signal_scan.desc()))
            .first()
        )

    if not strategy:
        return {
            "has_serpapi": False,
            "last_scanned": None,
            "new_signals": 0,
            "top_movers": [],
            "recent_signals": [],
            "message": "No strategies ready yet.",
        }

    has_serpapi = bool(settings_service.get_key(db, strategy.user_id, "serpapi"))
    summary = strategy.daily_signal_summary or {}

    # Most recent live signals for this strategy (last 7 days).
    since = datetime.utcnow() - timedelta(days=7)
    recent_rows = (
        db.query(Signal, Account)
        .outerjoin(Account, Account.id == Signal.account_id)
        .filter(
            Signal.strategy_id == strategy.id,
            Signal.detected_at >= since,
            Signal.source != "m3_tracking",
        )
        .order_by(Signal.detected_at.desc())
        .limit(8)
        .all()
    )
    recent_signals = [
        {
            "signal_type": s.signal_type,
            "summary": s.summary[:200] if s.summary else "",
            "company": acct.company_name if acct else None,
            "strength": s.strength_score,
            "source": s.source,
            "detected_at": s.detected_at.isoformat() if s.detected_at else None,
        }
        for s, acct in recent_rows
    ]

    message = None
    if not has_serpapi:
        message = "No live signals — add a SerpAPI key in Settings to enable the daily scan."
    elif not strategy.last_signal_scan:
        message = "First daily scan pending — run signals or wait for the next cron pass."

    return {
        "strategy_id": strategy.id,
        "strategy_name": strategy.product_name,
        "has_serpapi": has_serpapi,
        "last_scanned": (
            strategy.last_signal_scan.isoformat() if strategy.last_signal_scan else None
        ),
        "new_signals": summary.get("new_signals", 0),
        "is_demo": summary.get("is_demo", False),
        "top_movers": summary.get("top_movers", []),
        "recent_signals": recent_signals,
        "message": message,
    }
