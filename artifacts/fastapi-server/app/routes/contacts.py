from fastapi import APIRouter, Depends, HTTPException
from app.services import audit_service
from pydantic import BaseModel
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
        .filter(Contact.strategy_id == strategy_id)
    )
    if tier:
        q = q.filter(Contact.tier == tier)
    contacts = q.order_by(Contact.total_score.desc()).all()
    accounts = {
        a.id: a
        for a in db.query(Account)
        .filter(Account.strategy_id == strategy_id)
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


class ContactPatch(BaseModel):
    full_name: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    persona_type: str | None = None
    icp_fit_score: float | None = None
    seniority: str | None = None


@router.patch("/{contact_id}")
def patch_contact(
    contact_id: str,
    body: ContactPatch,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    c = own_contact(db, contact_id, user)
    changes = body.model_dump(exclude_unset=True)
    before = {k: getattr(c, k) for k in changes}
    for field, val in changes.items():
        setattr(c, field, val)
    db.commit()
    db.refresh(c)
    a = db.query(Account).filter(Account.id == c.account_id).first()
    for field, old_val in before.items():
        audit_service.log_change(
            event_type="contact_change",
            entity_type="contact",
            entity_id=c.id,
            strategy_id=c.strategy_id,
            change_field=field,
            change_before=old_val,
            change_after=getattr(c, field),
            actor="user",
            summary=f"Contact \"{c.full_name}\" · {field} updated",
        )
    return _serialize(c, a)


@router.post("/{contact_id}/reveal")
def reveal_contact(
    contact_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Reveal a contact's email address via Apollo API.

    This represents Step 2 of the 2-step enrichment flow, consuming
    an Apollo credit on demand rather than automatically for every lead.
    """
    from app.services import clients, settings_service

    c = own_contact(db, contact_id, user)
    a = db.query(Account).filter(Account.id == c.account_id).first()

    if c.email and c.email != "(not revealed)":
        return _serialize(c, a)

    apollo_key = settings_service.get_key(db, user.id, "apollo")
    if not apollo_key:
        raise HTTPException(400, "Apollo API key not configured")

    company_name = a.company_name if a else None
    domain = a.domain if a else None

    # Call Apollo to match the person and reveal email
    match_result = clients.apollo_match_person(
        apollo_key,
        name=c.full_name,
        org_name=company_name,
        domain=domain,
        reveal_phone=False,
        _strategy_id=c.strategy_id,
    )

    if not match_result:
        raise HTTPException(404, "Contact not found in Apollo or reveal failed")

    new_email = match_result.get("email")
    if new_email:
        before_email = c.email
        c.email = new_email
        c.is_demo = False  # If it was a demo contact, it's now real
        db.commit()
        db.refresh(c)
        audit_service.log_change(
            event_type="contact_reveal",
            entity_type="contact",
            entity_id=c.id,
            strategy_id=c.strategy_id,
            change_field="email",
            change_before=before_email,
            change_after=new_email,
            actor="user",
            summary=f"Revealed email for {c.full_name}",
        )
    else:
        # Update email to indicate it was tried but not found
        c.email = "Not found"
        db.commit()

    return _serialize(c, a)


def _serialize(c: Contact, a: Account | None) -> dict:
    return {
        "id": c.id,
        "full_name": c.full_name,
        "title": c.title,
        "email": c.email,
        "phone": c.phone,
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
