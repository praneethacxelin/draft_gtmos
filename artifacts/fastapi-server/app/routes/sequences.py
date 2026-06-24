import json
from fastapi import APIRouter, Depends, HTTPException
from app.services import audit_service, settings_service, clients
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from app.db import get_session, SessionLocal, Sequence, SequenceStep, OutreachEvent, User
from app.auth import current_user
from app.scoping import own_contact, own_sequence
from app.agents.s3_outreach import generate_sequence, deliverability_check, launch_sequence

router = APIRouter(prefix="/sequences", tags=["sequences"])


@router.post("/generate/{contact_id}")
async def generate(
    contact_id: str,
    step_count: int = 4,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    own_contact(db, contact_id, user)
    return await generate_sequence(db, contact_id, step_count=step_count)


@router.get("/by-contact/{contact_id}")
def by_contact(
    contact_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict | None:
    own_contact(db, contact_id, user)
    seq = db.query(Sequence).filter(Sequence.contact_id == contact_id).first()
    if not seq:
        return None
    
    from datetime import datetime
    from app.db import InstantlyCampaign
    
    # Sync and fetch all campaigns for this sequence
    camps = db.query(InstantlyCampaign).filter(InstantlyCampaign.sequence_id == seq.id).all()
    instantly_key = settings_service.get_key(db, user.id, "instantly")
    
    if instantly_key and camps:
        try:
            # Sync statuses
            instantly_camps = clients.instantly_get_campaigns(instantly_key) or []
            instantly_camps_map = {c["id"]: c for c in instantly_camps if "id" in c}
            
            # Prune deleted campaigns (if not returned by Instantly campaigns list)
            camps_to_delete = [c for c in camps if c.instantly_campaign_id not in instantly_camps_map]
            if camps_to_delete:
                for c in camps_to_delete:
                    db.delete(c)
                db.commit()
                # Re-fetch camps
                camps = db.query(InstantlyCampaign).filter(InstantlyCampaign.sequence_id == seq.id).all()
            
            # Sync analytics
            analytics_res = clients.instantly_get_analytics(instantly_key)
            analytics_list = []
            if isinstance(analytics_res, dict):
                analytics_list = analytics_res.get("data") or []
            elif isinstance(analytics_res, list):
                analytics_list = analytics_res
            analytics_map = {a["campaign_id"]: a for a in analytics_list if "campaign_id" in a}
            
            for c in camps:
                # Update status
                camp_data = instantly_camps_map.get(c.instantly_campaign_id)
                if camp_data:
                    instantly_status = camp_data.get("status")
                    # In Instantly v2: 1 = active, 2 = paused, 3 = complete, 0 = paused
                    if instantly_status == 1:
                        status_str = "active"
                    elif instantly_status == 2:
                        status_str = "paused"
                    elif instantly_status == 3:
                        status_str = "complete"
                    elif instantly_status == 0:
                        status_str = "paused"
                    else:
                        status_str = "active"
                    c.status = status_str
                    if seq.instantly_campaign_id == c.instantly_campaign_id:
                        seq.status = status_str
                
                # Update analytics
                anal = analytics_map.get(c.instantly_campaign_id)
                email_list = camp_data.get("email_list") if camp_data else []
                timestamp_created = camp_data.get("timestamp_created") if camp_data else None
                
                if anal or email_list or timestamp_created:
                    sent = anal.get("emails_sent_count", 0) if anal else 0
                    opened = anal.get("open_count", 0) if anal else 0
                    clicked = anal.get("link_click_count", 0) if anal else 0
                    replied = anal.get("reply_count", 0) if anal else 0
                    
                    open_rate = round(opened / sent * 100, 1) if sent else 0.0
                    click_rate = round(clicked / sent * 100, 1) if sent else 0.0
                    reply_rate = round(replied / sent * 100, 1) if sent else 0.0
                    
                    c.analytics_json = {
                        "sent": sent,
                        "opened": opened,
                        "clicked": clicked,
                        "replied": replied,
                        "bounced": anal.get("bounced_count", 0) if anal else 0,
                        "opportunities": anal.get("total_opportunities", 0) if anal else 0,
                        "opportunity_value": anal.get("total_opportunity_value", 0) if anal else 0,
                        "leads_count": anal.get("leads_count", 0) if anal else 0,
                        "contacted_count": anal.get("contacted_count", 0) if anal else 0,
                        "open_rate": open_rate,
                        "click_rate": click_rate,
                        "reply_rate": reply_rate,
                        "campaign_status": anal.get("campaign_status") if anal else None,
                        "email_list": email_list or [],
                        "timestamp_created": timestamp_created,
                    }
                c.synced_at = datetime.utcnow()
            db.commit()
        except Exception:
            pass
            
    # Mock campaign fallback for simulated sequence
    if not camps and seq.status == "simulated":
        mock_camp = InstantlyCampaign(
            sequence_id=seq.id,
            instantly_campaign_id="sim-campaign-123",
            status="active",
            analytics_json={
                "sent": 120,
                "opened": 60,
                "clicked": 24,
                "replied": 12,
                "opportunities": 4,
                "opportunity_value": 4000,
                "open_rate": 50.0,
                "click_rate": 20.0,
                "reply_rate": 10.0,
                "email_list": ["sender@company.com"],
                "timestamp_created": datetime.utcnow().isoformat() + "Z"
            }
        )
        db.add(mock_camp)
        db.commit()
        camps = [mock_camp]

    def normalize_campaign_analytics(anal: dict | None) -> dict:
        if not anal:
            return {
                "sent": 0, "opened": 0, "clicked": 0, "replied": 0, "bounced": 0,
                "opportunities": 0, "opportunity_value": 0, "open_rate": 0.0, "click_rate": 0.0, "reply_rate": 0.0,
                "email_list": [], "timestamp_created": None
            }
        
        sent = anal.get("sent")
        if sent is None:
            sent = anal.get("emails_sent_count", 0)
        opened = anal.get("opened")
        if opened is None:
            opened = anal.get("open_count", 0)
        clicked = anal.get("clicked")
        if clicked is None:
            clicked = anal.get("link_click_count", 0)
        replied = anal.get("replied")
        if replied is None:
            replied = anal.get("reply_count", 0)
            
        bounced = anal.get("bounced")
        if bounced is None:
            bounced = anal.get("bounced_count", 0)
            
        opportunities = anal.get("opportunities")
        if opportunities is None:
            opportunities = anal.get("total_opportunities", 0)
            
        opp_val = anal.get("opportunity_value")
        if opp_val is None:
            opp_val = anal.get("total_opportunity_value", 0)
            
        open_rate = anal.get("open_rate")
        if open_rate is None:
            open_rate = round(opened / sent * 100, 1) if sent else 0.0
            
        click_rate = anal.get("click_rate")
        if click_rate is None:
            click_rate = round(clicked / sent * 100, 1) if sent else 0.0
            
        reply_rate = anal.get("reply_rate")
        if reply_rate is None:
            reply_rate = round(replied / sent * 100, 1) if sent else 0.0
            
        return {
            "sent": sent,
            "opened": opened,
            "clicked": clicked,
            "replied": replied,
            "bounced": bounced,
            "opportunities": opportunities,
            "opportunity_value": opp_val,
            "open_rate": open_rate,
            "click_rate": click_rate,
            "reply_rate": reply_rate,
            "leads_count": anal.get("leads_count", 0),
            "contacted_count": anal.get("contacted_count", 0),
            "campaign_status": anal.get("campaign_status"),
            "email_list": anal.get("email_list") or [],
            "timestamp_created": anal.get("timestamp_created")
        }

    # Re-fetch camps to get latest
    camps = db.query(InstantlyCampaign).filter(InstantlyCampaign.sequence_id == seq.id).all()
    campaigns_response = []
    for c in camps:
        campaigns_response.append({
            "id": c.id,
            "instantly_campaign_id": c.instantly_campaign_id,
            "status": c.status,
            "analytics": normalize_campaign_analytics(c.analytics_json),
            "synced_at": c.synced_at.isoformat() if c.synced_at else None
        })

    # Sort campaigns newest-to-oldest by timestamp_created, with fallbacks to synced_at and id
    campaigns_response.sort(
        key=lambda x: (
            x["analytics"].get("timestamp_created") or "",
            x.get("synced_at") or "",
            x.get("id") or ""
        ),
        reverse=True
    )


    steps = db.query(SequenceStep).filter(SequenceStep.sequence_id == seq.id).order_by(SequenceStep.step_number).all()
    raw_plan = seq.channel_plan_json
    if isinstance(raw_plan, dict) and "plan" in raw_plan:
        channel_plan = raw_plan.get("plan")
        provenance = raw_plan.get("_provenance")
    else:
        channel_plan = raw_plan
        provenance = None
        
    return {
        "id": seq.id,
        "status": seq.status,
        "channel_plan": channel_plan,
        "provenance": provenance,
        "deliverability_score": seq.deliverability_score,
        "deliverability_report": seq.deliverability_report_json,
        "instantly_campaign_id": seq.instantly_campaign_id,
        "campaigns": campaigns_response,
        "steps": [{
            "id": s.id,
            "step_number": s.step_number,
            "channel": s.channel,
            "subject": s.subject,
            "body": s.body,
            "wait_days": s.wait_days,
            "send_at": s.send_at.isoformat() if s.send_at else None,
            "sent_at": s.sent_at.isoformat() if s.sent_at else None,
            "status": s.status,
        } for s in steps],
    }


@router.post("/{sequence_id}/deliverability-check")
def check(
    sequence_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    own_sequence(db, sequence_id, user)
    return deliverability_check(db, sequence_id)


class LaunchBody(BaseModel):
    test_email: Optional[str] = None
    schedule: Optional[dict] = None
    is_test: bool = False


@router.post("/{sequence_id}/launch")
def launch(
    sequence_id: str,
    payload: LaunchBody | None = None,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """Stream launch progress (Instantly push or simulated send)."""
    own_sequence(db, sequence_id, user)
    test_email = payload.test_email if payload else None
    schedule = payload.schedule if payload else None
    is_test = payload.is_test if payload else False
    from app.services.rate_limit import RateLimitExceeded

    async def gen():
        yield {"event": "stage_start", "data": json.dumps({"stage": "launch"})}
        db2 = SessionLocal()
        try:
            result = launch_sequence(db2, sequence_id, test_email=test_email, schedule=schedule, is_test=is_test)
            yield {"event": "stage_complete", "data": json.dumps({"stage": "launch", "result": result})}
            yield {"event": "complete", "data": json.dumps({"stage": "launch"})}
        except RateLimitExceeded as rle:
            yield {"event": "error", "data": json.dumps({
                "status": 429,
                "integration": rle.name,
                "retry_after_seconds": int(rle.retry_after),
                "message": (
                    f"Free-tier rate limit reached for {rle.name}. "
                    f"Retry in ~{int(rle.retry_after)}s."
                ),
            })}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"message": str(e)})}
        finally:
            db2.close()
    return EventSourceResponse(gen())


class StepPatch(BaseModel):
    subject: str | None = None
    body: str | None = None
    channel: str | None = None
    wait_days: int | None = None
    send_at: str | None = None  # ISO 8601 string from frontend datetime-local input


@router.patch("/steps/{step_id}")
def patch_step(
    step_id: str,
    body: StepPatch,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    from datetime import datetime as _dt
    step = db.query(SequenceStep).filter(SequenceStep.id == step_id).first()
    if not step:
        raise HTTPException(404, "Step not found")
    seq = db.query(Sequence).filter(Sequence.id == step.sequence_id).first()
    if not seq:
        raise HTTPException(404, "Sequence not found")
    own_contact(db, seq.contact_id, user)
    changes = body.model_dump(exclude_unset=True)
    before = {k: getattr(step, k) for k in changes}
    for field, val in changes.items():
        if field == "send_at":
            # Frontend sends a local ISO string; parse to datetime for the DB column
            if val:
                try:
                    parsed = _dt.fromisoformat(val)
                    setattr(step, "send_at", parsed)
                except ValueError:
                    pass  # ignore malformed value; keep existing
            else:
                setattr(step, "send_at", None)
        else:
            if field in ("subject", "body"):
                from app.agents.s3_outreach import _normalize_merge_tags
                val = _normalize_merge_tags(val)
            setattr(step, field, val)
    db.commit()
    db.refresh(step)
    for field, old_val in before.items():
        audit_service.log_change(
            event_type="step_change",
            entity_type="step",
            entity_id=step.id,
            strategy_id=seq.strategy_id,
            change_field=field,
            change_before=old_val,
            change_after=getattr(step, field),
            actor="user",
            summary=f"Sequence step {step.step_number} ({step.channel}) · {field} updated",
        )
    return {
        "id": step.id,
        "step_number": step.step_number,
        "channel": step.channel,
        "subject": step.subject,
        "body": step.body,
        "wait_days": step.wait_days,
        "send_at": step.send_at.isoformat() if step.send_at else None,
        "sent_at": step.sent_at.isoformat() if step.sent_at else None,
        "status": step.status,
    }


@router.get("/{sequence_id}/engagement")
def engagement(
    sequence_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    own_sequence(db, sequence_id, user)
    rows = db.query(OutreachEvent).filter(OutreachEvent.sequence_id == sequence_id).order_by(OutreachEvent.occurred_at.desc()).all()
    return [{
        "event_type": r.event_type,
        "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
    } for r in rows]


class ConnectAccountBody(BaseModel):
    email: str
    first_name: str
    last_name: str
    provider_code: int = 2  # default 2 (Gmail)
    app_password: str
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None


class ToggleWarmupBody(BaseModel):
    email: str
    enable: bool


@router.get("/sending-accounts")
def get_sending_accounts(
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    instantly_key = settings_service.get_key(db, user.id, "instantly")
    if not instantly_key:
        return []
    
    accounts = clients.instantly_get_accounts(instantly_key)
    if not accounts:
        return []
    
    emails = [a["email"] for a in accounts if "email" in a]
    analytics = {}
    if emails:
        try:
            analytics_res = clients.instantly_get_warmup_analytics(instantly_key, emails)
            if analytics_res:
                analytics = analytics_res.get("aggregate_data", {})
        except Exception as e:
            pass  # Fall back to empty analytics if it fails

    result = []
    for a in accounts:
        email = a.get("email")
        email_stats = analytics.get(email, {})
        result.append({
            "email": email,
            "first_name": a.get("first_name", ""),
            "last_name": a.get("last_name", ""),
            "provider_code": a.get("provider_code"),
            "status": a.get("status"),
            "warmup_status": a.get("warmup_status", 0),
            "health_score": email_stats.get("health_score") or a.get("stat_warmup_score") or 100,
            "sent_count": email_stats.get("sent", 0),
            "received_count": email_stats.get("received", 0),
            "landed_inbox": email_stats.get("landed_inbox", 0),
        })
    return result


@router.post("/sending-accounts/connect")
def connect_sending_account(
    body: ConnectAccountBody,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    instantly_key = settings_service.get_key(db, user.id, "instantly")
    if not instantly_key:
        raise HTTPException(status_code=400, detail="Instantly integration is not enabled or key is missing.")
    
    imap_host = body.imap_host
    imap_port = body.imap_port
    smtp_host = body.smtp_host
    smtp_port = body.smtp_port

    if body.provider_code == 2:  # Gmail
        if not imap_host: imap_host = "imap.gmail.com"
        if not imap_port: imap_port = 993
        if not smtp_host: smtp_host = "smtp.gmail.com"
        if not smtp_port: smtp_port = 465
    elif body.provider_code == 3:  # Outlook
        if not imap_host: imap_host = "outlook.office365.com"
        if not imap_port: imap_port = 993
        if not smtp_host: smtp_host = "smtp.office365.com"
        if not smtp_port: smtp_port = 587

    payload = {
        "email": body.email,
        "first_name": body.first_name,
        "last_name": body.last_name,
        "provider_code": body.provider_code,
        "imap_username": body.email,
        "imap_password": body.app_password,
        "imap_host": imap_host,
        "imap_port": imap_port,
        "smtp_username": body.email,
        "smtp_password": body.app_password,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
    }

    try:
        res = clients.instantly_create_account(instantly_key, payload)
        return {"status": "success", "account": res}
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to connect account: {str(exc)}")


@router.post("/sending-accounts/warmup/toggle")
def toggle_warmup(
    body: ToggleWarmupBody,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    instantly_key = settings_service.get_key(db, user.id, "instantly")
    if not instantly_key:
        raise HTTPException(status_code=400, detail="Instantly integration is not enabled or key is missing.")
    
    try:
        res = clients.instantly_toggle_warmup(instantly_key, [body.email], enable=body.enable)
        return {"status": "success", "job": res}
    except ValueError as val_err:
        raise HTTPException(status_code=409, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to toggle warmup: {str(exc)}")


@router.delete("/sending-accounts/{email}")
def delete_sending_account(
    email: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    instantly_key = settings_service.get_key(db, user.id, "instantly")
    if not instantly_key:
        raise HTTPException(status_code=400, detail="Instantly integration is not enabled or key is missing.")
    
    import httpx
    try:
        url = f"https://api.instantly.ai/api/v2/accounts/{email}"
        headers = {"Authorization": f"Bearer {instantly_key}"}
        r = httpx.delete(url, headers=headers, timeout=10.0)
        r.raise_for_status()
        return {"status": "success", "message": f"Account {email} disconnected."}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to delete account: {str(exc)}")


@router.get("/by-contact/{contact_id}/replies")
def get_contact_replies(
    contact_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    own_contact(db, contact_id, user)
    from app.db import Contact
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact or not contact.email:
        return []
    
    instantly_key = settings_service.get_key(db, user.id, "instantly")
    if not instantly_key:
        # Fallback simulated data for simulated sequence
        from datetime import datetime, timedelta
        seq = db.query(Sequence).filter(Sequence.contact_id == contact_id).first()
        if seq and seq.status == "simulated":
            return [
                {
                    "id": "sim-reply-1",
                    "subject": "Re: Connecting on innovative support strategies",
                    "body": "Hi there,\n\nThanks for reaching out. Yes, we are indeed looking at optimizing our operations. Could you share some pricing details first?\n\nBest,\nDavid",
                    "from_address_name": contact.full_name,
                    "from_address_email": contact.email,
                    "to_address_email": "sender@company.com",
                    "ue_type": 2, # reply/received
                    "timestamp_created": (datetime.utcnow() - timedelta(days=2)).isoformat() + "Z",
                },
                {
                    "id": "sim-reply-2",
                    "subject": "Re: Connecting on innovative support strategies",
                    "body": "Hi David,\n\nAbsolutely, I'd be happy to. Our starter plans begin at $49/agent/month, but I'd love to share more customized options based on your ticket volume. Are you free for a brief call tomorrow?\n\nBest,\nSender",
                    "from_address_name": "Sender",
                    "from_address_email": "sender@company.com",
                    "to_address_email": contact.email,
                    "ue_type": 1, # sent
                    "timestamp_created": (datetime.utcnow() - timedelta(days=2, hours=2)).isoformat() + "Z",
                }
            ]
        return []

    import httpx
    try:
        url = f"https://api.instantly.ai/api/v2/emails?lead={contact.email}"
        headers = {"Authorization": f"Bearer {instantly_key}"}
        r = httpx.get(url, headers=headers, timeout=10.0)
        r.raise_for_status()
        items = r.json().get("items", [])
        
        replies = []
        for item in items:
            replies.append({
                "id": item.get("id"),
                "subject": item.get("subject"),
                "body": item.get("body", {}).get("text") or item.get("body", {}).get("html") or "",
                "from_address_name": item.get("from_address_name"),
                "from_address_email": item.get("from_address_email"),
                "to_address_email": item.get("to_address_email"),
                "ue_type": item.get("ue_type"), # 1=sent, 2=received/reply
                "timestamp_created": item.get("timestamp_created"),
            })
        return replies
    except Exception as e:
        import logging
        logging.getLogger("gtm.sequences").warning("Failed to fetch Instantly emails for contact %s: %s", contact.email, e)
        return []


@router.post("/campaigns/{campaign_id}/pause")
def pause_campaign(
    campaign_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    from app.db import InstantlyCampaign
    instantly_key = settings_service.get_key(db, user.id, "instantly")
    
    db_camp = db.query(InstantlyCampaign).filter(InstantlyCampaign.instantly_campaign_id == campaign_id).first()
    if not db_camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    seq = db.query(Sequence).filter(Sequence.id == db_camp.sequence_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    own_contact(db, seq.contact_id, user)
    
    if instantly_key:
        import httpx
        try:
            url = f"https://api.instantly.ai/api/v2/campaigns/{campaign_id}/pause"
            headers = {"Authorization": f"Bearer {instantly_key}", "Content-Type": "application/json"}
            r = httpx.post(url, json={}, headers=headers, timeout=10.0)
            r.raise_for_status()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to pause campaign in Instantly: {str(e)}")
            
    db_camp.status = "paused"
    seq.status = "paused"
    db.commit()
    return {"status": "paused"}


@router.post("/campaigns/{campaign_id}/resume")
def resume_campaign(
    campaign_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    from app.db import InstantlyCampaign
    instantly_key = settings_service.get_key(db, user.id, "instantly")
    
    db_camp = db.query(InstantlyCampaign).filter(InstantlyCampaign.instantly_campaign_id == campaign_id).first()
    if not db_camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    seq = db.query(Sequence).filter(Sequence.id == db_camp.sequence_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    own_contact(db, seq.contact_id, user)
    
    if instantly_key:
        import httpx
        try:
            url = f"https://api.instantly.ai/api/v2/campaigns/{campaign_id}/activate"
            headers = {"Authorization": f"Bearer {instantly_key}", "Content-Type": "application/json"}
            r = httpx.post(url, json={}, headers=headers, timeout=10.0)
            r.raise_for_status()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to activate campaign in Instantly: {str(e)}")
            
    db_camp.status = "active"
    seq.status = "active"
    db.commit()
    return {"status": "active"}


@router.get("/campaigns/{campaign_id}/leads")
def get_campaign_leads(
    campaign_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    instantly_key = settings_service.get_key(db, user.id, "instantly")
    if not instantly_key or campaign_id.startswith("sim-"):
        # Return mock leads for offline/simulated experience
        return [
            {
                "email": "emily@techwave.com",
                "first_name": "Emily",
                "last_name": "Smith",
                "company_name": "TechWave Solutions",
                "status": 3, # Reply received
            },
            {
                "email": "david@nexus.com",
                "first_name": "David",
                "last_name": "Miller",
                "company_name": "Nexus Corp",
                "status": 6, # Interested
            },
            {
                "email": "sarah@apex.com",
                "first_name": "Sarah",
                "last_name": "Jones",
                "company_name": "Apex Ltd",
                "status": 4, # Completed
            },
            {
                "email": "robert@vertex.com",
                "first_name": "Robert",
                "last_name": "Taylor",
                "company_name": "Vertex Inc",
                "status": 5, # Unsubscribed
            }
        ]
    
    leads = clients.instantly_get_leads(instantly_key, campaign_id)
    if not leads:
        return []
    
    return [{
        "email": lead.get("email"),
        "first_name": lead.get("first_name"),
        "last_name": lead.get("last_name"),
        "company_name": lead.get("company_name"),
        "status": lead.get("status"),
    } for lead in leads]


@router.get("/campaigns/leads/replies")
def get_lead_replies(
    email: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    instantly_key = settings_service.get_key(db, user.id, "instantly")
    if not instantly_key or email.startswith("emily@") or email.startswith("david@") or email.startswith("sim-"):
        # Return mock replies
        if "emily" in email.lower():
            return [
                {
                    "id": "sim-reply-1",
                    "subject": "Re: Optimizing Support Operations",
                    "body": "Hi there,\n\nI read your email and yes, we are trying to scale our support team. Can we schedule a quick call next Tuesday at 10 AM?\n\nThanks,\nEmily",
                    "from_address_name": "Emily Smith",
                    "from_address_email": "emily@techwave.com",
                    "to_address_email": "sender@company.com",
                    "ue_type": 2, # reply/received
                    "timestamp_created": "2026-06-24T10:00:00Z",
                }
            ]
        elif "david" in email.lower():
            return [
                {
                    "id": "sim-reply-2",
                    "subject": "Re: Automated Ticketing Solutions",
                    "body": "Thank you for reaching out. What are the integration options for Jira?\n\nBest,\nDavid",
                    "from_address_name": "David Miller",
                    "from_address_email": "david@nexus.com",
                    "to_address_email": "sender@company.com",
                    "ue_type": 2,
                    "timestamp_created": "2026-06-23T15:30:00Z",
                }
            ]
        return []

    import httpx
    try:
        url = f"https://api.instantly.ai/api/v2/emails?lead={email}"
        headers = {"Authorization": f"Bearer {instantly_key}"}
        r = httpx.get(url, headers=headers, timeout=10.0)
        r.raise_for_status()
        items = r.json().get("items", [])
        
        replies = []
        for item in items:
            replies.append({
                "id": item.get("id"),
                "subject": item.get("subject"),
                "body": item.get("body", {}).get("text") or item.get("body", {}).get("html") or "",
                "from_address_name": item.get("from_address_name"),
                "from_address_email": item.get("from_address_email"),
                "to_address_email": item.get("to_address_email"),
                "ue_type": item.get("ue_type"), # 1=sent, 2=received/reply
                "timestamp_created": item.get("timestamp_created"),
            })
        return replies
    except Exception as e:
        import logging
        logging.getLogger("gtm.sequences").warning("Failed to fetch Instantly emails for lead %s: %s", email, e)
        return []


