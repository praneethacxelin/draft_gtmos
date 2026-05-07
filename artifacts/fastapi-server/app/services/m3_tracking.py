"""M3 Intelligence Loop — periodic engagement→signal converter.

Every ``M3_INTERVAL_SEC`` seconds (default 6h) the loop scans recent
``OutreachEvent`` rows, finds contacts whose engagement score has moved above
``ENGAGEMENT_THRESHOLD`` since the last scan, and inserts a ``Signal`` row
with ``source = 'm3_tracking'`` so downstream scoring picks it up. Idempotent:
we de-dupe via a ``raw_data_json`` window key so re-runs don't double count.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import func

from app.db import (
    SessionLocal,
    OutreachEvent,
    Sequence,
    Contact,
    Signal,
    gen_id,
)

log = logging.getLogger("gtm.m3")
M3_INTERVAL_SEC = 6 * 60 * 60  # 6 hours
ENGAGEMENT_THRESHOLD = 2  # contacts with >= N opens/clicks/replies in window
WINDOW_HOURS = 6

# event_type -> weighting used to compute engagement score deltas
EVENT_WEIGHTS = {
    "opened": 1,
    "clicked": 2,
    "replied": 4,
    "meeting_booked": 6,
}


def _scan_once() -> int:
    """Single pass; returns count of new signals inserted."""
    db = SessionLocal()
    inserted = 0
    try:
        window_start = datetime.utcnow() - timedelta(hours=WINDOW_HOURS)
        window_key = window_start.strftime("%Y%m%d%H")

        # Group recent engagement events by contact via Sequence.contact_id.
        rows = (
            db.query(
                Sequence.contact_id.label("contact_id"),
                Sequence.strategy_id.label("strategy_id"),
                OutreachEvent.event_type,
                func.count(OutreachEvent.id).label("n"),
            )
            .join(Sequence, Sequence.id == OutreachEvent.sequence_id)
            .filter(OutreachEvent.occurred_at >= window_start)
            .filter(OutreachEvent.event_type.in_(list(EVENT_WEIGHTS.keys())))
            .group_by(Sequence.contact_id, Sequence.strategy_id, OutreachEvent.event_type)
            .all()
        )

        per_contact: dict[tuple[str, str], dict[str, int]] = {}
        for r in rows:
            key = (r.contact_id, r.strategy_id)
            per_contact.setdefault(key, {})[r.event_type] = int(r.n)

        for (contact_id, strategy_id), counts in per_contact.items():
            score = sum(EVENT_WEIGHTS[t] * n for t, n in counts.items())
            if score < ENGAGEMENT_THRESHOLD:
                continue

            contact = db.query(Contact).filter(Contact.id == contact_id).first()
            if not contact:
                continue

            # De-dupe: one m3_tracking signal per (contact, window) pair.
            existing = (
                db.query(Signal)
                .filter(Signal.account_id == contact.account_id)
                .filter(Signal.source == "m3_tracking")
                .filter(Signal.raw_data_json["window_key"].astext == window_key)
                .filter(Signal.raw_data_json["contact_id"].astext == contact_id)
                .first()
            )
            if existing:
                continue

            db.add(Signal(
                id=gen_id(),
                account_id=contact.account_id,
                strategy_id=strategy_id,
                signal_type="engagement_lift",
                summary=(
                    f"Elevated engagement from {contact.full_name}: "
                    + ", ".join(f"{t}×{n}" for t, n in counts.items())
                ),
                strength_score=min(1.0, score / 10.0),
                source="m3_tracking",
                detected_at=datetime.utcnow(),
                raw_data_json={
                    "window_key": window_key,
                    "contact_id": contact_id,
                    "counts": counts,
                    "score": score,
                },
            ))
            inserted += 1

        if inserted:
            db.commit()
    finally:
        db.close()
    return inserted


async def m3_loop() -> None:
    """Background task: scan every M3_INTERVAL_SEC."""
    while True:
        try:
            count = await asyncio.to_thread(_scan_once)
            if count:
                log.info("m3 tracking inserted %d signals", count)
        except Exception as exc:  # pragma: no cover
            log.exception("m3 tracking crashed: %s", exc)
        await asyncio.sleep(M3_INTERVAL_SEC)
