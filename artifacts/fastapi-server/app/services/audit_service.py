"""Audit logging helpers.

All functions create their own short-lived DB sessions so they can be
called from any context (background tasks, client wrappers, route
handlers) without receiving a session as a parameter.

Failures are swallowed so a logging problem never breaks the main flow.
"""
import json
import logging
from typing import Any, Optional

from app.db import SessionLocal, AuditLog

log = logging.getLogger("gtm.audit")


def _to_jsonb(value: Any) -> Any:
    """Coerce a value to something safe for a JSONB column."""
    if value is None or isinstance(value, (dict, list, bool, int, float)):
        return value
    return str(value)[:4000]


def _make_curl(
    method: str,
    url: str,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    body: Optional[dict] = None,
) -> str:
    """Build a curl command string, masking any credential fields."""
    _SENSITIVE = {"api_key", "key", "secret", "token", "password", "authorization"}

    def _mask_key(k: str, v: Any) -> str:
        return "****" if any(s in k.lower() for s in _SENSITIVE) else str(v)

    full_url = url
    if params:
        qs = "&".join(f"{k}={_mask_key(k, v)}" for k, v in params.items())
        full_url = f"{url}?{qs}"

    parts = [f'curl -sS -X {method} "{full_url}"']
    if headers:
        for k, v in headers.items():
            safe_v = "****" if k.lower() in ("authorization", "x-api-key") else v
            parts.append(f'  -H "{k}: {safe_v}"')
    if body:
        safe_body = {k: ("****" if any(s in k.lower() for s in _SENSITIVE) else v) for k, v in body.items()}
        parts.append(f"  -d '{json.dumps(safe_body)}'")

    return " \\\n".join(parts)


def log_api_call(
    service: str,
    method: str,
    url: str,
    request_params: Optional[dict] = None,
    response_status: Optional[int] = None,
    latency_ms: Optional[int] = None,
    curl_command: Optional[str] = None,
    strategy_id: Optional[str] = None,
    strategy_name: Optional[str] = None,
    is_live: bool = True,
    response_summary: Optional[dict] = None,
    summary: Optional[str] = None,
) -> None:
    try:
        db = SessionLocal()
        try:
            entry = AuditLog(
                event_type="api_call",
                service=service,
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                http_method=method,
                endpoint_url=url,
                request_params=request_params,
                response_status=response_status,
                response_summary=response_summary,
                latency_ms=latency_ms,
                curl_command=curl_command,
                is_live=is_live,
                actor="agent",
                summary=summary or f"{service} {method} {url[:80]}",
            )
            db.add(entry)
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        log.warning("audit log_api_call failed: %s", exc)


def log_change(
    event_type: str,
    entity_type: str,
    entity_id: str,
    strategy_id: Optional[str] = None,
    strategy_name: Optional[str] = None,
    change_field: Optional[str] = None,
    change_before: Any = None,
    change_after: Any = None,
    actor: str = "user",
    summary: Optional[str] = None,
) -> None:
    try:
        db = SessionLocal()
        try:
            entry = AuditLog(
                event_type=event_type,
                service="internal",
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                entity_type=entity_type,
                entity_id=entity_id,
                change_field=change_field,
                change_before=_to_jsonb(change_before),
                change_after=_to_jsonb(change_after),
                is_live=False,
                actor=actor,
                summary=summary or f"{entity_type} {entity_id[:8]} · {change_field or 'updated'}",
            )
            db.add(entry)
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        log.warning("audit log_change failed: %s", exc)


def query_logs(
    db,
    strategy_id: Optional[str] = None,
    service: Optional[str] = None,
    event_type: Optional[str] = None,
    from_ts=None,
    to_ts=None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list, int]:
    q = db.query(AuditLog)
    if strategy_id:
        q = q.filter(AuditLog.strategy_id == strategy_id)
    if service:
        q = q.filter(AuditLog.service == service)
    if event_type:
        q = q.filter(AuditLog.event_type == event_type)
    if from_ts:
        q = q.filter(AuditLog.occurred_at >= from_ts)
    if to_ts:
        q = q.filter(AuditLog.occurred_at <= to_ts)
    total = q.count()
    rows = q.order_by(AuditLog.occurred_at.desc()).offset(offset).limit(limit).all()
    return rows, total
