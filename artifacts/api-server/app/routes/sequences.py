from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_session, Sequence, SequenceStep, OutreachEvent
from app.agents.s3_outreach import generate_sequence, deliverability_check, launch_sequence

router = APIRouter(prefix="/sequences", tags=["sequences"])


@router.post("/generate/{contact_id}")
def generate(contact_id: str, db: Session = Depends(get_session)) -> dict:
    return generate_sequence(db, contact_id)


@router.get("/by-contact/{contact_id}")
def by_contact(contact_id: str, db: Session = Depends(get_session)) -> dict | None:
    seq = db.query(Sequence).filter(Sequence.contact_id == contact_id).first()
    if not seq:
        return None
    steps = db.query(SequenceStep).filter(SequenceStep.sequence_id == seq.id).order_by(SequenceStep.step_number).all()
    return {
        "id": seq.id,
        "status": seq.status,
        "channel_plan": seq.channel_plan_json,
        "deliverability_score": seq.deliverability_score,
        "deliverability_report": seq.deliverability_report_json,
        "instantly_campaign_id": seq.instantly_campaign_id,
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
def check(sequence_id: str, db: Session = Depends(get_session)) -> dict:
    return deliverability_check(db, sequence_id)


@router.post("/{sequence_id}/launch")
def launch(sequence_id: str, db: Session = Depends(get_session)) -> dict:
    return launch_sequence(db, sequence_id)


@router.get("/{sequence_id}/engagement")
def engagement(sequence_id: str, db: Session = Depends(get_session)) -> list[dict]:
    rows = db.query(OutreachEvent).filter(OutreachEvent.sequence_id == sequence_id).order_by(OutreachEvent.occurred_at.desc()).all()
    return [{
        "event_type": r.event_type,
        "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
    } for r in rows]
