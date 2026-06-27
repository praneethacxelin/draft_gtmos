"""Closed-loop (live) experiment engine.

The relevancy experiment (``experiments.py``) only proves which Apollo facets
surface the highest-*fit* leads. That is not the same as proving which segment
actually *responds*. This module closes the loop so an experiment batch becomes
a real funnel test:

  1. ``promote_to_live`` — for each analyzed variant, materialize a small real
     contact cohort (from the leads the experiment already pulled, no new Apollo
     cost) tagged ``source="experiment"`` / ``source_ref=<experiment_id>`` and
     draft a personalized sequence per contact. Nothing is sent.
  2. ``launch_variant`` — the engineer clicks send; this launches the drafted
     sequences for one variant via the normal Instantly launch path and opens
     the live window on first launch (``window_started_at`` … ``window_ends_at``).
  3. The hourly Instantly poller (already running) ingests replies / meeting
     bookings into ``EngagementEvent`` + ``QualificationRecord`` as they happen.
  4. ``evaluate_live_batch`` — when the window closes, score every variant by
     its **positive-intent reply rate** (a reply that books a call / meeting =
     ``QualificationRecord.status == "sql"``) and crown the live winner. A
     durable learning is captured.

``simulate_window`` is a hidden, test-only accelerator that synthesizes the
funnel so the whole loop can be observed without waiting a real month.

The winner metric is deliberately *positive intent*, not raw volume or even raw
reply rate: the engineer asked for "a reply that means a booked call/meeting to
move further in the funnel and close a deal".
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.db import (
    Strategy,
    ExperimentBatch,
    Experiment,
    Account,
    Contact,
    Sequence,
    SequenceStep,
    OutreachEvent,
    EngagementEvent,
    QualificationRecord,
    now,
)

log = logging.getLogger("gtm.live_experiment")

# Fallback per-variant budget, only used when a batch somehow has no
# leads_per_experiment. Normally the budget is ANCHORED to the batch's
# leads_per_experiment so the funnel test learns from the same sample size the
# engineer chose to fetch — not a tiny hardcoded slice.
DRAFT_PER_VARIANT = 5

# A variant can promote at most every lead it actually fetched. This matches the
# Apollo leads-per-run ceiling, so the budget never asks for leads an experiment
# could not have pulled.
MAX_LEADS_PER_VARIANT = 25

# Relevancy-aware promotion gates. Promote spends real LLM drafts (and later
# Apollo reveal + outreach), so don't waste it on junk variants.
MIN_RELEVANCY_TO_PROMOTE = 20.0  # below this % fit, a variant is junk — skip it
MIN_LEADS_TO_PROMOTE = 3         # too few leads to form a meaningful cohort

# Default live window if the ROI plan doesn't specify one.
DEFAULT_WINDOW_MONTHS = 1

# Sequence statuses that mean "this variant's contact was actually sent to".
_LAUNCHED_SEQ_STATUSES = ("active", "simulated", "sent")

# A reply counts as a real reply when we see any of these.
_REPLY_OUTREACH_TYPES = ("replied",)
_REPLY_ENGAGEMENT_TYPES = ("email_reply", "replied", "reply")

# QualificationRecord.status that represents positive forward-movement.
_POSITIVE_STATUS = "sql"   # meeting booked / wants to move forward
_INTERESTED_STATUS = "mql"  # replied with interest, not yet a meeting


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _window_months(db: Session, strategy: Strategy) -> int:
    """Live window length — prefer the ROI experiment plan, else the default."""
    try:
        gtm = (strategy.roi_json or {}).get("gtm_plan") if strategy.roi_json else None
        plan = (gtm or {}).get("experiment_plan") if isinstance(gtm, dict) else None
        wm = int((plan or {}).get("window_months")) if isinstance(plan, dict) else 0
        if wm > 0:
            return wm
    except Exception:
        pass
    return DEFAULT_WINDOW_MONTHS


def _variant_contacts(db: Session, batch: ExperimentBatch, exp: Experiment) -> list[Contact]:
    return (
        db.query(Contact)
        .filter(
            Contact.strategy_id == batch.strategy_id,
            Contact.source == "experiment",
            Contact.source_ref == exp.id,
        )
        .all()
    )


def _serialize_metrics(exp: Experiment, m: dict) -> dict:
    return {
        "experiment_id": exp.id,
        "name": exp.name,
        "idx": exp.idx,
        "cohort_size": exp.cohort_size or 0,
        "launched": bool(exp.live_launched_at),
        **m,
    }


# ---------------------------------------------------------------------------
# Promotion allocation — how many leads each variant moves into the funnel test
# ---------------------------------------------------------------------------

def _variant_budget(batch: ExperimentBatch, draft_per_variant: Optional[int]) -> int:
    """Per-variant promotion budget (the share the TOP variant may promote).

    Anchored to the leads the engineer chose to fetch per experiment so the
    funnel test learns from a meaningful sample, not a tiny hardcoded slice.
    An explicit engineer override wins; otherwise the batch's
    ``leads_per_experiment`` is used.
    """
    budget = draft_per_variant or batch.leads_per_experiment or DRAFT_PER_VARIANT
    return max(1, min(int(budget), MAX_LEADS_PER_VARIANT))


def _plan_allocation(
    experiments: list[Experiment], winner_id: Optional[str], budget: int
) -> list[dict]:
    """Decide how many leads each variant promotes, distributed by composite score.

    The top-scoring (winner) variant gets the full ``budget``; every other
    variant gets a share proportional to its composite score, then clamped to
    the leads it actually fetched — never inventing leads, never silently
    wasting the ones already paid for. Junk variants that fail the quality gate
    are marked skipped (the analyzed winner is never skipped). This is the
    single source of truth used by both the preview and the real promotion.
    """
    rows: list[dict] = []
    eligible_scores: list[float] = []
    for exp in experiments:
        rel = exp.relevancy_json or {}
        rel_raw = rel.get("relevancy_score")
        has_score = isinstance(rel_raw, (int, float))
        relevancy = float(rel_raw) if has_score else None
        lead_count = len(exp.leads_json or [])
        is_winner = bool(winner_id and exp.id == winner_id)
        composite = float(exp.score) if isinstance(exp.score, (int, float)) else 0.0

        reason: Optional[str] = None
        if not is_winner:
            if lead_count < MIN_LEADS_TO_PROMOTE:
                reason = f"only {lead_count} leads (< {MIN_LEADS_TO_PROMOTE})"
            elif has_score and relevancy is not None and relevancy < MIN_RELEVANCY_TO_PROMOTE:
                reason = f"relevancy {relevancy:.0f}% (< {MIN_RELEVANCY_TO_PROMOTE:.0f}%)"

        rows.append({
            "experiment_id": exp.id,
            "name": exp.name,
            "idx": exp.idx,
            "is_winner": is_winner,
            "relevancy": rel_raw if has_score else None,
            "composite_score": round(composite, 1),
            "available_leads": lead_count,
            "skipped": bool(reason),
            "reason": reason,
            "planned": 0,
        })
        if not reason:
            eligible_scores.append(composite)

    # The highest composite among gate-passing variants anchors the scale, so the
    # leader promotes its full available cohort and the rest scale down smoothly.
    max_score = max(eligible_scores, default=0.0)
    for row in rows:
        if row["skipped"]:
            continue
        if max_score > 0:
            share = budget * (row["composite_score"] / max_score)
        else:
            share = budget  # no usable scores — give every passing variant the full budget
        planned = int(round(share))
        planned = max(1, min(planned, row["available_leads"], budget))
        row["planned"] = planned
    return rows


# ---------------------------------------------------------------------------
# 1. Promote an analyzed batch to a live funnel test
# ---------------------------------------------------------------------------

async def promote_to_live(
    db: Session, batch_id: str, draft_per_variant: Optional[int] = None
) -> dict:
    """Materialize a real cohort + draft sequences for every analyzed variant.

    Reuses the leads each experiment already pulled (no new Apollo spend). Does
    NOT send anything — the engineer launches each variant explicitly.
    """
    from app.agents.s3_outreach import generate_sequence

    batch = db.query(ExperimentBatch).filter(ExperimentBatch.id == batch_id).first()
    if not batch:
        return {"_error": "Experiment batch not found"}
    if batch.status != "analyzed":
        return {"_error": "Analyze the batch first — a live test runs the analyzed variants."}

    strategy = db.query(Strategy).filter(Strategy.id == batch.strategy_id).first()
    if not strategy:
        return {"_error": "Strategy not found"}

    experiments = (
        db.query(Experiment)
        .filter(Experiment.batch_id == batch.id, Experiment.status == "done")
        .order_by(Experiment.idx.asc())
        .all()
    )
    if not experiments:
        return {"_error": "Run the experiments first — there are no leads to test."}

    budget = _variant_budget(batch, draft_per_variant)
    plan = _plan_allocation(experiments, batch.best_experiment_id, budget)
    plan_by_id = {p["experiment_id"]: p for p in plan}

    # Cache existing accounts by company so we don't duplicate them.
    accounts_by_company: dict[str, Account] = {
        a.company_name: a
        for a in db.query(Account).filter(Account.strategy_id == batch.strategy_id).all()
    }

    total_contacts = 0
    total_drafts = 0
    per_variant: list[dict] = []
    skipped: list[dict] = []

    for exp in experiments:
        alloc = plan_by_id.get(exp.id) or {}
        # Quality gate — the analyzed winner is always promoted; every other
        # variant must clear the bar so we don't draft/launch into junk.
        if alloc.get("skipped"):
            skipped.append(
                {"experiment_id": exp.id, "name": exp.name, "reason": alloc.get("reason")}
            )
            continue

        rel = exp.relevancy_json or {}
        rel_raw = rel.get("relevancy_score")
        has_score = isinstance(rel_raw, (int, float))
        is_winner = bool(alloc.get("is_winner"))
        # Leads promoted = score-proportional share of the budget, clamped to the
        # leads this variant actually fetched (no silent waste). The winner — the
        # top composite score — naturally promotes its full available cohort.
        variant_cap = max(1, int(alloc.get("planned") or 1))

        # Re-promoting is idempotent: keep an existing cohort, just top up drafts.
        existing = _variant_contacts(db, batch, exp)
        existing_names = {(c.full_name or "").lower() for c in existing}
        cohort: list[Contact] = list(existing)

        leads = exp.leads_json or []
        for lead in leads:
            if len(cohort) >= variant_cap:
                break
            name = (lead.get("name") or "").strip()
            if not name or name.lower() in existing_names:
                continue
            company = lead.get("company") or "Unknown Co"
            account = accounts_by_company.get(company)
            if not account:
                account = Account(
                    user_id=strategy.user_id,
                    strategy_id=batch.strategy_id,
                    company_name=company,
                    domain=lead.get("domain"),
                    industry=lead.get("industry"),
                    employee_count=lead.get("employee_count"),
                    revenue_range=lead.get("revenue_range"),
                    enrichment_json={"source": "experiment", "experiment_id": exp.id},
                    tier=3,
                )
                db.add(account)
                db.flush()
                accounts_by_company[company] = account

            contact = Contact(
                user_id=strategy.user_id,
                account_id=account.id,
                strategy_id=batch.strategy_id,
                full_name=name,
                title=lead.get("title"),
                seniority=lead.get("seniority"),
                linkedin_url=lead.get("linkedin_url"),
                source="experiment",
                source_ref=exp.id,
                is_demo=False,
            )
            db.add(contact)
            db.flush()
            cohort.append(contact)
            existing_names.add(name.lower())
        db.commit()

        # Draft a sequence for each cohort contact that doesn't have one yet.
        drafted = 0
        for c in cohort:
            has_seq = db.query(Sequence).filter(Sequence.contact_id == c.id).first()
            if has_seq:
                continue
            try:
                await generate_sequence(db, c.id)
                drafted += 1
            except Exception as exc:  # pragma: no cover - LLM/parse hiccups
                log.warning("draft sequence failed for contact %s: %s", c.id, exc)

        exp.cohort_size = len(cohort)
        db.commit()
        total_contacts += len(cohort)
        total_drafts += drafted
        per_variant.append(
            {
                "experiment_id": exp.id,
                "name": exp.name,
                "cohort_size": len(cohort),
                "drafted_now": drafted,
                "relevancy": rel_raw if has_score else None,
                "is_winner": is_winner,
                "planned": variant_cap,
                "available_leads": len(exp.leads_json or []),
            }
        )

    if batch.live_status not in ("running", "completed"):
        batch.live_status = "drafted"
    db.commit()

    return {
        "ok": True,
        "batch_id": batch.id,
        "live_status": batch.live_status,
        "total_cohort": total_contacts,
        "total_drafted": total_drafts,
        "per_variant_budget": budget,
        "variants": per_variant,
        "skipped": skipped,
        "note": (
            f"Cohorts materialized and sequences drafted. Leads promoted are scaled by "
            f"each variant's rank (composite score) up to a {budget}-lead budget per "
            f"variant — the winner promotes its full cohort, lower ranks fewer. Reveal "
            f"emails, then launch each variant to start the live window."
            + (f" Skipped {len(skipped)} low-fit variant(s)." if skipped else "")
        ),
    }


def preview_promotion(
    db: Session, batch_id: str, draft_per_variant: Optional[int] = None
) -> dict:
    """Dry-run the promotion plan WITHOUT materializing anything.

    Lets the engineer see exactly how many leads each variant (and the batch in
    total) will move into the funnel test before spending real LLM drafts.
    Uses the same allocation math as ``promote_to_live``.
    """
    batch = db.query(ExperimentBatch).filter(ExperimentBatch.id == batch_id).first()
    if not batch:
        return {"_error": "Experiment batch not found"}
    if batch.status != "analyzed":
        return {"_error": "Analyze the batch first — a live test runs the analyzed variants."}

    experiments = (
        db.query(Experiment)
        .filter(Experiment.batch_id == batch.id, Experiment.status == "done")
        .order_by(Experiment.idx.asc())
        .all()
    )
    if not experiments:
        return {"_error": "Run the experiments first — there are no leads to test."}

    budget = _variant_budget(batch, draft_per_variant)
    plan = _plan_allocation(experiments, batch.best_experiment_id, budget)
    total = sum(p["planned"] for p in plan if not p["skipped"])
    return {
        "batch_id": batch.id,
        "budget_per_variant": budget,
        "leads_per_experiment": batch.leads_per_experiment,
        "total_to_promote": total,
        "total_available": sum(p["available_leads"] for p in plan),
        "skipped_count": sum(1 for p in plan if p["skipped"]),
        "variants": plan,
    }


# ---------------------------------------------------------------------------
# 2. Launch one variant (engineer clicks send) + open the window
# ---------------------------------------------------------------------------

def launch_variant(db: Session, experiment_id: str, test_email: Optional[str] = None) -> dict:
    """Launch every drafted sequence in a variant and open the live window."""
    from app.agents.s3_outreach import launch_sequence

    exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        return {"_error": "Experiment not found"}
    batch = db.query(ExperimentBatch).filter(ExperimentBatch.id == exp.batch_id).first()
    if not batch:
        return {"_error": "Experiment batch not found"}
    strategy = db.query(Strategy).filter(Strategy.id == batch.strategy_id).first()

    contacts = _variant_contacts(db, batch, exp)
    if not contacts:
        return {"_error": "Promote the batch to live first — this variant has no cohort."}

    launched = 0
    skipped = 0
    errors: list[str] = []
    for c in contacts:
        seq = db.query(Sequence).filter(Sequence.contact_id == c.id).first()
        if not seq:
            skipped += 1
            continue
        if seq.status in _LAUNCHED_SEQ_STATUSES:
            skipped += 1
            continue
        try:
            launch_sequence(db, seq.id, test_email=test_email)
            launched += 1
        except Exception as exc:
            errors.append(f"{c.full_name}: {exc}")

    exp.live_launched_at = datetime.utcnow()

    # Open the window on first launch in the batch.
    if not batch.window_started_at:
        months = _window_months(db, strategy) if strategy else DEFAULT_WINDOW_MONTHS
        batch.window_months = months
        batch.window_started_at = datetime.utcnow()
        batch.window_ends_at = datetime.utcnow() + timedelta(days=30 * months)
    batch.live_status = "running"
    db.commit()

    return {
        "ok": True,
        "experiment_id": exp.id,
        "launched": launched,
        "skipped": skipped,
        "errors": errors,
        "window_ends_at": batch.window_ends_at.isoformat() if batch.window_ends_at else None,
        "live_status": batch.live_status,
    }


# ---------------------------------------------------------------------------
# 3. Live funnel metrics (read-only)
# ---------------------------------------------------------------------------

def _variant_metrics(db: Session, batch: ExperimentBatch, exp: Experiment) -> dict:
    contacts = _variant_contacts(db, batch, exp)
    contact_ids = [c.id for c in contacts]
    if not contact_ids:
        return {
            "contacted": 0, "opened": 0, "replied": 0,
            "interested": 0, "positive": 0,
            "reply_rate_pct": 0.0, "positive_rate_pct": 0.0,
        }

    seqs = db.query(Sequence).filter(Sequence.contact_id.in_(contact_ids)).all()
    seq_by_contact = {s.contact_id: s for s in seqs}
    seq_ids = [s.id for s in seqs]

    contacted = sum(1 for s in seqs if s.status in _LAUNCHED_SEQ_STATUSES)

    opened_seq_ids: set[str] = set()
    replied_seq_ids: set[str] = set()
    if seq_ids:
        for ev in (
            db.query(OutreachEvent)
            .filter(OutreachEvent.sequence_id.in_(seq_ids))
            .all()
        ):
            if ev.event_type == "opened":
                opened_seq_ids.add(ev.sequence_id)
            elif ev.event_type in _REPLY_OUTREACH_TYPES:
                replied_seq_ids.add(ev.sequence_id)

    replied_contacts: set[str] = {
        cid for cid, s in seq_by_contact.items() if s.id in replied_seq_ids
    }
    for ev in (
        db.query(EngagementEvent)
        .filter(
            EngagementEvent.contact_id.in_(contact_ids),
            EngagementEvent.event_type.in_(_REPLY_ENGAGEMENT_TYPES),
        )
        .all()
    ):
        replied_contacts.add(ev.contact_id)

    positive = 0
    interested = 0
    for q in (
        db.query(QualificationRecord)
        .filter(QualificationRecord.contact_id.in_(contact_ids))
        .all()
    ):
        if q.status == _POSITIVE_STATUS:
            positive += 1
        elif q.status == _INTERESTED_STATUS:
            interested += 1

    opened = len({c for c, s in seq_by_contact.items() if s.id in opened_seq_ids})
    replied = len(replied_contacts)
    denom = contacted or 1
    return {
        "contacted": contacted,
        "opened": opened,
        "replied": replied,
        "interested": interested,
        "positive": positive,
        "reply_rate_pct": round(replied / denom * 100, 1),
        "positive_rate_pct": round(positive / denom * 100, 1),
    }


def compute_live_metrics(db: Session, batch_id: str) -> dict:
    batch = db.query(ExperimentBatch).filter(ExperimentBatch.id == batch_id).first()
    if not batch:
        return {"_error": "Experiment batch not found"}
    experiments = (
        db.query(Experiment)
        .filter(Experiment.batch_id == batch.id)
        .order_by(Experiment.idx.asc())
        .all()
    )
    rows = []
    for exp in experiments:
        if exp.cohort_size is None and not _variant_contacts(db, batch, exp):
            continue
        m = _variant_metrics(db, batch, exp)
        exp.live_metrics_json = m
        rows.append(_serialize_metrics(exp, m))
    db.commit()

    now_dt = datetime.utcnow()
    window_closed = bool(batch.window_ends_at and batch.window_ends_at <= now_dt)
    return {
        "batch_id": batch.id,
        "live_status": batch.live_status,
        "window_months": batch.window_months,
        "window_started_at": batch.window_started_at.isoformat() if batch.window_started_at else None,
        "window_ends_at": batch.window_ends_at.isoformat() if batch.window_ends_at else None,
        "window_closed": window_closed,
        "live_winner_experiment_id": batch.live_winner_experiment_id,
        "winner_metric": "positive_rate_pct",
        "variants": rows,
        "analysis": batch.live_analysis_json,
    }


# ---------------------------------------------------------------------------
# 4. Evaluate the window → crown the live winner
# ---------------------------------------------------------------------------

def evaluate_live_batch(db: Session, batch_id: str, force: bool = False) -> dict:
    batch = db.query(ExperimentBatch).filter(ExperimentBatch.id == batch_id).first()
    if not batch:
        return {"_error": "Experiment batch not found"}
    if batch.live_status not in ("running", "completed"):
        return {"_error": "This batch has no live test running."}

    now_dt = datetime.utcnow()
    if not force and not (batch.window_ends_at and batch.window_ends_at <= now_dt):
        return {
            "ok": False,
            "pending": True,
            "reason": "The live window is still open.",
            "window_ends_at": batch.window_ends_at.isoformat() if batch.window_ends_at else None,
        }

    experiments = (
        db.query(Experiment)
        .filter(Experiment.batch_id == batch.id)
        .order_by(Experiment.idx.asc())
        .all()
    )
    rows = []
    for exp in experiments:
        if exp.cohort_size is None and not _variant_contacts(db, batch, exp):
            continue
        m = _variant_metrics(db, batch, exp)
        exp.live_metrics_json = m
        rows.append((exp, m))

    if not rows:
        return {"_error": "No launched variants to evaluate."}

    # Winner = highest positive-intent rate, then reply rate, then cohort size.
    def _key(item):
        exp, m = item
        return (m["positive_rate_pct"], m["reply_rate_pct"], exp.cohort_size or 0)

    winner_exp, winner_m = max(rows, key=_key)
    any_positive = any(m["positive"] > 0 for _, m in rows)

    ranking = sorted(
        ({
            "experiment_id": e.id,
            "name": e.name,
            **m,
        } for e, m in rows),
        key=lambda r: (r["positive_rate_pct"], r["reply_rate_pct"]),
        reverse=True,
    )

    recommendations: list[str] = []
    if not any_positive:
        recommendations.append(
            "No variant booked a meeting yet. Keep the window open, or revisit "
            "messaging/timing before scaling."
        )
    else:
        recommendations.append(
            f"Scale '{winner_exp.name}' — it produced the highest positive-intent "
            f"reply rate ({winner_m['positive_rate_pct']}%)."
        )
        worst = ranking[-1]
        if worst["experiment_id"] != winner_exp.id:
            recommendations.append(
                f"Retire '{worst['name']}' ({worst['positive_rate_pct']}% positive) "
                "— it under-converted versus the winner."
            )

    analysis = {
        "winner_experiment_id": winner_exp.id if any_positive else None,
        "winner_name": winner_exp.name if any_positive else None,
        "winner_metric": "positive_rate_pct",
        "ranking": ranking,
        "any_positive": any_positive,
        "recommendations": recommendations,
        "evaluated_at": now_dt.isoformat(),
    }

    batch.live_analysis_json = analysis
    batch.live_winner_experiment_id = winner_exp.id if any_positive else None
    batch.live_status = "completed"
    db.commit()

    # Capture a durable learning so the rest of the factory can recall it.
    if any_positive:
        try:
            from app.agents.learnings import record_learning

            record_learning(
                db,
                content=(
                    f"Live funnel test winner: '{winner_exp.name}' converted "
                    f"{winner_m['positive']}/{winner_m['contacted']} contacts to a booked "
                    f"meeting ({winner_m['positive_rate_pct']}% positive-intent reply rate)."
                ),
                category="experiment",
                title="Live experiment winner (positive-intent)",
                strategy_id=batch.strategy_id,
                source="experiment",
                source_ref=batch.id,
                metrics={
                    "positive_rate_pct": winner_m["positive_rate_pct"],
                    "reply_rate_pct": winner_m["reply_rate_pct"],
                    "contacted": winner_m["contacted"],
                },
                confidence="High",
            )
        except Exception as exc:  # pragma: no cover
            log.warning("failed to capture live-experiment learning: %s", exc)

    return {
        "ok": True,
        "batch_id": batch.id,
        "live_status": batch.live_status,
        "live_winner_experiment_id": batch.live_winner_experiment_id,
        "analysis": analysis,
    }


# ---------------------------------------------------------------------------
# 5. Background tick — evaluate any window that has closed
# ---------------------------------------------------------------------------

def evaluate_due_batches(db: Session) -> int:
    """Evaluate every running batch whose window has closed. Returns count."""
    due = (
        db.query(ExperimentBatch)
        .filter(
            ExperimentBatch.live_status == "running",
            ExperimentBatch.window_ends_at.isnot(None),
            ExperimentBatch.window_ends_at <= datetime.utcnow(),
        )
        .all()
    )
    n = 0
    for batch in due:
        try:
            evaluate_live_batch(db, batch.id, force=True)
            n += 1
        except Exception as exc:  # pragma: no cover
            log.exception("live-experiment eval failed for batch %s: %s", batch.id, exc)
    return n


# ---------------------------------------------------------------------------
# 6. Hidden test accelerator — synthesize the funnel + close the window
# ---------------------------------------------------------------------------

def simulate_window(db: Session, batch_id: str) -> dict:
    """TEST ONLY: synthesize sends + replies + meetings so the live loop closes
    immediately, then evaluate the winner. Never wired to the main UI flow."""
    from app.services.instantly_poller import simulate_engagement_timeline

    batch = db.query(ExperimentBatch).filter(ExperimentBatch.id == batch_id).first()
    if not batch:
        return {"_error": "Experiment batch not found"}
    if batch.live_status not in ("drafted", "running"):
        return {"_error": "Promote + (optionally) launch the batch before simulating."}

    experiments = (
        db.query(Experiment)
        .filter(Experiment.batch_id == batch.id)
        .order_by(Experiment.idx.asc())
        .all()
    )

    launched_any = False
    for exp in experiments:
        contacts = _variant_contacts(db, batch, exp)
        if not contacts:
            continue
        # Deterministic per-variant conversion: anchor positive rate to the
        # relevancy score so a sensible winner emerges, with funnel falloff.
        score = float(exp.score or 30.0)
        positive_rate = max(0.1, min(0.6, 0.1 + (score / 100.0) * 0.5))
        replied_rate = min(0.9, positive_rate * 2.0)
        n = len(contacts)
        n_positive = max(0, round(positive_rate * n))
        n_replied = max(n_positive, round(replied_rate * n))

        for i, c in enumerate(contacts):
            seq = db.query(Sequence).filter(Sequence.contact_id == c.id).first()
            if not seq:
                continue
            if seq.status not in _LAUNCHED_SEQ_STATUSES:
                seq.status = "simulated"
                db.commit()
            simulate_engagement_timeline(db, seq.id)
            launched_any = True

            if i < n_replied:
                db.add(
                    EngagementEvent(
                        contact_id=c.id,
                        account_id=c.account_id,
                        strategy_id=batch.strategy_id,
                        channel="email",
                        event_type="email_reply",
                        intent_contribution_score=10.0,
                        metadata_json={"simulated": True, "experiment_id": exp.id},
                    )
                )
            if i < n_positive:
                db.query(QualificationRecord).filter(
                    QualificationRecord.contact_id == c.id
                ).delete()
                db.add(
                    QualificationRecord(
                        contact_id=c.id,
                        strategy_id=batch.strategy_id,
                        status=_POSITIVE_STATUS,
                        icp_fit_score=float(c.icp_fit_score or 0.0) if hasattr(c, "icp_fit_score") else 0.0,
                        intent_score=80.0,
                        engagement_score=float(c.engagement_score or 0.0),
                    )
                )
        exp.live_launched_at = exp.live_launched_at or datetime.utcnow()
        db.commit()

    if not launched_any:
        return {"_error": "No drafted cohorts to simulate. Promote the batch first."}

    # Force the window closed and evaluate.
    if not batch.window_started_at:
        batch.window_started_at = datetime.utcnow() - timedelta(days=30)
        batch.window_months = batch.window_months or DEFAULT_WINDOW_MONTHS
    batch.window_ends_at = datetime.utcnow()
    batch.live_status = "running"
    db.commit()

    result = evaluate_live_batch(db, batch.id, force=True)
    result["simulated"] = True
    return result
