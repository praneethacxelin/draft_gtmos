from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_session, Contact, Account, User
from app.auth import current_user
from app.scoping import own_strategy, own_contact

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("")
def list_contacts(
    strategy_id: str,
    tier: int | None = None,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    own_strategy(db, strategy_id, user)
    q = (
        db.query(Contact)
        .filter(Contact.strategy_id == strategy_id, Contact.user_id == user.id)
    )
    if tier:
        q = q.filter(Contact.tier == tier)
    contacts = q.order_by(Contact.total_score.desc()).all()
    accounts = {
        a.id: a
        for a in db.query(Account)
        .filter(Account.strategy_id == strategy_id, Account.user_id == user.id)
        .all()
    }
    return [_serialize(c, accounts.get(c.account_id)) for c in contacts]


@router.get("/{contact_id}")
def get_contact(
    contact_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    c = own_contact(db, contact_id, user)
    a = db.query(Account).filter(Account.id == c.account_id).first()
    return _serialize(c, a)


def _serialize(c: Contact, a: Account | None) -> dict:
    return {
        "id": c.id,
        "full_name": c.full_name,
        "title": c.title,
        "email": c.email,
        "linkedin_url": c.linkedin_url,
        "seniority": c.seniority,
        "department": c.department,
        "persona_type": c.persona_type,
        "icp_fit_score": c.icp_fit_score,
        "signal_score": c.signal_score,
        "engagement_score": c.engagement_score,
        "total_score": c.total_score,
        "tier": c.tier,
        "is_demo": c.is_demo,
        "account_id": c.account_id,
        "company_name": a.company_name if a else None,
        "industry": a.industry if a else None,
        "domain": a.domain if a else None,
    }
