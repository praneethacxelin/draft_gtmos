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
from typing import Optional

from sqlalchemy.orm import Session

from app.db import Strategy
from app.llm import chat_json, MODEL_NAME
from app.provenance import stamp
from app.services import audit_service


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


async def validate_roi(
    db: Session,
    strategy_id: str,
    investment_usd: float,
    expected_revenue_usd: float,
    timeframe_months: int = 12,
    market_segment: Optional[str] = None,
    notes: Optional[str] = None,
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
