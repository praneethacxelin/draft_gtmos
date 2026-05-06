from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_session, Signal, Account

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("")
def list_signals(strategy_id: str, db: Session = Depends(get_session)) -> list[dict]:
    rows = (
        db.query(Signal)
        .filter(Signal.strategy_id == strategy_id)
        .order_by(Signal.detected_at.desc())
        .limit(100)
        .all()
    )
    accounts = {a.id: a for a in db.query(Account).filter(Account.strategy_id == strategy_id).all()}
    return [{
        "id": s.id,
        "signal_type": s.signal_type,
        "source": s.source,
        "summary": s.summary,
        "strength_score": s.strength_score,
        "detected_at": s.detected_at.isoformat() if s.detected_at else None,
        "company_name": accounts.get(s.account_id).company_name if accounts.get(s.account_id) else None,
        "is_demo": s.source == "ai_demo",
    } for s in rows]
