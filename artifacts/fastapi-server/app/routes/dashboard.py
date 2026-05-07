from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.db import (
    get_session,
    Strategy,
    Contact,
    Sequence,
    Signal,
    Account,
    IntentScore,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(db: Session = Depends(get_session)) -> dict:
    strategies = db.query(Strategy).count()
    ready_strategies = db.query(Strategy).filter(Strategy.status == "ready").count()
    total_contacts = db.query(Contact).count()
    tier_1 = db.query(Contact).filter(Contact.tier == 1).count()
    sequences = db.query(Sequence).filter(Sequence.status.in_(["active", "simulated"])).count()
    top_intent = (
        db.query(IntentScore, Account)
        .join(Account, Account.id == IntentScore.account_id)
        .order_by(IntentScore.score.desc())
        .first()
    )
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
def activity(db: Session = Depends(get_session)) -> list[dict]:
    out = []
    for s in db.query(Signal).order_by(Signal.detected_at.desc()).limit(8).all():
        out.append({
            "type": "signal",
            "title": f"{s.signal_type.title()} signal",
            "detail": s.summary[:120],
            "at": s.detected_at.isoformat() if s.detected_at else None,
        })
    for st in db.query(Strategy).order_by(Strategy.created_at.desc()).limit(5).all():
        out.append({
            "type": "strategy",
            "title": f"Strategy: {st.product_name}",
            "detail": st.status,
            "at": st.created_at.isoformat() if st.created_at else None,
        })
    out.sort(key=lambda x: x["at"] or "", reverse=True)
    return out[:12]
