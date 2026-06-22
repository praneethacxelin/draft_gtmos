"""Persona Intelligence Scoring.

Deterministic, funnel-based scoring of how each buyer persona
(champion / economic_buyer / blocker / …) actually performs across the GTM
funnel for a given strategy. All math happens here in Python so the score
never depends on a model's arithmetic.

The score rewards:
  * response rate (replies / sends) and open rate,
  * funnel progression depth (how far contacts of a persona advance),
  * conversion outcomes and conversion value,
  * response speed (faster first reply scores higher).

When live funnel events are sparse, the score gracefully falls back to the
contact-level engagement / total scores already stored on each ``Contact`` so
the output stays meaningful with synthetic or early-stage data.
"""
from collections import defaultdict
from typing import Optional

from sqlalchemy.orm import Session

from app.db import (
    Contact,
    Sequence,
    OutreachEvent,
    QualificationRecord,
    AttributionEvent,
)

# Ordered funnel stages — index == depth reached.
FUNNEL_STAGES = [
    "identified",
    "contacted",
    "opened",
    "engaged",      # clicked or replied
    "qualified",    # mql / sql
    "converting",   # demo_booked / trial_started
    "won",          # deal_created
]
STAGE_INDEX = {name: i for i, name in enumerate(FUNNEL_STAGES)}
MAX_STAGE = len(FUNNEL_STAGES) - 1

# Score weighting (sums to 1.0).
W_RESPONSE = 0.30
W_DEPTH = 0.30
W_CONVERSION = 0.25
W_SPEED = 0.15

# A reply within this many hours earns full speed credit; slower decays to 0.
SPEED_FULL_CREDIT_HOURS = 24.0
SPEED_ZERO_CREDIT_HOURS = 14 * 24.0  # two weeks

# Default prospecting split across the top-ranked personas: the strongest
# persona gets 70% of the Apollo asks, the second-strongest 30%. Configurable.
DEFAULT_PERSONA_WEIGHTS = [0.70, 0.30]

PERSONA_LABELS = {
    "champion": "Champion",
    "economic_buyer": "Economic Buyer",
    "blocker": "Blocker",
    "influencer": "Influencer",
    "end_user": "End User",
}


def _grade(score: float) -> str:
    if score >= 75:
        return "High performing"
    if score >= 50:
        return "Solid"
    if score >= 30:
        return "Developing"
    return "Underperforming"


def _confidence(contact_count: int, event_count: int) -> str:
    """How much to trust the score given how much real signal backs it."""
    if contact_count >= 10 and event_count >= 20:
        return "High"
    if contact_count >= 3 and event_count >= 3:
        return "Moderate"
    return "Low"


def _label(persona_type: Optional[str]) -> str:
    if not persona_type:
        return "Unassigned"
    return PERSONA_LABELS.get(persona_type, persona_type.replace("_", " ").title())


def compute_persona_intelligence(db: Session, strategy_id: str) -> dict:
    """Aggregate funnel performance per persona for a strategy.

    Returns a dict persisted/served as-is. Read-only: never mutates the DB.
    """
    contacts = (
        db.query(Contact).filter(Contact.strategy_id == strategy_id).all()
    )

    if not contacts:
        return {
            "strategy_id": strategy_id,
            "persona_count": 0,
            "total_contacts": 0,
            "personas": [],
            "top_performer": None,
            "lowest_performer": None,
            "recommendations": [
                "No contacts found yet — run prospecting to populate persona data."
            ],
        }

    contact_persona = {c.id: (c.persona_type or None) for c in contacts}
    contacts_by_persona: dict[Optional[str], list[Contact]] = defaultdict(list)
    for c in contacts:
        contacts_by_persona[c.persona_type or None].append(c)

    # ---- Map sequences -> contact, and gather first sent/reply timestamps ----
    sequences = (
        db.query(Sequence).filter(Sequence.strategy_id == strategy_id).all()
    )
    seq_to_contact = {s.id: s.contact_id for s in sequences}
    seq_ids = list(seq_to_contact.keys())

    # Per-contact event tallies.
    sent = defaultdict(int)
    opened = defaultdict(int)
    clicked = defaultdict(int)
    replied = defaultdict(int)
    bounced = defaultdict(int)
    first_sent: dict[str, object] = {}
    first_reply: dict[str, object] = {}

    if seq_ids:
        events = (
            db.query(OutreachEvent)
            .filter(OutreachEvent.sequence_id.in_(seq_ids))
            .all()
        )
        for ev in events:
            cid = seq_to_contact.get(ev.sequence_id)
            if not cid:
                continue
            et = ev.event_type
            if et == "sent":
                sent[cid] += 1
                if ev.occurred_at and (cid not in first_sent or ev.occurred_at < first_sent[cid]):
                    first_sent[cid] = ev.occurred_at
            elif et == "opened":
                opened[cid] += 1
            elif et == "clicked":
                clicked[cid] += 1
            elif et == "replied":
                replied[cid] += 1
                if ev.occurred_at and (cid not in first_reply or ev.occurred_at < first_reply[cid]):
                    first_reply[cid] = ev.occurred_at
            elif et == "bounced":
                bounced[cid] += 1

    # ---- Qualification (mql/sql/nurture) per contact ----
    qual = (
        db.query(QualificationRecord)
        .filter(QualificationRecord.strategy_id == strategy_id)
        .all()
    )
    qualified_contacts: dict[str, str] = {}
    for q in qual:
        # Keep the strongest status seen (sql > mql > nurture).
        rank = {"nurture": 1, "mql": 2, "sql": 3}
        prev = qualified_contacts.get(q.contact_id)
        if prev is None or rank.get(q.status, 0) > rank.get(prev, 0):
            qualified_contacts[q.contact_id] = q.status

    # ---- Attribution / conversions per contact ----
    attr = (
        db.query(AttributionEvent)
        .filter(AttributionEvent.strategy_id == strategy_id)
        .all()
    )
    conv_rank = {"demo_booked": 5, "trial_started": 5, "deal_created": 6}
    contact_conversion_stage: dict[str, int] = {}
    contact_conversion_value: dict[str, float] = defaultdict(float)
    for a in attr:
        if not a.contact_id:
            continue
        stage = conv_rank.get(a.conversion_event)
        if stage is not None:
            contact_conversion_stage[a.contact_id] = max(
                contact_conversion_stage.get(a.contact_id, 0), stage
            )
        contact_conversion_value[a.contact_id] += float(a.conversion_value or 0.0)

    def _contact_stage(cid: str) -> int:
        """Furthest funnel stage a single contact reached."""
        stage = STAGE_INDEX["identified"]
        if sent.get(cid):
            stage = STAGE_INDEX["contacted"]
        if opened.get(cid):
            stage = max(stage, STAGE_INDEX["opened"])
        if clicked.get(cid) or replied.get(cid):
            stage = max(stage, STAGE_INDEX["engaged"])
        if cid in qualified_contacts:
            stage = max(stage, STAGE_INDEX["qualified"])
        conv = contact_conversion_stage.get(cid)
        if conv == 6:
            stage = max(stage, STAGE_INDEX["won"])
        elif conv == 5:
            stage = max(stage, STAGE_INDEX["converting"])
        return stage

    personas: list[dict] = []
    for persona_type, plist in contacts_by_persona.items():
        n = len(plist)
        ids = [c.id for c in plist]

        p_sent = sum(sent.get(i, 0) for i in ids)
        p_opened = sum(opened.get(i, 0) for i in ids)
        p_clicked = sum(clicked.get(i, 0) for i in ids)
        p_replied = sum(replied.get(i, 0) for i in ids)
        p_bounced = sum(bounced.get(i, 0) for i in ids)
        event_count = p_sent + p_opened + p_clicked + p_replied + p_bounced

        open_rate = (p_opened / p_sent) if p_sent else 0.0
        reply_rate = (p_replied / p_sent) if p_sent else 0.0

        qualified = sum(1 for i in ids if i in qualified_contacts)
        sql_count = sum(1 for i in ids if qualified_contacts.get(i) == "sql")
        conversions = sum(1 for i in ids if i in contact_conversion_stage)
        won = sum(1 for i in ids if contact_conversion_stage.get(i) == 6)
        conversion_value = sum(contact_conversion_value.get(i, 0.0) for i in ids)

        # Funnel counts per stage (how many contacts reached at least each stage).
        stage_reached = [_contact_stage(i) for i in ids]
        funnel = []
        for idx, name in enumerate(FUNNEL_STAGES):
            funnel.append(
                {
                    "stage": name,
                    "count": sum(1 for s in stage_reached if s >= idx),
                }
            )
        avg_depth = (sum(stage_reached) / n) if n else 0.0
        depth_pct = avg_depth / MAX_STAGE if MAX_STAGE else 0.0

        # ---- Response speed (avg hours to first reply across contacts that replied)
        speed_hours: list[float] = []
        for i in ids:
            if i in first_sent and i in first_reply and first_reply[i] >= first_sent[i]:
                delta = first_reply[i] - first_sent[i]
                speed_hours.append(delta.total_seconds() / 3600.0)
        avg_speed_hours = (sum(speed_hours) / len(speed_hours)) if speed_hours else None
        if avg_speed_hours is None:
            speed_factor = 0.0
        elif avg_speed_hours <= SPEED_FULL_CREDIT_HOURS:
            speed_factor = 1.0
        elif avg_speed_hours >= SPEED_ZERO_CREDIT_HOURS:
            speed_factor = 0.0
        else:
            span = SPEED_ZERO_CREDIT_HOURS - SPEED_FULL_CREDIT_HOURS
            speed_factor = 1.0 - (avg_speed_hours - SPEED_FULL_CREDIT_HOURS) / span

        # ---- Composite components (0..1) ----
        # Conversion component blends conversion rate and a value signal.
        conv_rate = (conversions / n) if n else 0.0

        live_signal = event_count > 0 or qualified > 0 or conversions > 0
        if live_signal:
            response_component = min(1.0, reply_rate / 0.15)  # 15% reply ≈ excellent
            conversion_component = min(1.0, conv_rate / 0.10)  # 10% of persona converting ≈ excellent
            components = {
                "response": round(response_component, 3),
                "depth": round(depth_pct, 3),
                "conversion": round(conversion_component, 3),
                "speed": round(speed_factor, 3),
            }
            raw = (
                W_RESPONSE * response_component
                + W_DEPTH * depth_pct
                + W_CONVERSION * conversion_component
                + W_SPEED * speed_factor
            )
            basis = "funnel"
        else:
            # Fall back to stored contact-level scores (0..100 or 0..1 tolerant).
            def _norm(v: float) -> float:
                return v / 100.0 if v > 1 else v

            eng = sum(_norm(float(c.engagement_score or 0.0)) for c in plist) / n if n else 0.0
            tot = sum(_norm(float(c.total_score or 0.0)) for c in plist) / n if n else 0.0
            response_component = eng
            conversion_component = tot
            components = {
                "response": round(eng, 3),
                "depth": 0.0,
                "conversion": round(tot, 3),
                "speed": 0.0,
            }
            raw = 0.5 * eng + 0.5 * tot
            basis = "contact_scores"

        score = round(max(0.0, min(1.0, raw)) * 100, 1)

        personas.append(
            {
                "persona_type": persona_type or "unassigned",
                "label": _label(persona_type),
                "contacts": n,
                "score": score,
                "grade": _grade(score),
                "confidence": _confidence(n, event_count),
                "basis": basis,
                "metrics": {
                    "sent": p_sent,
                    "opened": p_opened,
                    "clicked": p_clicked,
                    "replied": p_replied,
                    "bounced": p_bounced,
                    "open_rate_pct": round(open_rate * 100, 1),
                    "reply_rate_pct": round(reply_rate * 100, 1),
                    "qualified": qualified,
                    "sql": sql_count,
                    "conversions": conversions,
                    "won": won,
                    "conversion_value_usd": int(round(conversion_value)),
                    "avg_response_hours": (
                        round(avg_speed_hours, 1) if avg_speed_hours is not None else None
                    ),
                    "avg_funnel_depth": round(avg_depth, 2),
                },
                "components": components,
                "funnel": funnel,
            }
        )

    personas.sort(key=lambda p: p["score"], reverse=True)

    ranked = [p for p in personas if p["contacts"] > 0]
    top = ranked[0] if ranked else None
    lowest = ranked[-1] if len(ranked) > 1 else None

    recommendations = _build_recommendations(personas, top, lowest)

    total_contacts = sum(p["contacts"] for p in personas)
    total_events = sum(p["metrics"]["sent"] + p["metrics"]["replied"] for p in personas)

    return {
        "strategy_id": strategy_id,
        "persona_count": len([p for p in personas if p["contacts"] > 0]),
        "total_contacts": total_contacts,
        "data_basis": "funnel" if total_events > 0 else "contact_scores",
        "personas": personas,
        "top_performer": (
            {"persona_type": top["persona_type"], "label": top["label"], "score": top["score"]}
            if top
            else None
        ),
        "lowest_performer": (
            {
                "persona_type": lowest["persona_type"],
                "label": lowest["label"],
                "score": lowest["score"],
            }
            if lowest
            else None
        ),
        "recommendations": recommendations,
    }


def _build_recommendations(
    personas: list[dict], top: Optional[dict], lowest: Optional[dict]
) -> list[str]:
    recs: list[str] = []
    if not personas:
        return ["No persona data yet — run prospecting and outreach to learn what converts."]

    if top:
        recs.append(
            f"Double down on the {top['label']} persona — it is the strongest performer "
            f"(score {top['score']}). Prioritize and expand prospecting for this profile."
        )
    if lowest and top and lowest["persona_type"] != top["persona_type"]:
        if lowest["score"] < 30:
            recs.append(
                f"Re-evaluate the {lowest['label']} persona (score {lowest['score']}) — it is "
                "under-converting. Refine its messaging or deprioritize it in favor of stronger personas."
            )

    # Stage-specific drop-off guidance for the best-known persona.
    for p in personas:
        if p["contacts"] < 3:
            continue
        m = p["metrics"]
        if m["sent"] >= 5 and m["reply_rate_pct"] < 5:
            recs.append(
                f"{p['label']} has a low reply rate ({m['reply_rate_pct']}%) — test new subject "
                "lines and opening hooks for this persona."
            )
        if m["replied"] > 0 and m["qualified"] == 0:
            recs.append(
                f"{p['label']} replies but none qualify yet — tighten qualification or follow-up cadence."
            )
        if m["avg_response_hours"] is not None and m["avg_response_hours"] > 72:
            recs.append(
                f"{p['label']} takes ~{round(m['avg_response_hours'])}h to first reply — faster "
                "follow-up could lift conversion."
            )

    if not recs:
        recs.append("Persona performance is balanced — keep gathering funnel data to sharpen scoring.")

    # De-duplicate while preserving order.
    seen = set()
    out = []
    for r in recs:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _distribute_counts(total: int, fractions: list[float]) -> list[int]:
    """Split ``total`` into integer parts by ``fractions`` (sum→1).

    The remainder from flooring is handed to the parts with the largest
    fractional component first, so the strongest persona is never starved by
    rounding.
    """
    if total <= 0 or not fractions:
        return [0 for _ in fractions]
    raw = [total * f for f in fractions]
    floors = [int(x) for x in raw]
    remainder = total - sum(floors)
    order = sorted(range(len(fractions)), key=lambda i: raw[i] - floors[i], reverse=True)
    for k in range(remainder):
        floors[order[k % len(order)]] += 1
    return floors


def compute_persona_allocation(
    db: Session,
    strategy_id: str,
    *,
    total_prospects: Optional[int] = None,
    weights: Optional[list[float]] = None,
) -> dict:
    """Allocate prospect discovery across the best-performing personas.

    Ranks personas by their funnel-performance score (which rewards first
    response and engagement depth) and splits prospecting so the strongest
    persona gets the largest share — by default 70% to the top persona and 30%
    to the second. When fewer personas have data than there are weights, the
    weights are renormalized over the personas that exist.
    """
    intel = compute_persona_intelligence(db, strategy_id)
    ranked = [p for p in intel.get("personas", []) if p.get("contacts", 0) > 0]

    # Sanitize weights → positive, descending.
    raw_weights = [
        max(0.0, float(w))
        for w in (weights if weights else DEFAULT_PERSONA_WEIGHTS)
        if w is not None
    ]
    raw_weights = [w for w in raw_weights if w > 0] or list(DEFAULT_PERSONA_WEIGHTS)
    raw_weights.sort(reverse=True)

    n_alloc = min(len(raw_weights), len(ranked))
    selected = ranked[:n_alloc]
    used_weights = raw_weights[:n_alloc]
    wsum = sum(used_weights) or 1.0
    fractions = [w / wsum for w in used_weights]

    counts = (
        _distribute_counts(int(total_prospects), fractions)
        if total_prospects and int(total_prospects) > 0
        else [0] * n_alloc
    )

    allocations = []
    for i, p in enumerate(selected):
        m = p.get("metrics", {})
        allocations.append(
            {
                "persona_type": p["persona_type"],
                "label": p["label"],
                "rank": i + 1,
                "score": p["score"],
                "grade": p["grade"],
                "confidence": p["confidence"],
                "weight_pct": round(fractions[i] * 100, 1),
                "prospect_count": counts[i],
                "reply_rate_pct": m.get("reply_rate_pct"),
                "avg_funnel_depth": m.get("avg_funnel_depth"),
            }
        )

    deprioritized = [
        {"persona_type": p["persona_type"], "label": p["label"], "score": p["score"]}
        for p in ranked[n_alloc:]
    ]

    notes: list[str] = []
    if not ranked:
        notes.append(
            "No persona data yet — run experiments and outreach so the split can be learned "
            "from real first-response and funnel depth."
        )
    elif n_alloc == 1:
        notes.append(
            f"Only the {allocations[0]['label']} persona has data, so it receives 100% of "
            "prospecting until a second persona is validated."
        )
    else:
        top, second = allocations[0], allocations[1]
        notes.append(
            f"{top['label']} leads on first-response + funnel depth (score {top['score']}), so it "
            f"takes {top['weight_pct']}% of Apollo prospecting; {second['label']} takes "
            f"{second['weight_pct']}%."
        )
    if deprioritized:
        names = ", ".join(d["label"] for d in deprioritized)
        notes.append(
            f"Deprioritized for now (outside the top {n_alloc}): {names}. They re-enter the split "
            "if their response/depth improves."
        )

    return {
        "strategy_id": strategy_id,
        "data_basis": intel.get("data_basis"),
        "weights_input": raw_weights,
        "total_prospects": int(total_prospects) if total_prospects else None,
        "allocated_personas": n_alloc,
        "allocations": allocations,
        "deprioritized_personas": deprioritized,
        "notes": notes,
    }
