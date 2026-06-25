"""Silent Apollo capture — mirrors every Apollo person/org into ``apollo_captures``.

Best-effort and fully decoupled: a capture failure must never affect the Apollo
call or the pipeline. Deduped by (apollo_id, record_type); repeated pulls bump
``seen_count`` and refresh fields (e.g. a later email reveal). This quietly
builds our own proprietary dataset as usage grows.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.db import SessionLocal, ApolloCapture

log = logging.getLogger("gtm.apollo_store")


def _domain(org: dict) -> Optional[str]:
    if not isinstance(org, dict):
        return None
    dom = org.get("primary_domain") or org.get("domain")
    if dom:
        return str(dom).strip().lower() or None
    website = org.get("website_url") or org.get("website")
    if website:
        d = str(website).replace("https://", "").replace("http://", "").replace("www.", "")
        return d.split("/")[0].strip().lower() or None
    return None


def _person_fields(p: dict) -> dict:
    org = p.get("organization") or {}
    name = (
        p.get("name")
        or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        or None
    )
    loc = ", ".join([x for x in (p.get("city"), p.get("state"), p.get("country")) if x]) or None
    return {
        "name": name,
        "title": p.get("title"),
        "company": org.get("name"),
        "domain": _domain(org),
        "email": p.get("email") or None,
        "linkedin_url": p.get("linkedin_url"),
        "industry": org.get("industry"),
        "location": loc,
    }


def _org_fields(org: dict) -> dict:
    loc = ", ".join(
        [x for x in (org.get("headquarters_city"), org.get("headquarters_country")) if x]
    ) or None
    return {
        "name": org.get("name"),
        "company": org.get("name"),
        "domain": _domain(org),
        "email": None,
        "linkedin_url": org.get("linkedin_url"),
        "industry": org.get("industry"),
        "location": loc,
    }


def _upsert(db, apollo_id: str, record_type: str, fields: dict, payload: dict,
            endpoint: Optional[str], strategy_id: Optional[str]) -> None:
    now_dt = datetime.utcnow()
    row = (
        db.query(ApolloCapture)
        .filter(ApolloCapture.apollo_id == apollo_id, ApolloCapture.record_type == record_type)
        .first()
    )
    if row:
        row.seen_count = (row.seen_count or 1) + 1
        row.last_seen_at = now_dt
        row.payload_json = payload
        row.endpoint = endpoint or row.endpoint
        if strategy_id:
            row.strategy_id = strategy_id
        # Refresh any field that now has a value (e.g. a freshly revealed email).
        for k, v in fields.items():
            if v and not getattr(row, k, None):
                setattr(row, k, v)
            elif k == "email" and v:
                row.email = v
    else:
        db.add(
            ApolloCapture(
                apollo_id=apollo_id,
                record_type=record_type,
                endpoint=endpoint,
                strategy_id=strategy_id,
                payload_json=payload,
                seen_count=1,
                first_seen_at=now_dt,
                last_seen_at=now_dt,
                **fields,
            )
        )


def capture_people(
    records,
    endpoint: Optional[str] = None,
    strategy_id: Optional[str] = None,
) -> int:
    """Silently mirror a list of Apollo person dicts (and their orgs). Returns
    the number of records touched. Never raises."""
    if not records:
        return 0
    touched = 0
    db = None
    try:
        db = SessionLocal()
        for p in records:
            if not isinstance(p, dict):
                continue
            pid = p.get("id")
            if pid:
                _upsert(db, str(pid), "person", _person_fields(p), p, endpoint, strategy_id)
                touched += 1
            org = p.get("organization") or {}
            oid = org.get("id")
            if oid:
                _upsert(db, str(oid), "organization", _org_fields(org), org, endpoint, strategy_id)
                touched += 1
        db.commit()
    except Exception as exc:  # pragma: no cover - capture must never break flow
        if db is not None:
            try:
                db.rollback()
            except Exception:
                pass
        log.debug("apollo capture skipped: %s", exc)
    finally:
        if db is not None:
            db.close()
    return touched


def capture_person(
    record,
    endpoint: Optional[str] = None,
    strategy_id: Optional[str] = None,
) -> int:
    """Silently mirror a single Apollo person dict."""
    if not isinstance(record, dict):
        return 0
    return capture_people([record], endpoint=endpoint, strategy_id=strategy_id)
