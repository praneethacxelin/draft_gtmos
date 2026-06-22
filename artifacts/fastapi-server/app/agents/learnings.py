"""Centralized learnings — the GTM Factory's durable memory.

Every workstream produces insights worth keeping: which experiment facets won,
which persona converts, what messaging landed. Rather than letting those die
inside one batch's ``analysis_json``, we distill them into ``Learning`` rows.

Each learning's text is embedded into the ChromaDB ``gtm_learnings`` collection
(see ``app/services/vector_store.py``) so later steps can recall *semantically*
similar lessons — even across strategies. Everything degrades gracefully: if the
vector store is unavailable, the learning still persists in Postgres and search
falls back to a keyword filter.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.db import Learning, ExperimentBatch, Experiment, gen_id, now
from app.services.vector_store import store
from app.agents.persona_intelligence import compute_persona_intelligence

log = logging.getLogger("gtm.learnings")

CATEGORIES = {
    "persona",
    "segment",
    "messaging",
    "timing",
    "experiment",
    "channel",
    "general",
}
SOURCES = {"experiment", "persona", "outreach", "roi", "manual"}
CONFIDENCE_LEVELS = {"High", "Moderate", "Low"}


# --------------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------------- #

def serialize_learning(l: Learning, *, similarity: Optional[float] = None) -> dict:
    out = {
        "id": l.id,
        "strategy_id": l.strategy_id,
        "category": l.category,
        "title": l.title,
        "content": l.content,
        "source": l.source,
        "source_ref": l.source_ref,
        "metrics": l.metrics_json or {},
        "tags": l.tags_json or [],
        "confidence": l.confidence,
        "embedded": bool(l.embedded),
        "created_at": l.created_at.isoformat() if l.created_at else None,
        "updated_at": l.updated_at.isoformat() if l.updated_at else None,
    }
    if similarity is not None:
        out["similarity"] = similarity
    return out


def _learning_meta(l: Learning) -> dict:
    return {
        "strategy_id": l.strategy_id or "",
        "category": l.category or "general",
        "source": l.source or "manual",
        "confidence": l.confidence or "Moderate",
    }


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #

def record_learning(
    db: Session,
    *,
    content: str,
    category: str = "general",
    title: Optional[str] = None,
    strategy_id: Optional[str] = None,
    source: str = "manual",
    source_ref: Optional[str] = None,
    metrics: Optional[dict] = None,
    tags: Optional[list[str]] = None,
    confidence: str = "Moderate",
    dedupe: bool = True,
) -> Optional[dict]:
    """Create + embed a learning. Returns the serialized row (or None if empty).

    When ``dedupe`` is on, an identical (strategy, source_ref, content) learning
    is reused instead of inserting a duplicate — so re-running a capture step is
    idempotent.
    """
    content = (content or "").strip()
    if not content:
        return None
    category = category if category in CATEGORIES else "general"
    source = source if source in SOURCES else "manual"
    confidence = confidence if confidence in CONFIDENCE_LEVELS else "Moderate"

    if dedupe:
        existing = (
            db.query(Learning)
            .filter(
                Learning.strategy_id == strategy_id,
                Learning.source_ref == source_ref,
                Learning.content == content,
            )
            .first()
        )
        if existing:
            return serialize_learning(existing)

    row = Learning(
        id=gen_id(),
        strategy_id=strategy_id,
        category=category,
        title=(title or "").strip() or None,
        content=content,
        source=source,
        source_ref=source_ref,
        metrics_json=metrics or None,
        tags_json=tags or None,
        confidence=confidence,
        embedded=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    # Best-effort embedding — never blocks persistence.
    embed_text = f"{row.title}. {row.content}" if row.title else row.content
    if store.add_learning(row.id, embed_text, _learning_meta(row)):
        row.embedded = True
        db.commit()
        db.refresh(row)

    return serialize_learning(row)


def list_learnings(
    db: Session,
    *,
    strategy_id: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    q = db.query(Learning)
    if strategy_id:
        q = q.filter(Learning.strategy_id == strategy_id)
    if category:
        q = q.filter(Learning.category == category)
    if source:
        q = q.filter(Learning.source == source)
    rows = q.order_by(Learning.created_at.desc()).limit(max(1, min(limit, 500))).all()
    return [serialize_learning(r) for r in rows]


def search_learnings(
    db: Session,
    *,
    query: str,
    strategy_id: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 8,
) -> list[dict]:
    """Semantic search with a keyword fallback.

    Tries the vector store first (cross-strategy recall by meaning). If it is
    disabled or returns nothing, falls back to a case-insensitive substring
    match so the feature still works offline.
    """
    query = (query or "").strip()
    if not query:
        return list_learnings(db, strategy_id=strategy_id, category=category, limit=limit)

    where: Optional[dict] = None
    filters = []
    if strategy_id:
        filters.append({"strategy_id": strategy_id})
    if category:
        filters.append({"category": category})
    if len(filters) == 1:
        where = filters[0]
    elif len(filters) > 1:
        where = {"$and": filters}

    hits = store.search_learnings(query, n_results=max(1, min(limit, 50)), where=where)
    if hits:
        by_id = {h["id"]: h for h in hits}
        rows = db.query(Learning).filter(Learning.id.in_(list(by_id.keys()))).all()
        out = [
            serialize_learning(r, similarity=by_id[r.id]["similarity"])
            for r in rows
        ]
        out.sort(key=lambda x: x.get("similarity") or 0, reverse=True)
        if out:
            return out

    # Keyword fallback.
    q = db.query(Learning).filter(Learning.content.ilike(f"%{query}%"))
    if strategy_id:
        q = q.filter(Learning.strategy_id == strategy_id)
    if category:
        q = q.filter(Learning.category == category)
    rows = q.order_by(Learning.created_at.desc()).limit(max(1, min(limit, 50))).all()
    return [serialize_learning(r) for r in rows]


def delete_learning(db: Session, learning_id: str) -> bool:
    row = db.query(Learning).filter(Learning.id == learning_id).first()
    if not row:
        return False
    store.delete_learning(learning_id)
    db.delete(row)
    db.commit()
    return True


# --------------------------------------------------------------------------- #
# Auto-capture from other workstreams
# --------------------------------------------------------------------------- #

def capture_from_experiment_batch(db: Session, batch_id: str) -> list[dict]:
    """Distill an analyzed experiment batch into durable learnings.

    Pulls the winning-parameters insight, the why-best rationale, and any
    recommendations out of ``analysis_json`` and stores them as ``experiment``
    learnings tagged with the winning facets.
    """
    batch = db.query(ExperimentBatch).filter(ExperimentBatch.id == batch_id).first()
    if not batch or batch.status != "analyzed":
        return []
    analysis = batch.analysis_json or {}
    captured: list[dict] = []

    best_exp = None
    if batch.best_experiment_id:
        best_exp = (
            db.query(Experiment)
            .filter(Experiment.id == batch.best_experiment_id)
            .first()
        )

    facet_tags: list[str] = []
    metrics: dict = {}
    if best_exp:
        params = best_exp.params_json or {}
        for key in ("industries", "locations", "seniorities", "titles", "employee_ranges"):
            vals = params.get(key)
            if isinstance(vals, list):
                facet_tags.extend(str(v) for v in vals[:3])
        rel = best_exp.relevancy_json or {}
        metrics = {
            "composite_score": best_exp.score,
            "relevancy_score": rel.get("relevancy_score"),
            "lead_count": len((best_exp.leads_json or [])),
        }

    insight = (analysis.get("winning_parameters_insight") or "").strip()
    if insight:
        title = f"Winning facets — {best_exp.name}" if best_exp else "Winning experiment facets"
        rec = record_learning(
            db,
            content=insight,
            category="experiment",
            title=title,
            strategy_id=batch.strategy_id,
            source="experiment",
            source_ref=batch.id,
            metrics=metrics or None,
            tags=facet_tags or None,
            confidence="High",
        )
        if rec:
            captured.append(rec)

    why = (analysis.get("why_best") or "").strip()
    if why:
        rec = record_learning(
            db,
            content=why,
            category="experiment",
            title="Why the winning experiment won",
            strategy_id=batch.strategy_id,
            source="experiment",
            source_ref=batch.id,
            metrics=metrics or None,
            tags=facet_tags or None,
            confidence="Moderate",
        )
        if rec:
            captured.append(rec)

    for r in (analysis.get("recommendations") or [])[:5]:
        r = (r or "").strip() if isinstance(r, str) else ""
        if not r:
            continue
        rec = record_learning(
            db,
            content=r,
            category="experiment",
            title="Experiment recommendation",
            strategy_id=batch.strategy_id,
            source="experiment",
            source_ref=batch.id,
            confidence="Moderate",
        )
        if rec:
            captured.append(rec)

    return captured


def capture_from_persona(db: Session, strategy_id: str) -> list[dict]:
    """Distill persona intelligence into a learning about who converts best."""
    intel = compute_persona_intelligence(db, strategy_id)
    personas = intel.get("personas") or []
    top = intel.get("top_performer")
    if not top or not personas:
        return []

    top_row = next((p for p in personas if p.get("persona_type") == top), personas[0])
    label = top_row.get("label") or top
    reply = top_row.get("reply_rate_pct")
    depth = top_row.get("avg_funnel_depth")
    score = top_row.get("score")

    bits = [f"{label} is the strongest-performing persona"]
    if reply is not None:
        bits.append(f"first-response rate {reply}%")
    if depth is not None:
        bits.append(f"average funnel depth {depth}")
    content = ", ".join(bits) + ". Prioritise this persona in prospecting allocation."

    rec = record_learning(
        db,
        content=content,
        category="persona",
        title=f"Top persona — {label}",
        strategy_id=strategy_id,
        source="persona",
        source_ref=strategy_id,
        metrics={
            "score": score,
            "reply_rate_pct": reply,
            "avg_funnel_depth": depth,
            "data_basis": intel.get("data_basis"),
        },
        tags=[top],
        confidence="High" if intel.get("data_basis") == "funnel" else "Moderate",
    )
    return [rec] if rec else []
