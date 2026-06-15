"""Outreach analytics — aggregates OutreachEvent rows from Instantly campaigns."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Optional

from app.db import (
    get_session,
    User,
    OutreachEvent,
    Sequence,
    Contact,
    InstantlyCampaign,
    Strategy,
)
from app.auth import current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _pct(num: int, denom: int) -> float:
    return round(num / denom * 100, 1) if denom else 0.0


@router.get("/outreach")
def outreach_analytics(
    strategy_id: Optional[str] = Query(None),
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    q = db.query(Sequence)
    if strategy_id:
        q = q.filter(Sequence.strategy_id == strategy_id)
    sequences = q.all()
    seq_ids = [s.id for s in sequences]

    empty = {
        "total_sent": 0,
        "total_opened": 0,
        "total_clicked": 0,
        "total_replied": 0,
        "total_bounced": 0,
        "open_rate": 0.0,
        "click_rate": 0.0,
        "reply_rate": 0.0,
        "bounce_rate": 0.0,
        "sequences": [],
        "by_strategy": [],
    }

    if not seq_ids:
        return empty

    if not seq_ids:
        return empty

    instantly_camps = {}
    camps = db.query(InstantlyCampaign).filter(InstantlyCampaign.sequence_id.in_(seq_ids)).all()
    for c in camps:
        if c.analytics_json:
            instantly_camps[c.sequence_id] = c.analytics_json

    contacts_map: dict[str, Contact] = {}
    if strategy_id:
        for c in db.query(Contact).filter(Contact.strategy_id == strategy_id).all():
            contacts_map[c.id] = c
    else:
        all_strat_ids = list({s.strategy_id for s in sequences if s.strategy_id})
        for c in db.query(Contact).filter(Contact.strategy_id.in_(all_strat_ids)).all():
            contacts_map[c.id] = c

    strategy_map: dict[str, str] = {}
    for s in db.query(Strategy).filter(
        Strategy.id.in_({seq.strategy_id for seq in sequences if seq.strategy_id})
    ).all():
        strategy_map[s.id] = s.product_name

    seq_rows = []
    for seq in sequences:
        ev_agg = (
            db.query(
                OutreachEvent.event_type,
                func.count(OutreachEvent.id).label("cnt"),
            )
            .filter(OutreachEvent.sequence_id == seq.id)
            .group_by(OutreachEvent.event_type)
            .all()
        )
        ev: dict[str, int] = {row.event_type: row.cnt for row in ev_agg}
        if seq.id in instantly_camps:
            a_json = instantly_camps[seq.id]
            ev["sent"] = a_json.get("sent", ev.get("sent", 0))
            ev["opened"] = a_json.get("opened", ev.get("opened", 0))
            ev["clicked"] = a_json.get("clicked", ev.get("clicked", 0))
            ev["replied"] = a_json.get("replied", ev.get("replied", 0))
            ev["bounced"] = a_json.get("bounced", ev.get("bounced", 0))

        c = contacts_map.get(seq.contact_id)
        s_sent = ev.get("sent", 0)
        seq_rows.append(
            {
                "sequence_id": seq.id,
                "contact_name": c.full_name if c else "Unknown",
                "contact_email": c.email if c else None,
                "strategy_name": strategy_map.get(seq.strategy_id or "", ""),
                "status": seq.status,
                "instantly_campaign_id": seq.instantly_campaign_id,
                "sent": s_sent,
                "opened": ev.get("opened", 0),
                "clicked": ev.get("clicked", 0),
                "replied": ev.get("replied", 0),
                "bounced": ev.get("bounced", 0),
                "open_rate": _pct(ev.get("opened", 0), s_sent),
                "reply_rate": _pct(ev.get("replied", 0), s_sent),
            }
        )
    seq_rows.sort(key=lambda x: x["sent"], reverse=True)

    sent = sum(r["sent"] for r in seq_rows)
    opened = sum(r["opened"] for r in seq_rows)
    clicked = sum(r["clicked"] for r in seq_rows)
    replied = sum(r["replied"] for r in seq_rows)
    bounced = sum(r["bounced"] for r in seq_rows)

    by_strategy_agg: dict[str, dict[str, int]] = {}
    for seq in sequences:
        sid = seq.strategy_id or ""
        if sid not in by_strategy_agg:
            by_strategy_agg[sid] = {
                "sent": 0, "opened": 0, "clicked": 0, "replied": 0, "bounced": 0
            }
        for row in seq_rows:
            if row["sequence_id"] == seq.id:
                for k in ("sent", "opened", "clicked", "replied", "bounced"):
                    by_strategy_agg[sid][k] += row[k]

    by_strategy = []
    for sid, ev in by_strategy_agg.items():
        s_sent = ev["sent"]
        by_strategy.append(
            {
                "strategy_id": sid,
                "strategy_name": strategy_map.get(sid, "Unknown"),
                "sent": s_sent,
                "opened": ev["opened"],
                "clicked": ev["clicked"],
                "replied": ev["replied"],
                "bounced": ev["bounced"],
                "open_rate": _pct(ev["opened"], s_sent),
                "reply_rate": _pct(ev["replied"], s_sent),
            }
        )
    by_strategy.sort(key=lambda x: x["sent"], reverse=True)

    return {
        "total_sent": sent,
        "total_opened": opened,
        "total_clicked": clicked,
        "total_replied": replied,
        "total_bounced": bounced,
        "open_rate": _pct(opened, sent),
        "click_rate": _pct(clicked, sent),
        "reply_rate": _pct(replied, sent),
        "bounce_rate": _pct(bounced, sent),
        "sequences": seq_rows,
        "by_strategy": by_strategy,
    }
