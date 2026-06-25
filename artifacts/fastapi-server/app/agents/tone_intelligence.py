"""Tone × Persona intelligence.

Deterministic analysis of *how email tone correlates with replies for each
buyer persona*. The GTM-engineer hypothesis is that different personas respond
to different writing styles — e.g. a technical tone lands with an IT Manager
while a casual tone lands with a Customer Success Manager. This agent classifies
the tone of every email sequence (no LLM needed), joins it to the contact's
persona and reply outcome, and reports the winning tone per persona.

Read-only: never mutates the DB. All math happens here in Python so the output
never depends on a model's arithmetic.
"""
import re
from collections import defaultdict
from typing import Optional

from sqlalchemy.orm import Session

from app.db import Contact, Sequence, SequenceStep, OutreachEvent

# --- Tone lexicon (word-boundary matched, case-insensitive) ------------------
# Single tokens and multi-word phrases are both supported; phrases match as-is.
_TECHNICAL_TERMS = [
    "api", "apis", "integration", "integrate", "integrations", "architecture",
    "infrastructure", "latency", "throughput", "sla", "slas", "deployment",
    "deploy", "automation", "automate", "automated", "pipeline", "workflow",
    "workflows", "configuration", "configure", "platform", "scalable",
    "scalability", "schema", "webhook", "webhooks", "sdk", "backend", "endpoint",
    "endpoints", "payload", "provisioning", "orchestration", "observability",
    "uptime", "ticket routing", "resolution time", "data model", "rest api",
    "single sign-on", "sso", "rbac", "ci/cd", "kubernetes", "throughput",
]
_CASUAL_MARKERS = [
    "hey", "hi there", "quick", "wanted to", "let's", "grab", "coffee",
    "catch up", "cheers", "thanks", "awesome", "love to", "happy to",
    "no worries", "sounds good", "real quick", "by the way", "btw", "gonna",
    "wanna", "super", "totally",
]
_FORMAL_MARKERS = [
    "dear", "sincerely", "regards", "kind regards", "yours faithfully",
    "pursuant", "hereby", "please find", "i am writing to",
    "with reference to", "esteemed", "respectfully", "cordially",
]

TONE_LABELS = {
    "technical": "Technical",
    "casual": "Casual",
    "formal": "Formal",
    "consultative": "Consultative",
}

PERSONA_LABELS = {
    "champion": "Champion",
    "economic_buyer": "Economic Buyer",
    "blocker": "Blocker",
    "influencer": "Influencer",
    "end_user": "End User",
}

# A persona × tone cell needs at least this many contacted sequences before we
# treat its reply rate as a "winning" signal rather than small-sample noise.
MIN_TONE_SAMPLE = 2


def _build_pattern(terms: list[str]) -> "re.Pattern[str]":
    ordered = sorted(set(terms), key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(re.escape(t) for t in ordered) + r")\b")


_TECH_RE = _build_pattern(_TECHNICAL_TERMS)
_CASUAL_RE = _build_pattern(_CASUAL_MARKERS)
_FORMAL_RE = _build_pattern(_FORMAL_MARKERS)
_CONTRACTION_RE = re.compile(r"\b\w+'(?:s|re|ll|ve|d|t|m)\b")


def classify_tone(subject: Optional[str], body: Optional[str]) -> str:
    """Classify a single email's tone into technical/casual/formal/consultative.

    Uses lexical density (markers per 100 words) so length doesn't bias the
    result. Falls back to ``consultative`` (balanced professional) when no tone
    dominates.
    """
    text = f"{subject or ''} {body or ''}".lower().strip()
    if not text:
        return "consultative"
    words = re.findall(r"[a-z']+", text)
    n = max(1, len(words))
    scale = 100.0 / n

    tech_d = len(_TECH_RE.findall(text)) * scale
    casual_hits = len(_CASUAL_RE.findall(text)) + len(_CONTRACTION_RE.findall(text)) + text.count("!")
    casual_d = casual_hits * scale
    formal_d = len(_FORMAL_RE.findall(text)) * scale

    label, density = max(
        (("technical", tech_d), ("casual", casual_d), ("formal", formal_d)),
        key=lambda kv: kv[1],
    )
    # Require a minimum density before committing to a strong style.
    if density < 1.0:
        return "consultative"
    return label


def _label(persona_type: Optional[str]) -> str:
    if not persona_type:
        return "Unassigned"
    return PERSONA_LABELS.get(persona_type, persona_type.replace("_", " ").title())


def compute_tone_intelligence(db: Session, strategy_id: str) -> dict:
    """Correlate email tone with reply outcome per persona for a strategy."""
    contacts = db.query(Contact).filter(Contact.strategy_id == strategy_id).all()
    if not contacts:
        return {
            "strategy_id": strategy_id,
            "data_basis": "none",
            "total_sequences": 0,
            "tones": [],
            "personas": [],
            "recommendations": [
                "No contacts yet — run prospecting and outreach to learn which tone each persona responds to."
            ],
        }

    contact_persona = {c.id: (c.persona_type or None) for c in contacts}
    contact_engagement = {c.id: float(c.engagement_score or 0.0) for c in contacts}

    sequences = db.query(Sequence).filter(Sequence.strategy_id == strategy_id).all()
    seq_ids = [s.id for s in sequences]
    seq_to_contact = {s.id: s.contact_id for s in sequences}

    # ---- Classify each sequence's tone from its EMAIL steps ----
    steps_by_seq: dict[str, list[SequenceStep]] = defaultdict(list)
    if seq_ids:
        steps = (
            db.query(SequenceStep)
            .filter(SequenceStep.sequence_id.in_(seq_ids))
            .all()
        )
        for st in steps:
            if (st.channel or "").lower() == "email":
                steps_by_seq[st.sequence_id].append(st)

    contact_tone: dict[str, str] = {}
    for s in sequences:
        email_steps = steps_by_seq.get(s.id, [])
        if not email_steps:
            continue
        subject = " ".join(st.subject or "" for st in email_steps)
        body = " ".join(st.body or "" for st in email_steps)
        contact_tone[s.contact_id] = classify_tone(subject, body)

    # ---- Reply / sent outcome per contact (funnel signal) ----
    sent: dict[str, int] = defaultdict(int)
    replied: dict[str, int] = defaultdict(int)
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
            if ev.event_type == "sent":
                sent[cid] += 1
            elif ev.event_type == "replied":
                replied[cid] += 1

    has_funnel = any(sent.values())
    data_basis = "funnel" if has_funnel else "engagement_proxy"

    def _contacted(cid: str) -> bool:
        # Funnel: a send happened. Proxy: any classified sequence counts.
        return sent.get(cid, 0) > 0 if has_funnel else True

    def _replied(cid: str) -> bool:
        if has_funnel:
            return replied.get(cid, 0) > 0
        # Proxy: treat a clearly engaged contact as a responder.
        return contact_engagement.get(cid, 0.0) >= 50.0

    # ---- Aggregate per persona × tone ----
    # cells[persona][tone] = {"contacted": n, "replied": n}
    cells: dict[Optional[str], dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"contacted": 0, "replied": 0})
    )
    overall: dict[str, dict[str, int]] = defaultdict(lambda: {"contacted": 0, "replied": 0})

    for cid, tone in contact_tone.items():
        if not _contacted(cid):
            continue
        persona = contact_persona.get(cid)
        cell = cells[persona][tone]
        cell["contacted"] += 1
        overall[tone]["contacted"] += 1
        if _replied(cid):
            cell["replied"] += 1
            overall[tone]["replied"] += 1

    total_sequences = sum(o["contacted"] for o in overall.values())

    def _rate(c: dict[str, int]) -> Optional[float]:
        return round(c["replied"] / c["contacted"] * 100, 1) if c["contacted"] else None

    tones_out = [
        {
            "tone": tone,
            "label": TONE_LABELS.get(tone, tone.title()),
            "contacted": c["contacted"],
            "replied": c["replied"],
            "reply_rate_pct": _rate(c),
        }
        for tone, c in sorted(overall.items(), key=lambda kv: -kv[1]["contacted"])
    ]

    personas_out: list[dict] = []
    for persona, tone_map in cells.items():
        rows = []
        for tone, c in tone_map.items():
            rows.append(
                {
                    "tone": tone,
                    "label": TONE_LABELS.get(tone, tone.title()),
                    "contacted": c["contacted"],
                    "replied": c["replied"],
                    "reply_rate_pct": _rate(c),
                }
            )
        rows.sort(key=lambda r: (r["reply_rate_pct"] if r["reply_rate_pct"] is not None else -1), reverse=True)
        # Best tone = highest reply rate among cells with a usable sample.
        ranked = [r for r in rows if r["contacted"] >= MIN_TONE_SAMPLE and r["reply_rate_pct"] is not None]
        best = ranked[0] if ranked else None
        total = sum(r["contacted"] for r in rows)
        personas_out.append(
            {
                "persona_type": persona or "unassigned",
                "label": _label(persona),
                "total": total,
                "best_tone": (
                    {"tone": best["tone"], "label": best["label"], "reply_rate_pct": best["reply_rate_pct"]}
                    if best
                    else None
                ),
                "tones": rows,
            }
        )

    personas_out.sort(key=lambda p: p["total"], reverse=True)

    recommendations = _build_recommendations(personas_out, data_basis)

    return {
        "strategy_id": strategy_id,
        "data_basis": data_basis,
        "total_sequences": total_sequences,
        "tones": tones_out,
        "personas": personas_out,
        "recommendations": recommendations,
    }


def _build_recommendations(personas: list[dict], data_basis: str) -> list[str]:
    recs: list[str] = []
    for p in personas:
        ranked = [
            r for r in p["tones"]
            if r["contacted"] >= MIN_TONE_SAMPLE and r["reply_rate_pct"] is not None
        ]
        if len(ranked) >= 2 and ranked[0]["reply_rate_pct"] > ranked[-1]["reply_rate_pct"]:
            best, worst = ranked[0], ranked[-1]
            recs.append(
                f"Use a {best['label'].lower()} tone for the {p['label']} persona — "
                f"{best['reply_rate_pct']}% reply rate vs {worst['reply_rate_pct']}% for "
                f"{worst['label'].lower()}."
            )
        elif p["best_tone"] is not None:
            bt = p["best_tone"]
            recs.append(
                f"{p['label']} responds best to a {bt['label'].lower()} tone "
                f"({bt['reply_rate_pct']}% reply rate). Gather more sends to confirm."
            )
    if not recs:
        recs.append(
            "Not enough tone-vs-reply signal yet. Send more sequences across personas to "
            "learn which writing style earns the most replies."
        )
    if data_basis == "engagement_proxy":
        recs.append(
            "Based on early engagement scores (few real sends yet) — re-check once outreach has run."
        )
    return recs
