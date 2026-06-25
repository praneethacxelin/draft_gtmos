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

    def _real_email(value: str | None) -> str | None:
        """Reject Apollo's locked-email placeholders so we never store a fake address."""
        if not value:
            return None
        low = value.strip().lower()
        if not low or "@" not in low:
            return None
        if "not_unlocked" in low or low.startswith("email_not_unlocked") or low.split("@")[-1] == "domain.com":
            return None
        return value.strip()

    # --- Fast path: reveal by the Apollo person id we captured at discovery. ---
    # Matching by id via /people/bulk_match is far more reliable than re-matching
    # by name, and returns the work email when the account's plan includes it.
    if type == "email" and c.source_ref and str(c.source_ref).strip() and not c.is_demo:
        revealed = clients.apollo_bulk_reveal(
            apollo_key,
            [str(c.source_ref).strip()],
            reveal_personal=False,
            _strategy_id=c.strategy_id,
            _strategy_name=None,
        )
        person = revealed.get(str(c.source_ref).strip())
        if person:
            org = person.get("organization") or {}
            if a and org:
                d = clients.apollo_org_domain(org)
                if d and not a.domain:
                    a.domain = d
                if org.get("industry") and not a.industry:
                    a.industry = org.get("industry")
                if org.get("estimated_num_employees") and not a.employee_count:
                    a.employee_count = org.get("estimated_num_employees")
            new_email = _real_email(person.get("email"))
            before_email = c.email
            c.email = new_email or "Not found"
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
                change_after=c.email,
                actor="user",
                summary=(
                    f"Revealed email for {c.full_name} via Apollo id"
                    if new_email
                    else f"Apollo matched {c.full_name} by id but had no unlocked email"
                ),
            )
            return _serialize(c, a)
        # If id-match yielded nothing, fall through to the name-based match below.

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
        new_email = _real_email(match_result.get("email"))
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
    provider: str | None = None,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    import httpx
    from app.services import clients, settings_service
    c = own_contact(db, contact_id, user)
    a = db.query(Account).filter(Account.id == c.account_id).first()

    if not c.email or c.email == "(not revealed)" or c.email == "Not found":
        raise HTTPException(400, "Contact has no valid email to verify")

    hunter_key = settings_service.get_key(db, user.id, "hunter")
    instantly_key = settings_service.get_key(db, user.id, "instantly")
    if not hunter_key and not instantly_key:
        raise HTTPException(400, "No email-verification provider configured (Hunter.io or Instantly)")

    try:
        status = _verify_one(clients, c.email, c.strategy_id, hunter_key, instantly_key, provider)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 402:
            raise HTTPException(402, "No configured verification provider has an active plan. Instantly free trials cannot verify — add a Hunter.io key in Settings → Integrations.")
        raise HTTPException(400, f"Verification API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(400, f"Verification failed: {str(e)}")
    if status:
        c.email_verified = status
        db.commit()
        db.refresh(c)
    
    return _serialize(c, a)


def _verify_one(
    clients,
    email: str,
    strategy_id: str | None,
    hunter_key: str | None,
    instantly_key: str | None,
    provider: str | None,
) -> str | None:
    """Verify a single email, honoring a preferred provider.

    ``provider="instantly"`` → use Instantly first (pre-send checks).
    ``provider="hunter"`` → use Hunter first (post-bounce re-checks).
    Otherwise default to Hunter, then Instantly. Falls back to the other
    provider when the preferred one isn't configured.
    """
    pref = (provider or "").lower()
    if pref == "instantly":
        order = [("instantly", instantly_key), ("hunter", hunter_key)]
    elif pref == "hunter":
        order = [("hunter", hunter_key), ("instantly", instantly_key)]
    else:
        order = [("hunter", hunter_key), ("instantly", instantly_key)]
    last_error: Exception | None = None
    inconclusive: str | None = None  # remember a non-definitive result (e.g. "pending")
    for name, key in order:
        if not key:
            continue
        try:
            if name == "hunter":
                result = clients.hunter_verify_email(key, email=email, _strategy_id=strategy_id)
            else:
                result = clients.instantly_verify_email(key, email=email, _strategy_id=strategy_id)
            # A definitive verdict wins immediately. Instantly often returns an
            # async "pending" — that's inconclusive, so try the next provider
            # for a real valid/invalid/catch_all before settling for pending.
            if result in ("valid", "invalid", "catch_all"):
                return result
            if result:
                inconclusive = inconclusive or result
        except Exception as e:  # noqa: BLE001 - try the next provider on any failure
            # The preferred provider may not support verification on the
            # current plan (e.g. an Instantly free trial returns HTTP 402).
            # Remember the error but keep going so a second configured
            # provider (e.g. Hunter) can still produce a result.
            last_error = e
            continue
    if inconclusive is not None:
        return inconclusive
    if last_error is not None:
        raise last_error
    return None


class BulkVerifyRequest(BaseModel):
    contact_ids: list[str]
    provider: str | None = None


@router.post("/verify-bulk")
def verify_bulk_emails(
    body: BulkVerifyRequest,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    import httpx
    from app.services import clients, settings_service
    hunter_key = settings_service.get_key(db, user.id, "hunter")
    instantly_key = settings_service.get_key(db, user.id, "instantly")
    if not hunter_key and not instantly_key:
        raise HTTPException(400, "No email-verification provider configured (Hunter.io or Instantly)")

    verified_count = 0
    invalid_count = 0
    catch_all_count = 0

    for cid in body.contact_ids:
        c = own_contact(db, cid, user)
        if not c.email or c.email == "(not revealed)" or c.email == "Not found":
            continue

        try:
            status = _verify_one(clients, c.email, c.strategy_id, hunter_key, instantly_key, body.provider)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 402:
                raise HTTPException(402, "No configured verification provider has an active plan. Instantly free trials cannot verify — add a Hunter.io key in Settings → Integrations.")
            raise HTTPException(400, f"Verification API error: {e.response.text}")
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
