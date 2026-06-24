import json
from fastapi import APIRouter, Depends, HTTPException
from app.services import audit_service
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from app.db import get_session, SessionLocal, Sequence, SequenceStep, OutreachEvent, User
from app.auth import current_user
from app.scoping import own_contact, own_sequence
from app.agents.s3_outreach import generate_sequence, deliverability_check, launch_sequence

router = APIRouter(prefix="/sequences", tags=["sequences"])

class GenerateOptions(BaseModel):
    goal: str | None = None
    tone: str | None = None
    length: int | None = None


@router.post("/generate/{contact_id}")
async def generate(
    contact_id: str,
    options: GenerateOptions | None = None,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    own_contact(db, contact_id, user)
    
    goal = options.goal if options else None
    tone = options.tone if options else None
    length = options.length if options else None
    
    return await generate_sequence(db, contact_id, goal=goal, tone=tone, length=length)


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
    steps = db.query(SequenceStep).filter(SequenceStep.sequence_id == seq.id).order_by(SequenceStep.step_number).all()
    raw_plan = seq.channel_plan_json
    if isinstance(raw_plan, dict) and "plan" in raw_plan:
        channel_plan = raw_plan.get("plan")
        provenance = raw_plan.get("_provenance")
    else:
        channel_plan = raw_plan
        provenance = None
    last_launch = raw_plan.get("_last_launch") if isinstance(raw_plan, dict) else None
    return {
        "id": seq.id,
        "status": seq.status,
        "channel_plan": channel_plan,
        "provenance": provenance,
        "last_launch": last_launch,
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
    from app.services.rate_limit import RateLimitExceeded

    async def gen():
        yield {"event": "stage_start", "data": json.dumps({"stage": "launch"})}
        db2 = SessionLocal()
        try:
            result = launch_sequence(db2, sequence_id, test_email=test_email, schedule=schedule)
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


@router.patch("/steps/{step_id}")
def patch_step(
    step_id: str,
    body: StepPatch,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
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
