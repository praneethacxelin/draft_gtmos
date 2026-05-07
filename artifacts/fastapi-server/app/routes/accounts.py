from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_session, Account, Contact, Signal, IntentScore, User
from app.auth import current_user
from app.scoping import own_strategy

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("")
def list_accounts(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    own_strategy(db, strategy_id, user)
    accounts = (
        db.query(Account)
        .filter(Account.strategy_id == strategy_id, Account.user_id == user.id)
        .all()
    )
    out = []
    for a in accounts:
        signal_count = db.query(Signal).filter(Signal.account_id == a.id).count()
        contact_count = db.query(Contact).filter(Contact.account_id == a.id).count()
        intent = (
            db.query(IntentScore)
            .filter(IntentScore.account_id == a.id)
            .order_by(IntentScore.computed_at.desc())
            .first()
        )
        out.append({
            "id": a.id,
            "company_name": a.company_name,
            "domain": a.domain,
            "industry": a.industry,
            "employee_count": a.employee_count,
            "revenue_range": a.revenue_range,
            "tier": a.tier,
            "tech_stack": a.tech_stack_json,
            "signal_count": signal_count,
            "contact_count": contact_count,
            "intent_score": intent.score if intent else None,
            "intent_classification": intent.classification if intent else None,
        })
    out.sort(key=lambda x: (x["tier"] or 9, -(x["intent_score"] or 0)))
    return out


@router.get("/prioritized")
def prioritized(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    rows = list_accounts(strategy_id, db, user)
    return {
        "tier_1": [r for r in rows if r["tier"] == 1],
        "tier_2": [r for r in rows if r["tier"] == 2],
        "tier_3": [r for r in rows if r["tier"] == 3 or r["tier"] is None],
    }
