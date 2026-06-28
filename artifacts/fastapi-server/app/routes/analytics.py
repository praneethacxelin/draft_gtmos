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


# Fallbacks used only when the strategy's ROI plan doesn't supply the value.
_DEFAULT_DEAL_SIZE_USD = 10_000.0      # matches roi_validator.DEFAULT_AVERAGE_DEAL_SIZE
_DEFAULT_REPLY_WIN_RATE = 0.25         # reply -> closed-won when ROI has no win rate


def _deal_size_from_roi(roi: dict) -> float:
    """ACV used to value a reply. Prefers the user's ROI input, then the
    benchmark ACV, then a conservative fallback."""
    inputs = roi.get("inputs") if isinstance(roi.get("inputs"), dict) else {}
    bench = roi.get("benchmark") if isinstance(roi.get("benchmark"), dict) else {}
    for v in (inputs.get("average_deal_size_usd"), bench.get("avg_contract_value_usd")):
        try:
            if v and float(v) > 0:
                return float(v)
        except (TypeError, ValueError):
            pass
    return _DEFAULT_DEAL_SIZE_USD


def _win_rate_from_roi(roi: dict) -> tuple[float, str]:
    """Reply -> closed-won probability, taken from the ROI benchmark win rate
    when present (else a conservative default). Returns (rate, source)."""
    bench = roi.get("benchmark") if isinstance(roi.get("benchmark"), dict) else {}
    wr = bench.get("typical_win_rate_pct")
    try:
        if wr is not None and 0 < float(wr) <= 100:
            return round(float(wr) / 100.0, 4), "roi_benchmark"
    except (TypeError, ValueError):
        pass
    return _DEFAULT_REPLY_WIN_RATE, "default"


def _projected_revenue_from_roi(roi: dict) -> float:
    """The plan's expected revenue (what 'tracked' is measured against)."""
    calc = roi.get("calculator") if isinstance(roi.get("calculator"), dict) else {}
    gtm = roi.get("gtm_plan") if isinstance(roi.get("gtm_plan"), dict) else {}
    rev_plan = gtm.get("revenue_plan") if isinstance(gtm.get("revenue_plan"), dict) else {}
    inputs = roi.get("inputs") if isinstance(roi.get("inputs"), dict) else {}
    for v in (
        calc.get("projected_revenue_usd"),
        rev_plan.get("projected_total_usd"),
        inputs.get("expected_revenue_usd"),
    ):
        try:
            if v and float(v) > 0:
                return float(v)
        except (TypeError, ValueError):
            pass
    return 0.0


def compute_revenue_tracking(roi: Optional[dict], replied: int) -> dict:
    """Connect real email responses to expected revenue.

    Each reply is treated as a live conversation/opportunity. We value it with
    the strategy's ACV and apply the ROI win rate to project closed-won revenue,
    then compare that against the ROI plan's projected revenue. This is the
    closed loop the ROI planner itself does NOT compute (it is profile-only)."""
    roi = roi if isinstance(roi, dict) else {}
    deal_size = _deal_size_from_roi(roi)
    win_rate, win_rate_source = _win_rate_from_roi(roi)
    projected = _projected_revenue_from_roi(roi)
    opportunities = int(replied or 0)
    tracked_pipeline = opportunities * deal_size
    tracked_revenue = opportunities * win_rate * deal_size
    return {
        "opportunities": opportunities,
        "deal_size_usd": int(round(deal_size)),
        "win_rate": win_rate,
        "win_rate_source": win_rate_source,
        "tracked_pipeline_usd": int(round(tracked_pipeline)),
        "tracked_revenue_usd": int(round(tracked_revenue)),
        "projected_revenue_usd": int(round(projected)),
        "attainment_pct": _pct(int(round(tracked_revenue)), int(round(projected))) if projected else 0.0,
    }



@router.get("/outreach")
def outreach_analytics(
    strategy_id: Optional[str] = Query(None),
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    q = db.query(Sequence)
    user_strat_ids = []
    if not getattr(user, "is_admin", False):
        user_strat_ids = [
            r[0] for r in db.query(Strategy.id).filter(Strategy.user_id == user.id).all()
        ]

    # Hide draft sequences from analytics since they have no stats
    if strategy_id:
        q = q.filter(Sequence.strategy_id == strategy_id, Sequence.status != "draft")
    else:
        # Scope to the user's own strategies when no filter is given
        if not getattr(user, "is_admin", False):
            q = q.filter(Sequence.strategy_id.in_(user_strat_ids), Sequence.status != "draft")
        else:
            q = q.filter(Sequence.status != "draft")
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
        "revenue_tracking": {
            "opportunities": 0, "deal_size_usd": None, "win_rate": None,
            "win_rate_source": "none", "tracked_pipeline_usd": 0,
            "tracked_revenue_usd": 0, "projected_revenue_usd": 0, "attainment_pct": 0.0,
        },
        "sequences": [],
        "by_strategy": [],
    }

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
    strategy_roi_map: dict[str, dict] = {}
    for s in db.query(Strategy).filter(
        Strategy.id.in_({seq.strategy_id for seq in sequences if seq.strategy_id})
    ).all():
        strategy_map[s.id] = s.product_name
        if isinstance(s.roi_json, dict):
            strategy_roi_map[s.id] = s.roi_json

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
                "contact_id": seq.contact_id,
                "contact_name": c.full_name if c else "Unknown",
                "contact_email": c.email if c else None,
                "email_verified": c.email_verified if c else None,
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
        
    # --- Fetch Live Workspace Campaigns to fill gaps ---
    from app.services import settings_service, clients
    instantly_key = settings_service.get_key(db, user.id, "instantly")
    if instantly_key:
        try:
            ws_camps = clients.instantly_get_campaigns(instantly_key) or []
            analytics_res = clients.instantly_get_analytics(instantly_key)
            import json
            try:
                with open("analytics_dump.json", "w") as f:
                    json.dump(analytics_res, f)
            except:
                pass
            analytics_list = []
            if isinstance(analytics_res, dict):
                analytics_list = analytics_res.get("data") or []
            elif isinstance(analytics_res, list):
                analytics_list = analytics_res
            analytics_map = {a["campaign_id"]: a for a in analytics_list if isinstance(a, dict) and "campaign_id" in a}
            
            # 1. Update existing DB sequence rows with live stats
            # First, count how many sequences share each instantly_campaign_id
            cid_counts = {}
            for row in seq_rows:
                cid = row.get("instantly_campaign_id")
                if cid:
                    cid_counts[cid] = cid_counts.get(cid, 0) + 1

            cid_remainders = {}

            for row in seq_rows:
                cid = row.get("instantly_campaign_id")
                if cid and cid in analytics_map:
                    anal = analytics_map[cid]
                    count = cid_counts.get(cid, 1)
                    
                    if cid not in cid_remainders:
                        cid_remainders[cid] = {
                            "sent": anal.get("emails_sent_count", 0),
                            "opened": anal.get("open_count", 0),
                            "clicked": anal.get("link_click_count", 0),
                            "replied": anal.get("reply_count", 0),
                            "bounced": anal.get("bounced_count", 0)
                        }
                    
                    rem = cid_remainders[cid]
                    
                    if row["sent"] == 0 and anal.get("emails_sent_count", 0) > 0:
                        s = rem["sent"] // count + (1 if rem["sent"] % count > 0 else 0)
                        o = rem["opened"] // count + (1 if rem["opened"] % count > 0 else 0)
                        c = rem["clicked"] // count + (1 if rem["clicked"] % count > 0 else 0)
                        r = rem["replied"] // count + (1 if rem["replied"] % count > 0 else 0)
                        b = rem["bounced"] // count + (1 if rem["bounced"] % count > 0 else 0)
                        
                        row["sent"] = s
                        row["opened"] = o
                        row["clicked"] = c
                        row["replied"] = r
                        row["bounced"] = b
                        row["open_rate"] = _pct(row["opened"], row["sent"])
                        row["reply_rate"] = _pct(row["replied"], row["sent"])
                        
                        rem["sent"] = max(0, rem["sent"] - s)
                        rem["opened"] = max(0, rem["opened"] - o)
                        rem["clicked"] = max(0, rem["clicked"] - c)
                        rem["replied"] = max(0, rem["replied"] - r)
                        rem["bounced"] = max(0, rem["bounced"] - b)
                        cid_counts[cid] -= 1

            # 2. Add remaining workspace campaigns to show campaign-level aggregates
            # We don't skip them anymore so the user can see both lead-level and campaign-level stats
            for c in ws_camps:
                cid = c.get("id")
                if not cid:
                    continue
                anal = analytics_map.get(cid) or {}
                
                # In Instantly, email_list is the sender emails, not the leads. We cannot match contacts this way.
                # Always display it as a campaign aggregate.
                assigned_strategy = strategy_id or (user_strat_ids[0] if user_strat_ids else None)
                
                if strategy_id and assigned_strategy != strategy_id:
                    continue
                if not getattr(user, "is_admin", False) and assigned_strategy not in user_strat_ids:
                    continue

                s_sent = anal.get("emails_sent_count", 0) or 0
                opened = anal.get("open_count", 0) or 0
                clicked = anal.get("link_click_count", 0) or 0
                replied = anal.get("reply_count", 0) or 0
                bounced = anal.get("bounced_count", 0) or 0
                
                c_name = c.get("name", "Workspace Campaign")
                seq_rows.append({
                    "sequence_id": f"ws-{cid}",
                    "contact_id": None,
                    "contact_name": f"Campaign: {c_name}",
                    "contact_email": "(Campaign Aggregate)",
                    "email_verified": None,
                    "strategy_name": strategy_map.get(assigned_strategy, "Unknown Strategy") if assigned_strategy else "Workspace Campaign",
                    "status": "active",
                    "instantly_campaign_id": cid,
                    "sent": s_sent,
                    "opened": opened,
                    "clicked": clicked,
                    "replied": replied,
                    "bounced": bounced,
                    "open_rate": _pct(opened, s_sent),
                    "reply_rate": _pct(replied, s_sent),
                    "is_campaign_aggregate": True
                })
        except Exception as e:
            pass
            
    seq_rows.sort(key=lambda x: x["sent"], reverse=True)

    # Calculate top-level totals, ignoring the campaign aggregate rows to prevent double-counting
    lead_rows = [r for r in seq_rows if not r.get("is_campaign_aggregate")]
    
    sent = sum(r["sent"] for r in lead_rows)
    opened = sum(r["opened"] for r in lead_rows)
    clicked = sum(r["clicked"] for r in lead_rows)
    replied = sum(r["replied"] for r in lead_rows)
    bounced = sum(r["bounced"] for r in lead_rows)

    by_strategy_agg: dict[str, dict[str, int]] = {}
    for row in seq_rows:
        # Determine strategy ID from row directly if injected by workspace fetch, else match sequences
        sid = row.get("_strategy_id")
        if not sid:
            matching_seq = next((s for s in sequences if s.id == row["sequence_id"]), None)
            sid = matching_seq.strategy_id if matching_seq else ""
        sid = sid or ""
        
        if sid not in by_strategy_agg:
            by_strategy_agg[sid] = {
                "sent": 0, "opened": 0, "clicked": 0, "replied": 0, "bounced": 0
            }
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
                "revenue_tracking": compute_revenue_tracking(
                    strategy_roi_map.get(sid), ev["replied"]
                ),
            }
        )
    by_strategy.sort(key=lambda x: x["sent"], reverse=True)

    # Overall revenue tracking. When scoped to one strategy use its ROI plan;
    # otherwise roll up the per-strategy tracked figures so the workspace total
    # reconciles with the per-strategy rows.
    if strategy_id and strategy_id in strategy_roi_map:
        revenue_tracking = compute_revenue_tracking(strategy_roi_map[strategy_id], replied)
    else:
        revenue_tracking = {
            "opportunities": sum(r["revenue_tracking"]["opportunities"] for r in by_strategy),
            "deal_size_usd": None,
            "win_rate": None,
            "win_rate_source": "mixed",
            "tracked_pipeline_usd": sum(r["revenue_tracking"]["tracked_pipeline_usd"] for r in by_strategy),
            "tracked_revenue_usd": sum(r["revenue_tracking"]["tracked_revenue_usd"] for r in by_strategy),
            "projected_revenue_usd": sum(r["revenue_tracking"]["projected_revenue_usd"] for r in by_strategy),
            "attainment_pct": 0.0,
        }
        if revenue_tracking["projected_revenue_usd"]:
            revenue_tracking["attainment_pct"] = _pct(
                revenue_tracking["tracked_revenue_usd"], revenue_tracking["projected_revenue_usd"]
            )

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
        "revenue_tracking": revenue_tracking,
        "sequences": seq_rows,
        "by_strategy": by_strategy,
    }
