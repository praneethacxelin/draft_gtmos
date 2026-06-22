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
    type: str = "email",  # 'email' or 'phone'
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Reveal a contact's email or phone via Apollo API.

    This represents Step 2 of the 2-step enrichment flow, consuming
    an Apollo credit on demand rather than automatically for every lead.
    """
    from app.services import clients, settings_service

    c = own_contact(db, contact_id, user)
    a = db.query(Account).filter(Account.id == c.account_id).first()

    # Skip if we already have the requested data
    if type == "email" and c.email and c.email not in ("(not revealed)", "Not found"):
        return _serialize(c, a)
    if type == "phone" and c.phone and c.phone not in ("Not found", "Maybe: please request direct dial via people/bulk_match"):
        return _serialize(c, a)

    apollo_key = settings_service.get_key(db, user.id, "apollo")
    if not apollo_key:
        raise HTTPException(400, "Apollo API key not configured")

    company_name = a.company_name if a else None
    domain = a.domain if a else None

    # Call Apollo to match the person and reveal email/phone
    match_result = clients.apollo_match_person(
        apollo_key,
        name=c.full_name,
        org_name=company_name,
        domain=domain,
        linkedin_url=c.linkedin_url,
        reveal_phone=(type == "phone"),
        _strategy_id=c.strategy_id,
    )

    if not match_result:
        raise HTTPException(404, "Contact not found in Apollo or reveal failed")

    org = match_result.get("organization") or {}
    if a and org:
        domain = clients.apollo_org_domain(org)
        if domain and not a.domain:
            a.domain = domain
        if org.get("industry") and not a.industry:
            a.industry = org.get("industry")
        if org.get("estimated_num_employees") and not a.employee_count:
            a.employee_count = org.get("estimated_num_employees")
        if org.get("organization_revenue_printed") and not a.revenue_range:
            a.revenue_range = org.get("organization_revenue_printed")
        if org.get("technologies") and not a.tech_stack_json:
            a.tech_stack_json = org.get("technologies")

    if type == "email":
        new_email = match_result.get("email")
        if new_email:
            before_email = c.email
            c.email = new_email
            c.is_demo = False
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
            before_email = c.email
            c.email = "Not found"
            c.is_demo = False
            db.commit()
            db.refresh(c)
            audit_service.log_change(
                event_type="contact_reveal",
                entity_type="contact",
                entity_id=c.id,
                strategy_id=c.strategy_id,
                change_field="email",
                change_before=before_email,
                change_after="Not found",
                actor="user",
                summary=f"Attempted to reveal email for {c.full_name} but Apollo had no email",
            )
    else:
        # Reveal phone
        phones = match_result.get("phone_numbers") or []
        new_phone = phones[0].get("raw_number") if phones else None
        if new_phone:
            before_phone = c.phone
            c.phone = new_phone
            c.is_demo = False
            db.commit()
            db.refresh(c)
            audit_service.log_change(
                event_type="contact_reveal",
                entity_type="contact",
                entity_id=c.id,
                strategy_id=c.strategy_id,
                change_field="phone",
                change_before=before_phone,
                change_after=new_phone,
                actor="user",
                summary=f"Revealed phone for {c.full_name}",
            )
        else:
            before_phone = c.phone
            c.phone = "Not found"
            c.is_demo = False
            db.commit()
            db.refresh(c)
            audit_service.log_change(
                event_type="contact_reveal",
                entity_type="contact",
                entity_id=c.id,
                strategy_id=c.strategy_id,
                change_field="phone",
                change_before=before_phone,
                change_after="Not found",
                actor="user",
                summary=f"Attempted to reveal phone for {c.full_name} but Apollo had no phone",
            )

    return _serialize(c, a)


@router.post("/{contact_id}/verify")
def verify_contact_email(
    contact_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    import httpx
    from app.services import clients, settings_service
    c = own_contact(db, contact_id, user)
    a = db.query(Account).filter(Account.id == c.account_id).first()

    if not c.email or c.email == "(not revealed)" or c.email == "Not found":
        raise HTTPException(400, "Contact has no valid email to verify")

    instantly_key = settings_service.get_key(db, user.id, "instantly")
    if not instantly_key:
        raise HTTPException(400, "Instantly API key not configured")

    try:
        status = clients.instantly_verify_email(
            instantly_key,
            email=c.email,
            _strategy_id=c.strategy_id,
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 402:
            raise HTTPException(402, "Instantly: Workspace does not have an active paid plan for email verification.")
        raise HTTPException(400, f"Instantly API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(400, f"Verification failed: {str(e)}")
    if status:
        c.email_verified = status
        db.commit()
        db.refresh(c)
    
    return _serialize(c, a)


class BulkVerifyRequest(BaseModel):
    contact_ids: list[str]


@router.post("/verify-bulk")
def verify_bulk_emails(
    body: BulkVerifyRequest,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    import httpx
    from app.services import clients, settings_service
    instantly_key = settings_service.get_key(db, user.id, "instantly")
    if not instantly_key:
        raise HTTPException(400, "Instantly API key not configured")

    verified_count = 0
    invalid_count = 0
    catch_all_count = 0

    for cid in body.contact_ids:
        c = own_contact(db, cid, user)
        if not c.email or c.email == "(not revealed)" or c.email == "Not found":
            continue
            
        try:
            status = clients.instantly_verify_email(
                instantly_key,
                email=c.email,
                _strategy_id=c.strategy_id,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 402:
                raise HTTPException(402, "Instantly: Workspace does not have an active paid plan for email verification.")
            raise HTTPException(400, f"Instantly API error: {e.response.text}")
        except Exception as e:
            raise HTTPException(400, f"Verification failed: {str(e)}")
        if status:
            c.email_verified = status
            db.commit()
            if status == "valid":
                verified_count += 1
            elif status == "invalid":
                invalid_count += 1
            elif status == "catch_all":
                catch_all_count += 1

    return {
        "verified": verified_count,
        "invalid": invalid_count,
        "catch_all": catch_all_count,
        "total": len(body.contact_ids)
    }


def _serialize(c: Contact, a: Account | None) -> dict:
    return {
        "id": c.id,
        "full_name": c.full_name,
        "title": c.title,
        "email": c.email,
        "email_verified": c.email_verified,
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
        "source": c.source or "discovery",
        "source_ref": c.source_ref,
        "account_id": c.account_id,
        "company_name": a.company_name if a else None,
        "industry": a.industry if a else None,
        "domain": a.domain if a else None,
    }
