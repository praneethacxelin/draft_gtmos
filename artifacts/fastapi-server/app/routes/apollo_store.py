"""Read-only view into the silent Apollo capture store.

Lets you confirm the proprietary dataset is filling up as Apollo is used. The
table itself is written silently by ``app.services.apollo_store``; these
endpoints only report on it.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_session, ApolloCapture, User
from app.auth import current_user

router = APIRouter(prefix="/apollo-store", tags=["apollo-store"])


@router.get("/stats")
def apollo_store_stats(
    db: Session = Depends(get_session),
    _user: User = Depends(current_user),
):
    total = db.query(func.count(ApolloCapture.id)).scalar() or 0
    people = (
        db.query(func.count(ApolloCapture.id))
        .filter(ApolloCapture.record_type == "person")
        .scalar()
        or 0
    )
    orgs = (
        db.query(func.count(ApolloCapture.id))
        .filter(ApolloCapture.record_type == "organization")
        .scalar()
        or 0
    )
    with_email = (
        db.query(func.count(ApolloCapture.id))
        .filter(ApolloCapture.email.isnot(None))
        .scalar()
        or 0
    )
    last = (
        db.query(ApolloCapture.last_seen_at)
        .order_by(ApolloCapture.last_seen_at.desc())
        .first()
    )
    return {
        "total": total,
        "people": people,
        "organizations": orgs,
        "with_email": with_email,
        "last_captured_at": last[0].isoformat() if last and last[0] else None,
    }


@router.get("/sample")
def apollo_store_sample(
    record_type: str | None = Query(None, description="person | organization"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
    _user: User = Depends(current_user),
):
    q = db.query(ApolloCapture)
    if record_type:
        q = q.filter(ApolloCapture.record_type == record_type)
    rows = q.order_by(ApolloCapture.last_seen_at.desc()).limit(limit).all()
    return [
        {
            "apollo_id": r.apollo_id,
            "record_type": r.record_type,
            "name": r.name,
            "title": r.title,
            "company": r.company,
            "domain": r.domain,
            "email": r.email,
            "industry": r.industry,
            "location": r.location,
            "endpoint": r.endpoint,
            "seen_count": r.seen_count,
            "first_seen_at": r.first_seen_at.isoformat() if r.first_seen_at else None,
            "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None,
        }
        for r in rows
    ]
