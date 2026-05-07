"""SDR Copilot — next-best-action recommendations."""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db import Contact, Sequence, SequenceStep, OutreachEvent, Signal, ContactSnooze


def feed(db: Session, strategy_id: str, limit: int = 25) -> list[dict]:
    out = []
    now = datetime.utcnow()
    snoozed_ids = {
        row.contact_id for row in db.query(ContactSnooze)
        .filter(ContactSnooze.strategy_id == strategy_id)
        .filter(ContactSnooze.snoozed_until > now)
        .all()
    }
    contacts = (
        db.query(Contact)
        .filter(Contact.strategy_id == strategy_id, Contact.tier == 1)
        .order_by(Contact.total_score.desc())
        .limit(limit + len(snoozed_ids))
        .all()
    )
    contacts = [c for c in contacts if c.id not in snoozed_ids][:limit]

    cutoff = now - timedelta(hours=48)

    for c in contacts:
        # Recent signal?
        recent_sig = (
            db.query(Signal)
            .filter(Signal.account_id == c.account_id, Signal.detected_at >= cutoff)
            .order_by(Signal.detected_at.desc())
            .first()
        )
        seq = db.query(Sequence).filter(Sequence.contact_id == c.id).first()
        replied = False
        opened = 0
        if seq:
            events = db.query(OutreachEvent).filter(OutreachEvent.sequence_id == seq.id).all()
            opened = sum(1 for e in events if e.event_type == "opened")
            replied = any(e.event_type == "replied" for e in events)

        action = None
        reason = None
        recommended_copy = None
        urgency = "medium"

        if replied:
            action = "Respond now"
            reason = "Prospect replied — respond within 2 hours."
            recommended_copy = "Thanks for the reply. Are you open to a 15-min call this week?"
            urgency = "high"
        elif recent_sig:
            action = f"Call today — {recent_sig.signal_type} signal"
            reason = recent_sig.summary[:160]
            recommended_copy = (
                f"Reference the {recent_sig.signal_type} event in your opener — "
                "tie it to your product's relevant use case."
            )
            urgency = "high"
        elif opened >= 3 and seq:
            action = "Send follow-up variant"
            reason = f"Opened {opened}× but no reply."
            recommended_copy = "Lead with a stat or proof point and a single CTA."
            urgency = "medium"
        elif seq and seq.status == "draft":
            action = "Launch sequence"
            reason = "Sequence drafted but not launched."
            recommended_copy = "Run the deliverability check and push to Instantly."
            urgency = "low"
        else:
            action = "Build sequence"
            reason = "No outreach started for this Tier 1 contact."
            recommended_copy = "Generate a 4-step sequence for this contact."
            urgency = "low"

        out.append({
            "contact_id": c.id,
            "contact_name": c.full_name,
            "title": c.title,
            "score": c.total_score,
            "action": action,
            "reason": reason,
            "recommended_copy": recommended_copy,
            "urgency": urgency,
        })

    out.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["urgency"]])
    return out
