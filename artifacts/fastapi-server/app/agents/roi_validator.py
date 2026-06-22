"""ROI expectation validator.

Given a product profile (``Strategy``) and the user's stated investment vs
expected revenue/returns, this judges whether the expectation is realistic for
*this specific* profile — grounded in the profile's own TAM/SAM/SOM market
sizing, ICP firmographics, and NAICS segmentation rather than generic
benchmarks.

The model proposes profile-specific benchmark parameters (typical ROI
multiple range, payback period, win rate, ACV, sales cycle) and a corrected
investment or revenue target when the stated expectation is off. All money
math the UI relies on (the expected multiple, TAM/SAM ceiling checks) is
recomputed deterministically in Python so the verdict never hinges on the
model's arithmetic.
"""
import json
import math
from typing import Optional

from sqlalchemy.orm import Session

from app.db import Contact, Strategy
from app.llm import chat_json, MODEL_NAME
from app.provenance import stamp
from app.services import audit_service

# --- GTM planning assumptions (defaults — all editable by the user) ---
DEFAULT_CONVERSION_RATE = 0.01          # prospects -> closed deals (1%)
DEFAULT_LEAD_ACQUISITION_COST = 0.30    # $/lead (Apollo enrichment, email lookup)
DEFAULT_OUTREACH_COST = 0.50            # $/prospect (sending infra, deliverability)
DEFAULT_GTM_ENGINEER_CAPACITY = 10      # active qualified prospects / engineer / day
DEFAULT_CURRENT_GTM_ENGINEERS = 1
DEFAULT_CAMPAIGN_COUNT = 3
DEFAULT_AVERAGE_DEAL_SIZE = 10_000.0    # fallback only — derived from ACV when available
WORKING_DAYS_PER_MONTH = 21
URGENCY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}

# --- Additional per-prospect GTM cost assumptions (platform cost) ---
DEFAULT_SERP_API_COST = 0.10        # $/prospect — SERP/news/signal enrichment lookups
DEFAULT_AI_TOKEN_COST = 0.05        # $/prospect — LLM tokens for research + drafting

# --- Email sending capacity (cold-safe daily limits per inbox) ---
# These are conservative COLD-outreach safe ceilings (with warmup), NOT the raw
# provider caps (free ~500/day, Workspace ~2000/day), which torch deliverability.
COLD_SEND_PER_DAY = {"free": 30, "workspace": 50}
DEFAULT_EMAIL_ACCOUNTS = 2
DEFAULT_EMAIL_ACCOUNT_TYPE = "workspace"
SENDING_DAYS_PER_MONTH = 21

# --- Experiment seeding (month-1 discovery loop that precedes phased execution) ---
EXPERIMENT_WINDOW_MONTHS = 1        # default learning window before phases begin
DEFAULT_EXPERIMENT_COUNT = 3        # persona × segment hypotheses to test
MIN_LEADS_PER_EXPERIMENT = 25       # statistically-useful floor per experiment

# --- Revenue execution planning (phases / seasonality / carry-forward) ---
DEFAULT_SALES_CYCLE_MONTHS = 3
# Per-calendar-month seasonality multiplier applied to expected response /
# conversion. <1.0 means a typically slower selling month. Grounded in common
# B2B GTM patterns (summer lull, year-end holiday & budget freezes).
MONTH_SEASONALITY = {
    1: 0.95, 2: 1.00, 3: 1.05, 4: 1.05, 5: 1.05, 6: 1.00,
    7: 0.85, 8: 0.80, 9: 1.05, 10: 1.05, 11: 0.95, 12: 0.75,
}
MONTH_NAMES = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]
SEASONALITY_NOTES = {
    7: "summer slowdown — lighter inboxes and slower procurement",
    8: "summer slowdown — lighter inboxes and slower procurement",
    11: "pre-holiday slowdown begins late in the month",
    12: "holiday season and year-end budget freezes depress response",
}


def _money(val) -> Optional[float]:
    """Coerce a possibly-stringified money value to a float, or None."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = (
            val.replace("$", "").replace(",", "").replace("USD", "").strip().lower()
        )
        mult = 1.0
        if cleaned.endswith("b") or cleaned.endswith("bn"):
            mult = 1_000_000_000
            cleaned = cleaned.rstrip("bn")
        elif cleaned.endswith("m"):
            mult = 1_000_000
            cleaned = cleaned.rstrip("m")
        elif cleaned.endswith("k"):
            mult = 1_000
            cleaned = cleaned.rstrip("k")
        try:
            return float(cleaned) * mult
        except ValueError:
            return None
    return None


def _tier_value(tam_sam_som: dict, key: str) -> Optional[float]:
    if not isinstance(tam_sam_som, dict):
        return None
    block = tam_sam_som.get(key)
    if isinstance(block, dict):
        return _money(block.get("value_usd"))
    return None


def _distribute(total: int, parts: int) -> list[int]:
    """Split ``total`` across ``parts`` buckets, front-loading any remainder."""
    if parts <= 0:
        return []
    base, rem = divmod(max(0, total), parts)
    return [base + (1 if i < rem else 0) for i in range(parts)]


def _allocate_engineers(team_size: int, prospect_dist: list[int]) -> list[int]:
    """Allocate ``team_size`` engineers across campaigns proportional to volume."""
    n = len(prospect_dist)
    if n == 0:
        return []
    if team_size <= 0:
        return [0] * n
    total_prospects = sum(prospect_dist) or 1
    raw = [team_size * p / total_prospects for p in prospect_dist]
    alloc = [max(0, int(math.floor(r))) for r in raw]
    # Hand out the leftover engineers to the campaigns with the largest remainder.
    leftover = team_size - sum(alloc)
    if leftover > 0:
        order = sorted(range(n), key=lambda i: raw[i] - alloc[i], reverse=True)
        for i in range(leftover):
            alloc[order[i % n]] += 1
    return alloc


def _confidence_from_score(score: float) -> str:
    if score >= 0.85:
        return "High"
    if score >= 0.6:
        return "Moderate"
    return "Low"


def _email_capacity(
    *,
    email_accounts: int,
    email_account_type: str,
    required_prospects: int,
    time_horizon_months: int,
    experiment_window_months: int = EXPERIMENT_WINDOW_MONTHS,
) -> dict:
    """How many cold emails the configured inboxes can actually send.

    Deterministic feasibility check: compares the prospect volume that must be
    contacted against realistic cold-send capacity over the timeframe, and over
    just the month-1 experiment window (which gates experiment sizing).
    """
    accounts = max(0, int(email_accounts or 0))
    acct_type = (email_account_type or DEFAULT_EMAIL_ACCOUNT_TYPE).strip().lower()
    if acct_type not in COLD_SEND_PER_DAY:
        acct_type = DEFAULT_EMAIL_ACCOUNT_TYPE
    per_day = COLD_SEND_PER_DAY[acct_type]
    months = max(1, int(time_horizon_months or 1))

    daily_capacity = accounts * per_day
    monthly_capacity = daily_capacity * SENDING_DAYS_PER_MONTH
    total_capacity = monthly_capacity * months
    window_capacity = monthly_capacity * max(1, int(experiment_window_months or 1))

    sufficient = total_capacity >= required_prospects if required_prospects > 0 else True
    # Inboxes required to cover the volume in the available timeframe.
    needed_per_day = (
        math.ceil(required_prospects / (months * SENDING_DAYS_PER_MONTH))
        if required_prospects > 0
        else 0
    )
    recommended_accounts = math.ceil(needed_per_day / per_day) if per_day else 0
    additional_accounts = max(0, recommended_accounts - accounts)

    message = None
    if not sufficient:
        message = (
            f"{accounts} {acct_type} inbox(es) can send ~{total_capacity:,} cold emails over "
            f"{months} month(s), short of the {required_prospects:,} prospects to reach. Add "
            f"{additional_accounts} inbox(es) (or extend the timeframe) to close the gap."
        )

    return {
        "email_accounts": accounts,
        "email_account_type": acct_type,
        "per_account_per_day": per_day,
        "daily_capacity": daily_capacity,
        "monthly_capacity": monthly_capacity,
        "total_capacity": total_capacity,
        "experiment_window_capacity": window_capacity,
        "required_prospects": required_prospects,
        "sufficient": sufficient,
        "recommended_accounts": recommended_accounts,
        "additional_accounts": additional_accounts,
        "message": message,
    }


def _build_experiment_plan(
    *,
    required_prospects: int,
    window_capacity: int,
    persona_count: int,
    experiment_window_months: int = EXPERIMENT_WINDOW_MONTHS,
) -> dict:
    """Seed the month-1 experiment loop from the ROI math (capacity-driven).

    The number of experiments reflects how many persona × segment hypotheses we
    can meaningfully test, and leads-per-experiment is what the inboxes can
    actually email in the experiment window divided across those experiments
    (floored at a useful sample size).
    """
    # How many emails we can really send in the learning window.
    sendable = max(0, int(window_capacity or 0))

    # Number of hypotheses to test: bounded by persona variety and by whether we
    # have the send capacity to give each experiment a useful sample.
    max_by_capacity = max(1, sendable // MIN_LEADS_PER_EXPERIMENT) if sendable > 0 else 1
    desired = max(1, min(DEFAULT_EXPERIMENT_COUNT, max(1, persona_count or DEFAULT_EXPERIMENT_COUNT)))
    n_experiments = max(1, min(desired, max_by_capacity))

    if sendable > 0:
        leads_per_experiment = max(MIN_LEADS_PER_EXPERIMENT, sendable // n_experiments)
        # Never plan to email more than we can send in the window.
        leads_per_experiment = min(leads_per_experiment, max(1, sendable // n_experiments) or leads_per_experiment)
    else:
        leads_per_experiment = MIN_LEADS_PER_EXPERIMENT

    total_experiment_leads = n_experiments * leads_per_experiment
    capacity_limited = sendable > 0 and total_experiment_leads >= sendable

    return {
        "window_months": max(1, int(experiment_window_months or 1)),
        "n_experiments": n_experiments,
        "leads_per_experiment": leads_per_experiment,
        "total_experiment_leads": total_experiment_leads,
        "window_send_capacity": sendable,
        "capacity_limited": capacity_limited,
        "rationale": (
            f"Run {n_experiments} experiment(s) of {leads_per_experiment} leads each in the "
            f"{max(1, int(experiment_window_months or 1))}-month learning window to test which "
            "persona/segment converts before committing to phased execution."
        ),
    }


def _build_revenue_plan(
    *,
    revenue_target: float,
    deal_size: float,
    conversion_rate: float,
    sales_cycle_months: int,
    time_horizon_months: int,
    execution_start_month: int,
    available_engineers: int,
    capacity_per_day: float,
    budget_sufficient: bool,
    capacity_sufficient: bool,
    ceiling_breached: bool,
) -> dict:
    """Distribute the annual target across sales-cycle phases.

    Models seasonality, a deterministic carry-forward simulation (shortfalls
    roll into the next phase), per-phase capacity, and confidence. All math is
    deterministic so the plan never depends on the model's arithmetic.
    """
    cycle = max(1, int(sales_cycle_months or DEFAULT_SALES_CYCLE_MONTHS))
    horizon = max(1, int(time_horizon_months or 1))
    start_month = int(execution_start_month or 1)
    if start_month < 1 or start_month > 12:
        start_month = ((start_month - 1) % 12) + 1

    # ---- Split the horizon into phases of one sales cycle each ----
    phase_lengths: list[int] = []
    remaining = horizon
    while remaining > 0:
        length = min(cycle, remaining)
        phase_lengths.append(length)
        remaining -= length
    n_phases = len(phase_lengths)

    # ---- Seasonality weight per phase (avg of its calendar months) ----
    cursor = 0  # months elapsed since execution start
    phase_meta: list[dict] = []
    for length in phase_lengths:
        months: list[int] = []
        for k in range(length):
            cal = ((start_month - 1 + cursor + k) % 12) + 1
            months.append(cal)
        cursor += length
        factors = [MONTH_SEASONALITY[m] for m in months]
        season_factor = sum(factors) / len(factors) if factors else 1.0
        notes = sorted({SEASONALITY_NOTES[m] for m in months if m in SEASONALITY_NOTES})
        phase_meta.append(
            {
                "months": months,
                "season_factor": round(season_factor, 3),
                "season_notes": notes,
            }
        )

    # ---- Base distribution proportional to phase length, then re-weighted by
    # seasonality and renormalized so the phases still sum to the target. ----
    base_weights = [pl / horizon for pl in phase_lengths]
    seasoned = [base_weights[i] * phase_meta[i]["season_factor"] for i in range(n_phases)]
    seasoned_sum = sum(seasoned) or 1.0
    distributed_targets = [revenue_target * (s / seasoned_sum) for s in seasoned]

    # ---- Carry-forward simulation across phases ----
    phases: list[dict] = []
    carried_in = 0.0
    cumulative_projected = 0.0
    for i in range(n_phases):
        meta = phase_meta[i]
        length = phase_lengths[i]
        base_target = distributed_targets[i]
        # The base targets sum to the annual target. Carry-in from an
        # under-delivering prior phase is tracked separately so the displayed
        # base "Target" column never double-counts (it always sums to annual).
        effective_target = base_target + carried_in

        closures = max(0, math.ceil(effective_target / deal_size)) if effective_target > 0 else 0
        prospects = math.ceil(closures / conversion_rate) if closures > 0 else 0

        working_days = length * WORKING_DAYS_PER_MONTH
        phase_capacity = available_engineers * capacity_per_day * working_days
        capacity_attainment = (
            min(1.0, phase_capacity / prospects) if prospects > 0 else 1.0
        )
        # A sub-1.0 season factor means we realistically expect to land below the
        # phase target; a >=1.0 factor doesn't let us exceed it for planning.
        season_attainment = min(1.0, meta["season_factor"])
        projected_attainment = round(capacity_attainment * season_attainment, 3)
        projected_revenue = effective_target * projected_attainment
        shortfall = max(0.0, effective_target - projected_revenue)
        cumulative_projected += projected_revenue

        start_idx = sum(phase_lengths[:i])
        first_cal = meta["months"][0]
        last_cal = meta["months"][-1]
        phases.append(
            {
                "phase": i + 1,
                "label": f"Phase {i + 1}",
                "month_range": f"Months {start_idx + 1}–{start_idx + length}",
                "calendar_range": (
                    MONTH_NAMES[first_cal]
                    if first_cal == last_cal
                    else f"{MONTH_NAMES[first_cal]}–{MONTH_NAMES[last_cal]}"
                ),
                "quarter": f"Q{(first_cal - 1) // 3 + 1}",
                "base_target_usd": int(round(base_target)),
                "carried_in_usd": int(round(carried_in)),
                # Displayed "Target" = base target (the phase's own share); base
                # targets across phases sum exactly to the annual target.
                "phase_target_usd": int(round(base_target)),
                "effective_target_usd": int(round(effective_target)),
                "required_closures": closures,
                "required_prospects": prospects,
                "phase_capacity_prospects": int(round(phase_capacity)),
                "season_factor": meta["season_factor"],
                "season_notes": meta["season_notes"],
                "projected_attainment_pct": round(projected_attainment * 100, 1),
                "projected_revenue_usd": int(round(projected_revenue)),
                "carry_forward_usd": int(round(shortfall)),
                "confidence": _confidence_from_score(projected_attainment),
            }
        )
        carried_in = shortfall

    final_shortfall = carried_in
    projected_total = cumulative_projected
    coverage = projected_total / revenue_target if revenue_target > 0 else 1.0

    # ---- Overall confidence ----
    avg_attainment = (
        sum(p["projected_attainment_pct"] for p in phases) / (100 * len(phases))
        if phases
        else 1.0
    )
    conf_score = avg_attainment
    if ceiling_breached:
        conf_score -= 0.25
    if not budget_sufficient:
        conf_score -= 0.15
    if not capacity_sufficient:
        conf_score -= 0.15
    conf_score = max(0.0, min(1.0, conf_score))
    overall_confidence = _confidence_from_score(conf_score)

    worst = min(phases, key=lambda p: p["season_factor"]) if phases else None
    seasonality_impact = None
    if worst and worst["season_factor"] < 0.95 and worst["season_notes"]:
        seasonality_impact = (
            f"{worst['label']} ({worst['calendar_range']}, {worst['quarter']}) is affected by "
            f"{worst['season_notes'][0]}; expect ~{round((1 - worst['season_factor']) * 100)}% "
            f"lower response there."
        )

    return {
        "sales_cycle_months": cycle,
        "execution_start_month": start_month,
        "execution_start_label": MONTH_NAMES[start_month],
        "phase_count": n_phases,
        "annual_target_usd": int(round(revenue_target)),
        "projected_total_usd": int(round(projected_total)),
        "projected_coverage_pct": round(coverage * 100, 1),
        "final_shortfall_usd": int(round(final_shortfall)),
        "overall_confidence": overall_confidence,
        "seasonality_impact": seasonality_impact,
        "phases": phases,
    }


def _build_gtm_plan(
    *,
    revenue_target: float,
    average_deal_size: Optional[float],
    conversion_rate: float,
    lead_acquisition_cost: float,
    outreach_cost: float,
    gtm_engineer_capacity: float,
    current_gtm_engineers: int,
    time_horizon_months: int,
    time_urgency: str,
    campaign_count: int,
    investment: Optional[float],
    benchmark_acv: Optional[float],
    verdict: Optional[str],
    ceiling_breached: bool,
    realistic_low: Optional[float] = None,
    realistic_high: Optional[float] = None,
    sales_cycle_months: int = DEFAULT_SALES_CYCLE_MONTHS,
    execution_start_month: int = 1,
    serp_api_cost: float = DEFAULT_SERP_API_COST,
    ai_token_cost: float = DEFAULT_AI_TOKEN_COST,
    email_accounts: int = DEFAULT_EMAIL_ACCOUNTS,
    email_account_type: str = DEFAULT_EMAIL_ACCOUNT_TYPE,
    persona_count: int = 0,
) -> dict:
    """Deterministic GTM planning layer built on top of the feasibility check.

    Computes required prospect volume, GTM execution cost, team capacity, and a
    campaign execution strategy. All arithmetic happens here in Python so the
    plan never depends on the model's math.
    """
    # ---- Sanitize / default the assumptions ----
    deal_size = average_deal_size if (average_deal_size and average_deal_size > 0) else None
    if deal_size is None:
        deal_size = benchmark_acv if (benchmark_acv and benchmark_acv > 0) else DEFAULT_AVERAGE_DEAL_SIZE
    conv = conversion_rate if (conversion_rate and 0 < conversion_rate <= 1) else DEFAULT_CONVERSION_RATE
    lead_cost = lead_acquisition_cost if lead_acquisition_cost is not None and lead_acquisition_cost >= 0 else DEFAULT_LEAD_ACQUISITION_COST
    out_cost = outreach_cost if outreach_cost is not None and outreach_cost >= 0 else DEFAULT_OUTREACH_COST
    serp_cost = serp_api_cost if serp_api_cost is not None and serp_api_cost >= 0 else DEFAULT_SERP_API_COST
    token_cost = ai_token_cost if ai_token_cost is not None and ai_token_cost >= 0 else DEFAULT_AI_TOKEN_COST
    capacity_per_day = gtm_engineer_capacity if (gtm_engineer_capacity and gtm_engineer_capacity > 0) else DEFAULT_GTM_ENGINEER_CAPACITY
    engineers = max(0, int(current_gtm_engineers or 0))
    months = max(1, int(time_horizon_months or 1))
    n_campaigns = max(1, int(campaign_count or DEFAULT_CAMPAIGN_COUNT))
    urgency = (time_urgency or "medium").strip().lower()
    if urgency not in URGENCY_RANK:
        urgency = "medium"

    # ---- Step 2 & 3: required closures and prospect volume ----
    required_closures = max(1, math.ceil(revenue_target / deal_size)) if revenue_target > 0 else 0
    required_prospects = math.ceil(required_closures / conv) if required_closures > 0 else 0

    # ---- Step 4-6: GTM execution cost (platform cost to reach the target) ----
    data_cost = round(required_prospects * lead_cost, 2)
    outreach_total = round(required_prospects * out_cost, 2)
    serp_total = round(required_prospects * serp_cost, 2)
    token_total = round(required_prospects * token_cost, 2)
    total_cost = round(data_cost + outreach_total + serp_total + token_total, 2)

    # ---- Capacity planning ----
    working_days = months * WORKING_DAYS_PER_MONTH
    capacity_per_engineer = capacity_per_day * working_days
    available_capacity = engineers * capacity_per_engineer
    utilization_pct = (
        round((required_prospects / available_capacity) * 100, 1)
        if available_capacity > 0
        else None
    )
    capacity_gap = max(0, required_prospects - available_capacity)
    capacity_sufficient = available_capacity >= required_prospects and engineers > 0
    recommended_engineers = (
        math.ceil(required_prospects / capacity_per_engineer) if capacity_per_engineer > 0 else 0
    )
    additional_engineers = max(0, recommended_engineers - engineers)

    # ---- Budget feasibility ----
    budget_sufficient = investment is None or investment >= total_cost

    # ---- Email sending capacity (cold-safe) + month-1 experiment seeding ----
    email_capacity = _email_capacity(
        email_accounts=email_accounts,
        email_account_type=email_account_type,
        required_prospects=required_prospects,
        time_horizon_months=months,
    )
    experiment_plan = _build_experiment_plan(
        required_prospects=required_prospects,
        window_capacity=email_capacity["experiment_window_capacity"],
        persona_count=persona_count,
    )

    # ---- Reconciliation: does this plan reach the target, and how does the
    # target compare with the market-grounded realistic range? ----
    def _prospects_for(rev: Optional[float]) -> Optional[int]:
        if not rev or rev <= 0:
            return None
        closures = max(1, math.ceil(rev / deal_size))
        return math.ceil(closures / conv)

    # By construction closures = ceil(target / deal_size), so executing the plan
    # at the stated assumptions recovers at least the target.
    forward_revenue = required_closures * deal_size
    reaches_target = forward_revenue >= revenue_target

    r_low = realistic_low if (realistic_low and realistic_low > 0) else None
    r_high = realistic_high if (realistic_high and realistic_high > 0) else None
    if r_low and r_high and r_low > r_high:
        r_low, r_high = r_high, r_low
    if r_high is not None and revenue_target > r_high:
        alignment = "above_realistic"
    elif r_low is not None and revenue_target < r_low:
        alignment = "below_realistic"
    elif r_low is not None or r_high is not None:
        alignment = "within_realistic"
    else:
        alignment = "unknown"

    reconciliation = {
        "target_usd": int(round(revenue_target)),
        "forward_revenue_usd": int(round(forward_revenue)),
        "reaches_target": bool(reaches_target),
        "realistic_low_usd": int(round(r_low)) if r_low is not None else None,
        "realistic_high_usd": int(round(r_high)) if r_high is not None else None,
        "alignment": alignment,
        "prospects_for_realistic_low": _prospects_for(r_low),
        "prospects_for_realistic_high": _prospects_for(r_high),
    }

    # ---- Step 1 (preserved): revenue assessment label ----
    if ceiling_breached:
        revenue_assessment = "Unrealistic"
    elif verdict == "too_optimistic":
        revenue_assessment = "Aggressive"
    elif verdict == "too_conservative":
        revenue_assessment = "Conservative"
    elif verdict == "realistic":
        revenue_assessment = "Realistic"
    else:
        revenue_assessment = "Realistic"
    # Nudge an otherwise-"realistic" target to "Aggressive" if execution is strained.
    if revenue_assessment == "Realistic" and (
        not budget_sufficient or (utilization_pct is not None and utilization_pct > 150)
    ):
        revenue_assessment = "Aggressive"

    # ---- Campaign execution strategy ----
    rank = URGENCY_RANK[urgency]
    high_urgency = rank >= 3
    low_urgency = rank <= 1
    if high_urgency and capacity_sufficient and budget_sufficient:
        mode = "parallel"
    elif low_urgency and (not capacity_sufficient or not budget_sufficient):
        mode = "sequential"
    else:
        mode = "hybrid"

    prospect_dist = _distribute(required_prospects, n_campaigns)

    # ---- Engineer allocation that respects real capacity constraints ----
    # The same engineer is never counted twice across *concurrently active*
    # campaigns. When campaigns run sequentially, the whole team is reused on
    # each one (engineers free up when a campaign completes).
    wave_size = math.ceil(n_campaigns / 2)
    if mode == "parallel":
        # All campaigns active at once -> divide the available team among them.
        eng_dist = _allocate_engineers(engineers, prospect_dist)
        # Each campaign is active for the whole horizon.
        active_months = [months] * n_campaigns
    elif mode == "sequential":
        # One campaign at a time -> each reuses the full team.
        eng_dist = [engineers] * n_campaigns
        per = months / n_campaigns
        active_months = [per] * n_campaigns
    else:  # hybrid: wave 1 runs in parallel, later campaigns reuse the team
        wave1 = _allocate_engineers(engineers, prospect_dist[:wave_size])
        wave2 = [engineers] * (n_campaigns - wave_size)
        eng_dist = wave1 + wave2
        half = months / 2
        active_months = [half] * wave_size + [half] * (n_campaigns - wave_size)

    campaigns = []
    for i in range(n_campaigns):
        c_prospects = prospect_dist[i]
        c_engineers = eng_dist[i]
        c_working_days = active_months[i] * WORKING_DAYS_PER_MONTH
        throughput = int(round(c_engineers * capacity_per_day * c_working_days))
        c_util = round((c_prospects / throughput) * 100, 1) if throughput > 0 else None
        campaigns.append(
            {
                "name": f"Campaign {chr(65 + i)}",
                "prospects": c_prospects,
                "engineers": c_engineers,
                "closures": math.ceil(c_prospects * conv),
                "throughput_prospects": throughput,
                "utilization_pct": c_util,
                "bottleneck": throughput < c_prospects,
            }
        )

    bottlenecks = [c["name"] for c in campaigns if c["bottleneck"]]

    if mode == "parallel":
        waves = [[c["name"] for c in campaigns]]
        reasoning = (
            f"{urgency.capitalize()} urgency with sufficient team capacity and budget — "
            f"run all {n_campaigns} campaigns simultaneously. The {engineers} available "
            f"engineer(s) are split across the active campaigns (no engineer works two at once)."
        )
    elif mode == "sequential":
        waves = [[c["name"]] for c in campaigns]
        constraint = "team capacity" if not capacity_sufficient else "budget"
        reasoning = (
            f"{urgency.capitalize()} urgency with constrained {constraint} — run campaigns "
            f"one after another ({' → '.join(c['name'] for c in campaigns)}). The full "
            f"{engineers}-engineer team frees up and is reused on each successive campaign."
        )
    else:  # hybrid
        first = [c["name"] for c in campaigns[:wave_size]]
        rest = [c["name"] for c in campaigns[wave_size:]]
        waves = [first] + ([rest] if rest else [])
        reasoning = (
            f"Partial capacity with {urgency} urgency — launch {len(first)} campaign(s) in "
            f"parallel (team split across them)"
            + (
                f", then reuse the full {engineers}-engineer team on the remaining {len(rest)}."
                if rest
                else "."
            )
        )

    # ---- Strategic guidance ----
    guidance: list[str] = []
    if ceiling_breached:
        guidance.append(
            "Reduce the revenue target or extend the timeline — it exceeds the realistic market ceiling."
        )
    if investment is not None and not budget_sufficient:
        guidance.append(
            f"Increase GTM budget to at least ${total_cost:,.0f} to fund the required prospect volume."
        )
    if additional_engineers > 0:
        guidance.append(
            f"Hire {additional_engineers} additional GTM engineer(s) to meet the required workload."
        )
    if not capacity_sufficient and low_urgency:
        guidance.append("Extend the timeline to absorb the workload with the current team.")
    if bottlenecks:
        if mode == "parallel" and n_campaigns > 1:
            guidance.append(
                f"Engineer bottleneck on {', '.join(bottlenecks)} — reduce parallelization "
                "(run fewer campaigns at once) or reallocate engineers toward the heavier campaigns."
            )
        else:
            guidance.append(
                f"Engineer bottleneck on {', '.join(bottlenecks)} — add capacity or extend that "
                "campaign's window so throughput can keep up with prospect volume."
            )
    if mode == "sequential" and high_urgency:
        guidance.append(
            "Increase campaign parallelization to compress the timeline now that urgency is high."
        )
    if revenue_assessment == "Aggressive" and not guidance:
        guidance.append("Consider phasing the target or adding resources — the plan is achievable but strained.")
    if not guidance:
        guidance.append("Proceed with the current plan — budget, team capacity, and target are aligned.")

    if capacity_sufficient:
        capacity_message = "Current GTM team capacity is sufficient."
    else:
        capacity_message = "Additional GTM Engineers Recommended."

    # ---- Revenue execution plan (phases / seasonality / carry-forward) ----
    revenue_plan = _build_revenue_plan(
        revenue_target=revenue_target,
        deal_size=deal_size,
        conversion_rate=conv,
        sales_cycle_months=sales_cycle_months,
        time_horizon_months=months,
        execution_start_month=execution_start_month,
        available_engineers=engineers,
        capacity_per_day=capacity_per_day,
        budget_sufficient=budget_sufficient,
        capacity_sufficient=capacity_sufficient,
        ceiling_breached=ceiling_breached,
    )
    if revenue_plan.get("seasonality_impact"):
        guidance.append(revenue_plan["seasonality_impact"])

    return {
        "inputs": {
            "revenue_target_usd": int(round(revenue_target)),
            "average_deal_size_usd": int(round(deal_size)),
            "conversion_rate": conv,
            "lead_acquisition_cost": lead_cost,
            "outreach_cost": out_cost,
            "serp_api_cost": serp_cost,
            "ai_token_cost": token_cost,
            "gtm_engineer_capacity": capacity_per_day,
            "current_gtm_engineers": engineers,
            "time_horizon_months": months,
            "time_urgency": urgency,
            "campaign_count": n_campaigns,
            "email_accounts": email_capacity["email_accounts"],
            "email_account_type": email_capacity["email_account_type"],
            "sales_cycle_months": max(1, int(sales_cycle_months or DEFAULT_SALES_CYCLE_MONTHS)),
            "execution_start_month": revenue_plan["execution_start_month"],
        },
        "required_closures": required_closures,
        "required_prospects": required_prospects,
        "costs": {
            "lead_acquisition_cost_usd": data_cost,
            "outreach_cost_usd": outreach_total,
            "serp_api_cost_usd": serp_total,
            "ai_token_cost_usd": token_total,
            "total_gtm_cost_usd": total_cost,
            "budget_sufficient": budget_sufficient,
            "planned_investment_usd": int(investment) if investment is not None else None,
        },
        "capacity": {
            "working_days": working_days,
            "capacity_per_engineer": capacity_per_engineer,
            "available_capacity": available_capacity,
            "required_capacity": required_prospects,
            "utilization_pct": utilization_pct,
            "capacity_gap": capacity_gap,
            "sufficient": capacity_sufficient,
            "current_engineers": engineers,
            "recommended_engineers": recommended_engineers,
            "additional_engineers": additional_engineers,
            "message": capacity_message,
        },
        "campaign_plan": {
            "mode": mode,
            "campaign_count": n_campaigns,
            "reasoning": reasoning,
            "campaigns": campaigns,
            "waves": waves,
            "bottlenecks": bottlenecks,
            "available_engineers": engineers,
        },
        "revenue_plan": revenue_plan,
        "email_capacity": email_capacity,
        "experiment_plan": experiment_plan,
        "reconciliation": reconciliation,
        "revenue_assessment": revenue_assessment,
        "strategic_guidance": guidance,
    }


async def validate_roi(
    db: Session,
    strategy_id: str,
    investment_usd: float,
    expected_revenue_usd: float,
    timeframe_months: int = 12,
    market_segment: Optional[str] = None,
    notes: Optional[str] = None,
    *,
    revenue_target_usd: Optional[float] = None,
    average_deal_size_usd: Optional[float] = None,
    conversion_rate: float = DEFAULT_CONVERSION_RATE,
    lead_acquisition_cost: float = DEFAULT_LEAD_ACQUISITION_COST,
    outreach_cost: float = DEFAULT_OUTREACH_COST,
    gtm_engineer_capacity: float = DEFAULT_GTM_ENGINEER_CAPACITY,
    current_gtm_engineers: int = DEFAULT_CURRENT_GTM_ENGINEERS,
    time_urgency: str = "medium",
    campaign_count: int = DEFAULT_CAMPAIGN_COUNT,
    sales_cycle_months: int = DEFAULT_SALES_CYCLE_MONTHS,
    execution_start_month: int = 1,
    serp_api_cost: float = DEFAULT_SERP_API_COST,
    ai_token_cost: float = DEFAULT_AI_TOKEN_COST,
    email_accounts: int = DEFAULT_EMAIL_ACCOUNTS,
    email_account_type: str = DEFAULT_EMAIL_ACCOUNT_TYPE,
) -> dict:
    """Validate an investment vs expected-revenue expectation for a profile.

    Returns a dict persisted to ``Strategy.roi_json``. On LLM failure it
    returns a dict containing an ``_error`` key (the route surfaces a 502).
    """
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return {"_error": "Strategy not found"}

    investment = _money(investment_usd)
    expected_revenue = _money(expected_revenue_usd)
    if not investment or investment <= 0:
        return {"_error": "Investment must be a positive number"}
    if expected_revenue is None or expected_revenue < 0:
        return {"_error": "Expected revenue must be a non-negative number"}

    icp = strategy.icp_json or {}
    naics = strategy.naics_json or {}
    tam_sam_som = strategy.tam_sam_som_json or {}
    dd = strategy.discovery_data or {}

    tam = _tier_value(tam_sam_som, "tam")
    sam = _tier_value(tam_sam_som, "sam")
    som = _tier_value(tam_sam_som, "som")

    # ---- Deterministic signals (never trust the model's arithmetic) ----
    expected_multiple = round(expected_revenue / investment, 2) if investment else None
    ceiling_flags: list[str] = []
    if tam and expected_revenue > tam:
        ceiling_flags.append(
            f"Expected revenue (${expected_revenue:,.0f}) exceeds the entire TAM "
            f"(${tam:,.0f}) — capturing 100%+ of the total market is not achievable."
        )
    elif sam and expected_revenue > sam:
        ceiling_flags.append(
            f"Expected revenue (${expected_revenue:,.0f}) exceeds the serviceable "
            f"market SAM (${sam:,.0f}) — that implies winning the whole reachable market."
        )
    elif som and expected_revenue > som * 3:
        ceiling_flags.append(
            f"Expected revenue (${expected_revenue:,.0f}) is more than 3x the "
            f"realistically obtainable SOM (${som:,.0f}) for the chosen timeframe."
        )

    market_ctx = {
        "tam_usd": tam,
        "sam_usd": sam,
        "som_usd": som,
        "methodology": tam_sam_som.get("methodology") if isinstance(tam_sam_som, dict) else None,
    }

    prompt = (
        "You are a B2B GTM finance strategist validating whether a company's ROI "
        "expectation for a specific product is realistic. Be rigorous and honest — "
        "if the expectation is wildly off, say so and propose a corrected target.\n\n"
        f"PRODUCT: {strategy.product_name}\n"
        f"DESCRIPTION: {(strategy.description or '')[:600]}\n"
        f"ICP: {json.dumps(icp)[:1000]}\n"
        f"NAICS segments: {json.dumps(naics)[:700]}\n"
        f"Market sizing for THIS profile (use as the ceiling): {json.dumps(market_ctx, default=str)}\n"
        f"Discovery answers: {json.dumps(dd)[:900] if dd else 'none'}\n"
        f"Target market segment: {market_segment or 'as per ICP'}\n"
        f"User notes: {notes or 'none'}\n\n"
        f"THE EXPECTATION TO VALIDATE:\n"
        f"- Planned GTM investment: ${investment:,.0f}\n"
        f"- Expected revenue/return: ${expected_revenue:,.0f}\n"
        f"- Over timeframe: {timeframe_months} months\n"
        f"- Implied revenue multiple (computed): {expected_multiple}x\n\n"
        "Judge realism using benchmarks that fit THIS product's market, ACV, and "
        "sales motion (not generic SaaS averages). Revenue can never exceed SAM and "
        "realistically should be at or below SOM for the timeframe. Return STRICT JSON:\n"
        "{\n"
        '  "verdict": "realistic" | "too_optimistic" | "too_conservative" | "insufficient_data",\n'
        '  "headline": "one-sentence plain-English verdict",\n'
        '  "benchmark": {\n'
        '     "typical_roi_multiple_low": number, "typical_roi_multiple_high": number,\n'
        '     "typical_payback_months": number, "avg_contract_value_usd": number,\n'
        '     "typical_win_rate_pct": number, "typical_sales_cycle_months": number,\n'
        '     "note": "why these benchmarks fit this product/market"\n'
        "  },\n"
        '  "realistic_revenue_low_usd": integer, "realistic_revenue_high_usd": integer,\n'
        '  "recommended_investment_usd": integer,\n'
        '  "calculator": {\n'
        '     "accounts_reachable": integer, "deals_expected": integer,\n'
        '     "projected_pipeline_usd": integer, "projected_revenue_usd": integer,\n'
        '     "assumptions": ["short strings showing the math"]\n'
        "  },\n"
        '  "corrections": [ {"field": "expected_revenue" | "investment", "from_usd": integer, "to_usd": integer, "reason": "string"} ],\n'
        '  "warnings": ["short strings"],\n'
        '  "rationale": "2-4 sentences explaining the verdict and how to fix the expectation"\n'
        "}\n"
        "All *_usd fields MUST be plain integers (no $, commas, or M/B suffixes)."
    )

    ai = await chat_json(prompt, max_tokens=900)
    if not isinstance(ai, dict) or "_error" in ai:
        return {"_error": (ai or {}).get("_error", "LLM returned no usable result")}

    # ---- Merge deterministic signals over the model output ----
    result = dict(ai)
    result["inputs"] = {
        "investment_usd": int(investment),
        "expected_revenue_usd": int(expected_revenue),
        "timeframe_months": timeframe_months,
        "market_segment": market_segment,
        "notes": notes,
        "revenue_target_usd": (
            int(_money(revenue_target_usd)) if revenue_target_usd is not None and _money(revenue_target_usd) is not None
            else int(expected_revenue)
        ),
        "average_deal_size_usd": (
            int(_money(average_deal_size_usd)) if average_deal_size_usd is not None and _money(average_deal_size_usd) is not None
            else None
        ),
        "conversion_rate": conversion_rate,
        "lead_acquisition_cost": lead_acquisition_cost,
        "outreach_cost": outreach_cost,
        "gtm_engineer_capacity": gtm_engineer_capacity,
        "current_gtm_engineers": current_gtm_engineers,
        "time_urgency": time_urgency,
        "campaign_count": campaign_count,
        "sales_cycle_months": sales_cycle_months,
        "execution_start_month": execution_start_month,
    }
    result["expected_multiple"] = expected_multiple
    result["market_context"] = market_ctx

    # Deterministic ceiling check wins: if revenue breaches TAM/SAM/SOM, force
    # the verdict to "too_optimistic" regardless of what the model said.
    existing_warnings = result.get("warnings")
    warnings = list(existing_warnings) if isinstance(existing_warnings, list) else []
    if ceiling_flags:
        warnings = ceiling_flags + warnings
        if result.get("verdict") not in ("too_optimistic",):
            result["verdict"] = "too_optimistic"
    result["warnings"] = warnings

    # ---- GTM planning layer (deterministic, additive — does not alter the
    # existing feasibility verdict above) ----
    benchmark_block = result.get("benchmark") if isinstance(result.get("benchmark"), dict) else {}
    benchmark_acv = _money(benchmark_block.get("avg_contract_value_usd"))
    # Distinct personas present for this strategy seed the experiment count.
    try:
        persona_count = (
            db.query(Contact.persona_type)
            .filter(Contact.strategy_id == strategy_id, Contact.persona_type.isnot(None))
            .distinct()
            .count()
        )
    except Exception:
        persona_count = 0
    result["gtm_plan"] = _build_gtm_plan(
        revenue_target=(_money(revenue_target_usd) if revenue_target_usd is not None else expected_revenue),
        average_deal_size=_money(average_deal_size_usd),
        conversion_rate=conversion_rate,
        lead_acquisition_cost=lead_acquisition_cost,
        outreach_cost=outreach_cost,
        gtm_engineer_capacity=gtm_engineer_capacity,
        current_gtm_engineers=current_gtm_engineers,
        time_horizon_months=timeframe_months,
        time_urgency=time_urgency,
        campaign_count=campaign_count,
        investment=investment,
        benchmark_acv=benchmark_acv,
        verdict=result.get("verdict"),
        ceiling_breached=bool(ceiling_flags),
        realistic_low=_money(result.get("realistic_revenue_low_usd")),
        realistic_high=_money(result.get("realistic_revenue_high_usd")),
        sales_cycle_months=sales_cycle_months,
        execution_start_month=execution_start_month,
        serp_api_cost=serp_api_cost,
        ai_token_cost=ai_token_cost,
        email_accounts=email_accounts,
        email_account_type=email_account_type,
        persona_count=persona_count,
    )

    result["_provenance"] = stamp(
        source="ai_generated",
        logic=(
            "Validated the user's investment-vs-revenue expectation against this "
            "profile's own TAM/SAM/SOM and ICP. The model proposed profile-specific "
            "benchmarks and a corrected target; revenue ceilings vs TAM/SAM/SOM were "
            "enforced deterministically in code."
        ),
        steps=[
            "Load profile ICP + NAICS + market sizing",
            "Compute implied revenue multiple and TAM/SAM/SOM ceiling checks",
            "Prompt model for benchmarks + corrected target grounded in the ceiling",
            "Override verdict to too_optimistic if revenue breaches market ceiling",
            "Persist verdict + calculator to strategy.roi_json",
        ],
        counts={
            "ceiling_flags": len(ceiling_flags),
            "warnings": len(warnings),
        },
        model=MODEL_NAME,
    )

    strategy.roi_json = result
    db.commit()

    audit_service.log_pipeline_event(
        stage="roi_validation",
        service="roi_validator",
        strategy_id=strategy_id,
        strategy_name=strategy.product_name,
        prompt=prompt,
        inputs={
            "investment_usd": int(investment),
            "expected_revenue_usd": int(expected_revenue),
            "timeframe_months": timeframe_months,
            "tam_sam_som": market_ctx,
        },
        outputs=result,
        decision=(
            f"ROI verdict: {result.get('verdict')} "
            f"(implied {expected_multiple}x over {timeframe_months}mo)"
        ),
        summary=(
            f"ROI Validation: \"{strategy.product_name}\" — {result.get('verdict')} "
            f"({expected_multiple}x)"
        ),
    )

    return result
