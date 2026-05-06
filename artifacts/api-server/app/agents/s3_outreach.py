"""S3 — 3-Channel Outreach generation."""
import json
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db import Strategy, Contact, Sequence, SequenceStep, Account
from app.llm import chat_json, chat_text
from app.services import settings_service, clients


SPAM_TRIGGERS = ["free", "guarantee", "$$$", "act now", "click here", "buy now", "no risk"]


def generate_sequence(db: Session, contact_id: str) -> dict:
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        return {"error": "Contact not found"}
    strategy = db.query(Strategy).filter(Strategy.id == contact.strategy_id).first()
    account = db.query(Account).filter(Account.id == contact.account_id).first()

    persona_block = ""
    if strategy and strategy.personas_json:
        ptype = contact.persona_type or "champion"
        persona = strategy.personas_json.get(ptype) if isinstance(strategy.personas_json, dict) else None
        if persona:
            persona_block = json.dumps(persona)[:600]

    use_cases = ""
    if strategy and strategy.use_cases_json:
        ucs = strategy.use_cases_json.get("use_cases", []) if isinstance(strategy.use_cases_json, dict) else []
        use_cases = json.dumps(ucs[:3])[:600]

    seniority = (contact.seniority or "").lower()
    email_first = seniority in ("vp", "c_suite", "director", "head", "owner", "founder")
    channel_plan = []
    if email_first:
        channel_plan = [
            {"step": 1, "channel": "email", "wait_days": 0},
            {"step": 2, "channel": "email", "wait_days": 3},
            {"step": 3, "channel": "linkedin", "wait_days": 4},
            {"step": 4, "channel": "call", "wait_days": 5},
        ]
    else:
        channel_plan = [
            {"step": 1, "channel": "linkedin", "wait_days": 0},
            {"step": 2, "channel": "linkedin", "wait_days": 3},
            {"step": 3, "channel": "email", "wait_days": 4},
            {"step": 4, "channel": "email", "wait_days": 5},
        ]

    # Personalize messages
    plan_str = ", ".join(f"step {s['step']} via {s['channel']}" for s in channel_plan)
    msgs = chat_json(
        f"Write personalized outreach messages for {contact.full_name}, {contact.title} at "
        f"{account.company_name if account else 'the company'}. "
        f"Product: {strategy.product_name if strategy else ''}. "
        f"Persona profile: {persona_block}. Top use cases: {use_cases}. "
        f"Sequence: {plan_str}. Return JSON with key 'messages' = array of "
        "{step, subject, body}. Subjects under 60 chars. Bodies 4-6 sentences, "
        "specific and not salesy. For LinkedIn steps, body should be a short DM (2-3 sentences). "
        "For call steps, body should be a 3-bullet talking-points outline.",
        max_tokens=2000,
    )

    # Persist
    seq = db.query(Sequence).filter(Sequence.contact_id == contact_id).first()
    if seq:
        db.query(SequenceStep).filter(SequenceStep.sequence_id == seq.id).delete()
    else:
        seq = Sequence(contact_id=contact_id, strategy_id=contact.strategy_id)
        db.add(seq)
        db.flush()

    seq.channel_plan_json = channel_plan
    seq.status = "draft"

    base_time = datetime.utcnow().replace(hour=9, minute=0, second=0, microsecond=0)
    cumulative = 0
    msg_by_step = {m.get("step"): m for m in (msgs.get("messages", []) if isinstance(msgs, dict) else [])}
    for s in channel_plan:
        m = msg_by_step.get(s["step"], {})
        cumulative += s["wait_days"]
        send_at = base_time + timedelta(days=cumulative, hours=random.randint(0, 4))
        db.add(SequenceStep(
            sequence_id=seq.id,
            step_number=s["step"],
            channel=s["channel"],
            subject=m.get("subject"),
            body=m.get("body"),
            wait_days=s["wait_days"],
            send_at=send_at,
        ))
    db.commit()

    return {
        "sequence_id": seq.id,
        "step_count": len(channel_plan),
    }


def deliverability_check(db: Session, sequence_id: str) -> dict:
    steps = db.query(SequenceStep).filter(
        SequenceStep.sequence_id == sequence_id, SequenceStep.channel == "email"
    ).all()
    if not steps:
        return {"score": 100, "flagged_phrases": [], "notes": "No email steps to evaluate."}

    flagged: list[str] = []
    total_chars = 0
    link_count = 0
    for s in steps:
        body = (s.body or "").lower()
        total_chars += len(body)
        link_count += body.count("http")
        for trig in SPAM_TRIGGERS:
            if trig in body:
                flagged.append(trig)

    score = 100
    score -= min(len(flagged) * 8, 40)
    if total_chars / max(len(steps), 1) > 1500:
        score -= 10
    if link_count > 4:
        score -= 10

    sequence = db.query(Sequence).filter(Sequence.id == sequence_id).first()
    if sequence:
        sequence.deliverability_score = score
        sequence.deliverability_report_json = {
            "score": score,
            "flagged_phrases": flagged,
            "link_count": link_count,
            "avg_length": int(total_chars / max(len(steps), 1)),
        }
        db.commit()

    return {
        "score": score,
        "flagged_phrases": list(set(flagged)),
        "link_count": link_count,
        "avg_length": int(total_chars / max(len(steps), 1)),
        "notes": "Deliverability looks good." if score >= 80 else "Consider trimming language and links.",
    }


def launch_sequence(db: Session, sequence_id: str) -> dict:
    seq = db.query(Sequence).filter(Sequence.id == sequence_id).first()
    if not seq:
        return {"error": "Sequence not found"}

    instantly_key = settings_service.get_key(db, "instantly")
    steps = db.query(SequenceStep).filter(SequenceStep.sequence_id == sequence_id).order_by(SequenceStep.step_number).all()

    if instantly_key:
        contact = db.query(Contact).filter(Contact.id == seq.contact_id).first()
        result = clients.instantly_create_campaign(
            instantly_key,
            f"GTM-{seq.id[:8]}",
            [{"channel": s.channel, "subject": s.subject, "body": s.body} for s in steps],
        )
        seq.status = "active"
        seq.instantly_campaign_id = (result or {}).get("id") if isinstance(result, dict) else None
        db.commit()
        return {"status": "active", "instantly_pushed": True}
    else:
        seq.status = "simulated"
        # Mark as sent and synthesize some engagement events
        for s in steps:
            s.sent_at = datetime.utcnow()
            s.status = "sent"
        db.commit()
        return {"status": "simulated", "instantly_pushed": False}
