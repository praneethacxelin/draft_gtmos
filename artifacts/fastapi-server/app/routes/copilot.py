from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_session, ContactSnooze, Contact, User, gen_id
from app.auth import current_user
from app.scoping import own_strategy, own_contact
from app.agents.sdr_copilot import feed

router = APIRouter(prefix="/copilot", tags=["copilot"])


class SnoozeBody(BaseModel):
    hours: int = 24
    reason: str | None = None


@router.get("/feed")
def get_feed(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    own_strategy(db, strategy_id, user)
    return feed(db, strategy_id)


@router.post("/snooze/{contact_id}")
def snooze_contact(
    contact_id: str,
    body: SnoozeBody,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Suppress this contact from the next-best-action feed until ``until``."""
    contact = own_contact(db, contact_id, user)
    hours = max(1, min(body.hours, 24 * 30))
    until = datetime.utcnow() + timedelta(hours=hours)

    existing = (
        db.query(ContactSnooze)
        .filter(ContactSnooze.contact_id == contact_id)
        .first()
    )
    if existing:
        existing.snoozed_until = until
        existing.reason = body.reason
        existing.updated_at = datetime.utcnow()
    else:
        db.add(ContactSnooze(
            id=gen_id(),
            contact_id=contact_id,
            strategy_id=contact.strategy_id,
            snoozed_until=until,
            reason=body.reason,
        ))
    db.commit()
    return {"contact_id": contact_id, "snoozed_until": until.isoformat()}
