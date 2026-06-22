"""Post-experiments campaign execution plan.

This is the bridge between *what we learned* and *what we now run*. It is the
campaign plan the user asked to keep OUT of the ROI panel and that "comes only
after the successful run of experiments":

  1. Gate — there must be an analyzed experiment batch with a declared winner.
     Until then the plan is withheld and we explain what's missing.
  2. Inherit — pull the phased revenue targets the ROI engine already produced
     (seasonality-aware, summing to the annual target) plus the total required
     prospects.
  3. Kick off after the learning window — phases start one experiment window
     (≈1 month) after the ROI execution-start month, because month one is spent
     testing hypotheses, not scaling.
  4. Front-load prospecting — because of the sales-cycle lag, prospecting effort
     is weighted into the EARLY phases (a geometric decay curve) so pipeline
     matures in time to hit the later-landing revenue. The first phases get the
     heaviest prospecting load (Q2/Q3-style front-loading).
  5. Allocate by persona — each phase's prospects are split across the winning
     personas using the same 70/30 weighting the persona engine recommends.
  6. Target with the winning facets — the best experiment's Apollo parameters
     become the targeting recipe for the whole program.

All distribution math is deterministic Python; nothing depends on a model's
arithmetic.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.db import Strategy, ExperimentBatch, Experiment
from app.agents.persona_intelligence import compute_persona_allocation, _distribute_counts
from app.agents.roi_validator import MONTH_NAMES, EXPERIMENT_WINDOW_MONTHS

log = logging.getLogger("gtm.campaign_plan")

# Each later phase gets this fraction of the previous phase's prospecting weight.
# 0.7 puts ~40% of prospecting into phase 1 of a 4-phase program — deliberately
# front-loaded so pipeline has time to mature before revenue is due.
FRONTLOAD_DECAY = 0.7
# Facet keys carried over from the winning experiment as the targeting recipe.
FACET_KEYS = (
    "titles",
    "seniorities",
    "locations",
    "industries",
    "employee_ranges",
    "technologies",
    "revenue_ranges",
    "keywords",
)


def _shift_month(start_month: int, offset: int) -> int:
    return ((int(start_month or 1) - 1 + int(offset or 0)) % 12) + 1


def _phase_length(ph: dict) -> int:
    """Phase length in months, parsed from the ROI phase's 'Months X–Y' range."""
    nums = re.findall(r"\d+", ph.get("month_range") or "")
    if len(nums) >= 2:
        return max(1, int(nums[1]) - int(nums[0]) + 1)
    return 1


def _frontload_weights(n_phases: int) -> list[float]:
    """Geometric decay weights, normalized to sum to 1.0 (earliest = heaviest)."""
    if n_phases <= 0:
        return []
    raw = [FRONTLOAD_DECAY ** i for i in range(n_phases)]
    total = sum(raw) or 1.0
    return [r / total for r in raw]


def _experiment_gate(db: Session, strategy_id: str) -> tuple[Optional[ExperimentBatch], Optional[Experiment]]:
    """Return the latest analyzed batch with a winner, plus the winning experiment."""
    batch = (
        db.query(ExperimentBatch)
        .filter(
            ExperimentBatch.strategy_id == strategy_id,
            ExperimentBatch.status == "analyzed",
            ExperimentBatch.best_experiment_id.isnot(None),
        )
        .order_by(ExperimentBatch.updated_at.desc())
        .first()
    )
    if not batch:
        return None, None
    winner = (
        db.query(Experiment)
        .filter(Experiment.id == batch.best_experiment_id)
        .first()
    )
    return batch, winner


def _winning_facets(winner: Optional[Experiment]) -> dict:
    if not winner or not isinstance(winner.params_json, dict):
        return {}
    out: dict = {}
    for k in FACET_KEYS:
        v = winner.params_json.get(k)
        if isinstance(v, list) and v:
            out[k] = v
        elif isinstance(v, str) and v.strip():
            out[k] = v
    return out


def build_campaign_plan(db: Session, strategy_id: str) -> dict:
    """Build the post-experiments execution plan, or explain why it's gated."""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return {"ready": False, "reason": "Strategy not found.", "gate": "missing_strategy"}

    roi = strategy.roi_json or {}
    gtm = (roi.get("gtm_plan") or {}) if isinstance(roi, dict) else {}
    revenue_plan = gtm.get("revenue_plan") or {}
    phases = revenue_plan.get("phases") or []
    total_prospects = int(gtm.get("required_prospects") or 0)

    if not phases or total_prospects <= 0:
        return {
            "ready": False,
            "gate": "roi_pending",
            "reason": "Run the ROI calculator first — the campaign plan inherits its phased "
            "targets and required prospect volume.",
        }

    batch, winner = _experiment_gate(db, strategy_id)
    if not batch:
        return {
            "ready": False,
            "gate": "experiments_pending",
            "reason": "Seed, run, and analyze an experiment batch first. The campaign plan "
            "only kicks off after a successful experiment run picks a winning segment.",
        }

    # ---- Timing: program begins after the learning window ----
    inputs = gtm.get("inputs") or {}
    roi_start = int(inputs.get("execution_start_month") or revenue_plan.get("execution_start_month") or 1)
    exp_window = int((gtm.get("experiment_plan") or {}).get("window_months") or EXPERIMENT_WINDOW_MONTHS)
    campaign_start_month = _shift_month(roi_start, exp_window)

    # ---- Front-loaded prospecting distribution across the phases ----
    n_phases = len(phases)
    weights = _frontload_weights(n_phases)
    frontloaded = _distribute_counts(total_prospects, weights)

    winning_facets = _winning_facets(winner)
    winning_insight = (batch.analysis_json or {}).get("winning_parameters_insight")

    plan_phases: list[dict] = []
    elapsed = 0  # months elapsed since the ROI execution start (before window shift)
    for i, ph in enumerate(phases):
        prospect_count = frontloaded[i] if i < len(frontloaded) else 0
        # Persona split for this phase's prospect load (70/30 by default).
        alloc = compute_persona_allocation(db, strategy_id, total_prospects=prospect_count)
        persona_split = [
            {
                "persona_type": a["persona_type"],
                "label": a["label"],
                "weight_pct": a["weight_pct"],
                "prospect_count": a["prospect_count"],
            }
            for a in (alloc.get("allocations") or [])
        ]

        # Calendar range shifted so the program starts after the learning window.
        length = _phase_length(ph)
        first_cal = _shift_month(roi_start, exp_window + elapsed)
        last_cal = _shift_month(roi_start, exp_window + elapsed + length - 1)
        elapsed += length
        cal_range = (
            MONTH_NAMES[first_cal]
            if first_cal == last_cal
            else f"{MONTH_NAMES[first_cal]}–{MONTH_NAMES[last_cal]}"
        )

        plan_phases.append(
            {
                "phase": ph.get("phase", i + 1),
                "label": ph.get("label", f"Phase {i + 1}"),
                "calendar_range": cal_range,
                "quarter": f"Q{(first_cal - 1) // 3 + 1}",
                "revenue_target_usd": ph.get("phase_target_usd", 0),
                "required_closures": ph.get("required_closures", 0),
                # Front-loaded prospecting load (overrides the flat ROI split).
                "prospect_count": prospect_count,
                "prospect_share_pct": round(weights[i] * 100, 1) if i < len(weights) else 0.0,
                "baseline_prospects": ph.get("required_prospects", 0),
                "persona_split": persona_split,
                "season_factor": ph.get("season_factor"),
                "confidence": ph.get("confidence"),
            }
        )

    front_share = round(sum(weights[: min(2, n_phases)]) * 100, 1)

    return {
        "ready": True,
        "gate": "ready",
        "strategy_id": strategy_id,
        "source_batch_id": batch.id,
        "winning_experiment_id": batch.best_experiment_id,
        "winning_experiment_name": winner.name if winner else None,
        "winning_facets": winning_facets,
        "winning_parameters_insight": winning_insight,
        "kickoff_month": campaign_start_month,
        "kickoff_label": MONTH_NAMES[campaign_start_month],
        "experiment_window_months": exp_window,
        "total_prospects": total_prospects,
        "frontload_decay": FRONTLOAD_DECAY,
        "frontload_first_two_pct": front_share,
        "phase_count": n_phases,
        "annual_target_usd": revenue_plan.get("annual_target_usd"),
        "overall_confidence": revenue_plan.get("overall_confidence"),
        "phases": plan_phases,
        "notes": [
            f"Program kicks off in {MONTH_NAMES[campaign_start_month]} — after a "
            f"{exp_window}-month experiment window proves the winning segment.",
            f"Prospecting is front-loaded: the first {min(2, n_phases)} phase(s) carry "
            f"{front_share}% of the {total_prospects:,} prospects so pipeline matures "
            "ahead of the later-landing revenue.",
            "Each phase's prospects are split across the top personas using the 70/30 "
            "weighting from persona intelligence.",
        ],
    }
