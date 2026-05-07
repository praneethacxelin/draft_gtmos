"""Hourly Instantly engagement poller.

For every ``InstantlyCampaign`` row with a non-null ``instantly_campaign_id``
we attempt to pull recent engagement events (sent / opened / clicked /
replied / bounced). Events that haven't been recorded yet are inserted
into ``outreach_events``. The polling loop is scheduled at startup from
``main.lifespan`` and silently no-ops when no Instantly API key is
configured.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from app.db import (
    SessionLocal,
    InstantlyCampaign,
    OutreachEvent,
    Sequence,
    SequenceStep,
)
from app.services import settings_service, clients

log = logging.getLogger("gtm.instantly_poll")
POLL_INTERVAL_SEC = 3600  # 1 hour


def _ingest_once() -> int:
    """Pull engagement for every active Instantly campaign. Returns events ingested."""
    db = SessionLocal()
    ingested = 0
    try:
        instantly_key = settings_service.get_key(db, "instantly")
        if not instantly_key:
            return 0

        rows = db.query(InstantlyCampaign).filter(InstantlyCampaign.status == "active").all()
        for row in rows:
            try:
                events = clients.instantly_get_events(instantly_key, row.instantly_campaign_id) or []
            except Exception as exc:  # pragma: no cover - external API
                log.warning("instantly fetch failed for %s: %s", row.instantly_campaign_id, exc)
                continue
            seq = db.query(Sequence).filter(Sequence.id == row.sequence_id).first()
            if not seq:
                continue
            steps = {s.step_number: s for s in db.query(SequenceStep).filter(SequenceStep.sequence_id == seq.id).all()}
            for ev in events:
                ev_id = str(ev.get("id") or "")
                # de-dupe via raw_data_json["instantly_id"]
                exists = (
                    db.query(OutreachEvent)
                    .filter(OutreachEvent.sequence_id == seq.id)
                    .filter(OutreachEvent.raw_data_json["instantly_id"].astext == ev_id)
                    .first()
                )
                if exists:
                    continue
                step = steps.get(ev.get("step")) if isinstance(ev.get("step"), int) else None
                db.add(OutreachEvent(
                    sequence_id=seq.id,
                    sequence_step_id=step.id if step else None,
                    event_type=ev.get("event_type", "sent"),
                    occurred_at=datetime.utcnow(),
                    raw_data_json={"instantly_id": ev_id, **ev},
                ))
                ingested += 1
            row.synced_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()
    return ingested


async def poll_loop() -> None:
    """Background task: poll Instantly every POLL_INTERVAL_SEC."""
    while True:
        try:
            count = await asyncio.to_thread(_ingest_once)
            if count:
                log.info("instantly poller ingested %d events", count)
        except Exception as exc:  # pragma: no cover
            log.exception("instantly poller crashed: %s", exc)
        await asyncio.sleep(POLL_INTERVAL_SEC)


def simulate_engagement_timeline(db, sequence_id: str) -> int:
    """Generate a deterministic engagement timeline for a launched (simulated)
    sequence. Used both by ``launch_sequence`` in demo mode and by ``seed.py``
    so the M3 / Copilot views aren't empty on a fresh demo.
    """
    steps = (
        db.query(SequenceStep)
        .filter(SequenceStep.sequence_id == sequence_id)
        .order_by(SequenceStep.step_number)
        .all()
    )
    if not steps:
        return 0
    base = datetime.utcnow() - timedelta(days=4)
    inserted = 0
    for idx, step in enumerate(steps):
        sent_at = base + timedelta(days=idx, hours=1)
        step.sent_at = sent_at
        step.status = "sent"
        db.add(OutreachEvent(
            sequence_id=sequence_id,
            sequence_step_id=step.id,
            event_type="sent",
            occurred_at=sent_at,
        ))
        inserted += 1
        # Simulate engagement for steps 1 and 2 only (typical funnel)
        if idx == 0:
            db.add(OutreachEvent(
                sequence_id=sequence_id, sequence_step_id=step.id,
                event_type="opened", occurred_at=sent_at + timedelta(hours=4),
            ))
            inserted += 1
        if idx == 1:
            for evt, delta in [("opened", 2), ("clicked", 5), ("replied", 9)]:
                db.add(OutreachEvent(
                    sequence_id=sequence_id, sequence_step_id=step.id,
                    event_type=evt, occurred_at=sent_at + timedelta(hours=delta),
                ))
                inserted += 1
    db.commit()
    return inserted
