"""Audit log query endpoint."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session, User, AuditLog
from app.auth import current_user
from app.services import audit_service

router = APIRouter(prefix="/audit-logs", tags=["audit"])


def _serialize(row: AuditLog) -> dict:
    return {
        "id": row.id,
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
        "event_type": row.event_type,
        "service": row.service,
        "strategy_id": row.strategy_id,
        "strategy_name": row.strategy_name,
        "http_method": row.http_method,
        "endpoint_url": row.endpoint_url,
        "request_params": row.request_params,
        "response_status": row.response_status,
        "response_summary": row.response_summary,
        "latency_ms": row.latency_ms,
        "curl_command": row.curl_command,
        "is_live": row.is_live,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "change_field": row.change_field,
        "change_before": row.change_before,
        "change_after": row.change_after,
        "actor": row.actor,
        "summary": row.summary,
    }


@router.get("")
def list_audit_logs(
    strategy_id: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    from_ts: Optional[str] = Query(None, description="ISO datetime"),
    to_ts: Optional[str] = Query(None, description="ISO datetime"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    from_dt = datetime.fromisoformat(from_ts) if from_ts else None
    to_dt = datetime.fromisoformat(to_ts) if to_ts else None
    rows, total = audit_service.query_logs(
        db,
        strategy_id=strategy_id,
        service=service,
        event_type=event_type,
        from_ts=from_dt,
        to_ts=to_dt,
        limit=limit,
        offset=offset,
    )
    return {"logs": [_serialize(r) for r in rows], "total": total}


@router.get("/by-strategy")
def get_audit_logs_by_strategy(
    from_ts: str | None = None,
    to_ts: str | None = None,
    service: str | None = None,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Return audit logs grouped by strategy for the Pipeline Flow view."""
    from_dt = datetime.fromisoformat(from_ts) if from_ts else None
    to_dt = datetime.fromisoformat(to_ts) if to_ts else None

    q = db.query(AuditLog)
    if from_dt:
        q = q.filter(AuditLog.occurred_at >= from_dt)
    if to_dt:
        q = q.filter(AuditLog.occurred_at <= to_dt)
    if service:
        q = q.filter(AuditLog.service == service)

    # Fetch most recent 500 logs first, keeping them newest first
    rows = q.order_by(AuditLog.occurred_at.desc()).limit(500).all()

    grouped: dict[str, dict] = {}
    ungrouped: list[dict] = []

    for row in rows:
        serialized = _serialize(row)
        sid = row.strategy_id
        if sid:
            if sid not in grouped:
                grouped[sid] = {
                    "strategy_id": sid,
                    "strategy_name": row.strategy_name or "Unknown",
                    "events": [],
                    "event_counts": {},
                }
            grouped[sid]["events"].append(serialized)
            et = row.event_type or "other"
            grouped[sid]["event_counts"][et] = grouped[sid]["event_counts"].get(et, 0) + 1
        else:
            ungrouped.append(serialized)

    return {
        "strategies": list(grouped.values()),
        "ungrouped": ungrouped,
    }
