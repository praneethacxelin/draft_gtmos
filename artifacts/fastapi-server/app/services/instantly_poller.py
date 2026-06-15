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
    Strategy,
    EngagementEvent,
    QualificationRecord,
    Contact,
)
from app.services import settings_service, clients

log = logging.getLogger("gtm.instantly_poll")
POLL_INTERVAL_SEC = 3600  # 1 hour


def _ingest_once() -> int:
    """Pull engagement for every active Instantly campaign, using each
    campaign owner's own Instantly key. Returns total events ingested."""
    db = SessionLocal()
    ingested = 0
    # Cache per-user key lookups to avoid hammering the DB.
    key_cache: dict[str, str | None] = {}
    try:
        rows = db.query(InstantlyCampaign).filter(InstantlyCampaign.status == "active").all()
        for row in rows:
            seq = db.query(Sequence).filter(Sequence.id == row.sequence_id).first()
            if not seq:
                continue
            strategy = (
                db.query(Strategy).filter(Strategy.id == seq.strategy_id).first()
                if seq.strategy_id
                else None
            )
            owner_id = strategy.user_id if strategy else None
            if not owner_id:
                continue
            if owner_id not in key_cache:
                key_cache[owner_id] = settings_service.get_key(db, owner_id, "instantly")
            instantly_key = key_cache[owner_id]
            if not instantly_key:
                continue
            try:
                camp_id = row.instantly_campaign_id
                # Get overall analytics
                analytics = clients.instantly_get_analytics(instantly_key, camp_id)
                if analytics:
                    row.analytics_json = analytics

                # Get steps analytics
                steps_analytics = clients.instantly_get_steps_analytics(instantly_key, camp_id)
                if steps_analytics:
                    row.steps_analytics_json = steps_analytics

                # Get daily analytics (last 30 days)
                end_date = datetime.utcnow().strftime("%Y-%m-%d")
                start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
                daily = clients.instantly_get_daily_analytics(instantly_key, camp_id, start_date, end_date)
                if daily:
                    row.daily_analytics_json = daily

                # Fetch leads to populate Intelligence tab
                leads = clients.instantly_get_leads(instantly_key, camp_id) or []
                for ld in leads:
                    email = ld.get("email")
                    status = ld.get("status")
                    if not email or not status: continue
                    # Find contact
                    contact = db.query(Contact).filter(Contact.email == email).first()
                    if not contact: continue
                    
                    # Insert EngagementEvent if interested or replied
                    if status in ("interested", "replied", "meeting_booked"):
                        # de-dupe
                        exists = db.query(EngagementEvent).filter(
                            EngagementEvent.contact_id == contact.id,
                            EngagementEvent.channel == "email",
                            EngagementEvent.event_type == "email_reply"
                        ).first()
                        if not exists:
                            db.add(EngagementEvent(
                                strategy_id=seq.strategy_id,
                                contact_id=contact.id,
                                account_id=contact.account_id,
                                channel="email",
                                event_type="email_reply",
                                intent_contribution_score=10.0,
                                metadata_json={"instantly_status": status, "lead_id": ld.get("id")}
                            ))
                            if status in ("interested", "meeting_booked"):
                                # Also update Qualification
                                q = db.query(QualificationRecord).filter(QualificationRecord.contact_id == contact.id).first()
                                if q:
                                    q.status = "sql" if status == "meeting_booked" else "mql"
                                    q.reasoning = f"Instantly lead status changed to {status}"

                ingested += 1
            except Exception as exc:  # pragma: no cover
                log.warning("instantly fetch failed for %s: %s", row.instantly_campaign_id, exc)
                continue

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
