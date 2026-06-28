from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from app.db import get_session, User, Contact, Account, Sequence, Experiment, InstantlyCampaign, OutreachEvent, Strategy
from app.auth import current_user

router = APIRouter(prefix="/crm", tags=["crm"])

@router.get("/contacts")
def list_crm_contacts(
    strategy_id: Optional[str] = Query(None),
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    # Determine allowed strategies for the user
    user_strat_ids = []
    if not getattr(user, "is_admin", False):
        user_strat_ids = [r[0] for r in db.query(Strategy.id).filter(Strategy.user_id == user.id).all()]

    # Query contacts
    q = db.query(Contact)
    if strategy_id and strategy_id != "all":
        # Make sure user owns this strategy
        if not getattr(user, "is_admin", False) and strategy_id not in user_strat_ids:
            return []
        q = q.filter(Contact.strategy_id == strategy_id)
    else:
        if not getattr(user, "is_admin", False):
            q = q.filter(Contact.strategy_id.in_(user_strat_ids))

    contacts = q.order_by(Contact.created_at.desc()).all()
    if not contacts:
        return []

    contact_ids = [c.id for c in contacts]
    
    # Query accounts
    account_ids = list({c.account_id for c in contacts if c.account_id})
    accounts = {a.id: a for a in db.query(Account).filter(Account.id.in_(account_ids)).all()}

    # Query sequences
    sequences = db.query(Sequence).filter(Sequence.contact_id.in_(contact_ids)).all()
    seq_by_contact = {}
    for s in sequences:
        # Keep the most recently active or just the first one found
        if s.contact_id not in seq_by_contact or s.status == "active":
            seq_by_contact[s.contact_id] = s
            
    # Query experiments
    exp_ids = list({s.experiment_id for s in sequences if hasattr(s, "experiment_id") and s.experiment_id})
    # Wait, Sequence doesn't have experiment_id. Experiment ID is on Contact.source_ref!
    source_refs = list({c.source_ref for c in contacts if c.source_ref})
    experiments = {e.id: e for e in db.query(Experiment).filter(Experiment.id.in_(source_refs)).all()}
    
    # Query instantly campaigns
    seq_ids = [s.id for s in sequences]
    instantly_camps = {ic.sequence_id: ic for ic in db.query(InstantlyCampaign).filter(InstantlyCampaign.sequence_id.in_(seq_ids)).all()}

    # Query outreach events
    ev_agg = (
        db.query(
            OutreachEvent.sequence_id,
            OutreachEvent.event_type,
            func.count(OutreachEvent.id).label("cnt")
        )
        .filter(OutreachEvent.sequence_id.in_(seq_ids))
        .group_by(OutreachEvent.sequence_id, OutreachEvent.event_type)
        .all()
    )
    events_by_seq = {}
    for row in ev_agg:
        sid = row.sequence_id
        if sid not in events_by_seq:
            events_by_seq[sid] = {}
        events_by_seq[sid][row.event_type] = row.cnt

    results = []
    for c in contacts:
        a = accounts.get(c.account_id)
        seq = seq_by_contact.get(c.id)
        exp = experiments.get(c.source_ref) if c.source_ref else None
        
        # Outreach stats
        sent, opened, clicked, replied, bounced = 0, 0, 0, 0, 0
        campaign_name = exp.name if exp else None
        
        if seq:
            ic = instantly_camps.get(seq.id)
            if ic and ic.analytics_json:
                # Merge stats from instantly campaign
                sent = ic.analytics_json.get("sent", 0)
                opened = ic.analytics_json.get("opened", 0)
                clicked = ic.analytics_json.get("clicked", 0)
                replied = ic.analytics_json.get("replied", 0)
                bounced = ic.analytics_json.get("bounced", 0)
                if not campaign_name:
                    campaign_name = "External Campaign"
            
            # Add DB events (if Instantly json wasn't populated or to combine)
            evs = events_by_seq.get(seq.id, {})
            # We prefer instantly analytics json, but fallback to DB events
            if sent == 0: sent = evs.get("sent", evs.get("test_sent", 0))
            if opened == 0: opened = evs.get("opened", 0)
            if clicked == 0: clicked = evs.get("clicked", 0)
            if replied == 0: replied = evs.get("replied", 0)
            if bounced == 0: bounced = evs.get("bounced", 0)
            
        results.append({
            "id": c.id,
            "full_name": c.full_name,
            "title": c.title,
            "email": c.email,
            "phone": c.phone,
            "linkedin_url": c.linkedin_url,
            "seniority": c.seniority,
            "department": c.department,
            "persona_type": c.persona_type,
            "tier": c.tier,
            "strategy_id": c.strategy_id,
            "account_name": a.company_name if a else None,
            "account_domain": a.domain if a else None,
            "account_industry": a.industry if a else None,
            "campaign_name": campaign_name,
            "sequence_status": seq.status if seq else "uncontacted",
            "sent": sent,
            "opened": opened,
            "clicked": clicked,
            "replied": replied,
            "bounced": bounced,
        })
        
    return results
