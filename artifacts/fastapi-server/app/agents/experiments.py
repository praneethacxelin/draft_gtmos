"""Experiments engine — Apollo parameter pattern search.

A product profile can run multiple *experiment batches*. Each batch holds N
experiments, where every experiment is a distinct combination of Apollo facets
(location, industry, employee size, revenue, titles, seniorities, technologies).
The GTM engineer sets N; the LLM seeds N meaningfully-different variations from
the profile's ICP/personas/discovery; the engineer can then edit any facet via
editable forms before running.

Running an experiment calls Apollo (reusing the proven relaxation ladder and
the firmographic helpers in ``s2_signals``) and stores the returned leads
INLINE on the experiment row — they are deliberately NOT written to the live
``contacts`` table, because experiments are exploratory and must not pollute
the real pipeline.

After the batch runs, ``analyze_batch`` feeds the experiment inputs/outputs to
the model in a compact, systematic shape (never the full raw lead dump — that
causes hallucination and weak pattern finding) to:
  1. score each experiment's output *relevancy* against the product profile
     (a construction lead is useless for a healthcare-AI product), and
  2. rank the experiments and justify the single best-performing parameter set.
"""
import json
import logging
import re
from typing import Optional

from sqlalchemy.orm import Session
from app.db import Strategy, ExperimentBatch, Experiment, gen_id
from app.llm import chat_json, MODEL_NAME
from app.provenance import stamp
from app.services import settings_service, clients, fetch_limits, audit_service
from app.agents.s2_signals import (
    _normalize_apollo_locations,
    _resolve_apollo_industries,
)

log = logging.getLogger("gtm.experiments")

# Facets the editable experiment form supports.
_FACET_KEYS = (
    "titles",
    "seniorities",
    "locations",
    "industries",
    "employee_ranges",
    "technologies",
    "revenue_ranges",
    "keywords",
)

# A relevancy score from a tiny or PARTIAL sample is unreliable. Confidence in a
# variant's relevancy is measured against the leads the engineer REQUESTED for
# the batch (so a 9-of-25 sample is discounted versus a full 25-of-25 one), but
# never above this statistical floor — even a "complete" 3-lead batch can't claim
# full trust. A 2-lead "100% relevant" experiment must not out-rank a 25-lead
# "80% relevant" one.
MIN_CONFIDENT_SAMPLE = 10

# A variant must surface at least this many leads to be eligible as the
# relevancy winner — we never crown a winner on a tiny, unreliable sample.
MIN_LEADS_FOR_WINNER = 5

# Discovery org-size labels → Apollo "min,max" employee ranges.
_ORG_SIZE_DIGITS_TO_RANGE = {
    1: "1,10",
    11: "11,50",
    51: "51,200",
    201: "201,1000",
    1000: "1001,100000",
}

_VALID_SENIORITIES = {
    "owner", "founder", "c_suite", "partner", "vp", "head", "director", "manager",
}

_COUNTRY_OR_REGION_HINTS = {
    "north america": "North America",
    "united states": "United States",
    "usa": "United States",
    "u.s.": "United States",
    "us": "United States",
    "canada": "Canada",
    "india": "India",
    "asia-pacific": "Asia-Pacific",
    "asia pacific": "Asia-Pacific",
    "apac": "Asia-Pacific",
    "singapore": "Singapore",
    "australia": "Australia",
    "japan": "Japan",
    "philippines": "Philippines",
    "europe": "Europe",
    "united kingdom": "United Kingdom",
    "uk": "United Kingdom",
    "germany": "Germany",
    "france": "France",
}

_DISCOVERY_INDUSTRY_HINTS = (
    (("b2b saas", "saas companies", "software companies", "software business"), "B2B SaaS"),
    (("e-commerce", "ecommerce", "online retail", "e-commerce brands", "ecommerce brands"), "E-commerce"),
    (("fintech",), "Financial Services"),
    (("healthcare", "health care"), "Healthcare"),
    (("telecom", "telecommunications"), "Telecommunications"),
    (("education", "edtech"), "Education"),
)

_SUPPORT_KEYWORD_HINTS = (
    ("ticket volume", "high ticket volume"),
    ("sla", "SLA management"),
    ("first-response", "first-response time"),
    ("first response", "first-response time"),
    ("customer satisfaction", "customer satisfaction"),
    ("csat", "CSAT improvement"),
    ("multi-channel", "multi-channel support"),
    ("omni", "omnichannel support"),
    ("self-service", "self-service"),
    ("ticket routing", "ticket routing"),
    ("helpdesk", "helpdesk"),
)

_FACET_LABELS = {
    "titles": "job titles",
    "seniorities": "seniority",
    "locations": "locations",
    "industries": "industries",
    "employee_ranges": "company size",
    "technologies": "technologies",
    "keywords": "keywords",
}


def _clean_text(value: object) -> str:
    if isinstance(value, list):
        return " ".join(str(v) for v in value if v)
    return str(value or "")


def _split_csv_text(value: object) -> list[str]:
    if isinstance(value, list):
        chunks = value
    else:
        chunks = re.split(r"[,;\n]+", str(value or ""))
    out: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        item = str(chunk or "").strip()
        if not item or item == "__other__":
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        clean = str(item or "").strip()
        key = clean.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(clean)
    return out


def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _extract_geo_mentions(text: str) -> list[str]:
    low = f" {text.lower()} "
    found: list[str] = []
    for needle, label in _COUNTRY_OR_REGION_HINTS.items():
        pattern = r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])"
        if re.search(pattern, low) and label not in found:
            found.append(label)
    return found


def _profile_titles(strategy: Strategy) -> dict[str, list[str]]:
    dd = strategy.discovery_data or {}
    economic = _split_csv_text(dd.get("economic_buyer"))
    champion = _split_csv_text(dd.get("champion"))
    blockers = _split_csv_text(dd.get("deal_blockers"))
    blockers = [
        b for b in blockers
        if any(w in b.lower() for w in ("it", "security", "finance", "procurement", "director", "manager"))
    ]
    return {
        "economic_buyer": economic,
        "champion": champion,
        "blocker": blockers,
        "all": _dedupe(economic + champion + blockers),
    }


def _seniorities_for_titles(titles: list[str]) -> list[str]:
    out: list[str] = []
    text = " ".join(titles).lower()
    checks = [
        ("cxo", "c_suite"),
        ("chief", "c_suite"),
        ("founder", "founder"),
        ("vp", "vp"),
        ("vice president", "vp"),
        ("head", "head"),
        ("director", "director"),
        ("lead", "manager"),
        ("manager", "manager"),
    ]
    for needle, seniority in checks:
        if needle in text and seniority not in out:
            out.append(seniority)
    return out or ["vp", "head", "director", "manager"]


def _profile_industries(strategy: Strategy) -> list[str]:
    """Discovery-narrowed buyer industries."""
    dd = strategy.discovery_data or {}
    text = " ".join([
        _clean_text(dd.get("perfect_customer")),
        _clean_text(dd.get("company_type")),
    ]).lower()
    out: list[str] = []
    for needles, label in _DISCOVERY_INDUSTRY_HINTS:
        if any(n in text for n in needles) and label not in out:
            out.append(label)
    if out:
        return out

    icp = strategy.icp_json or {}
    return _dedupe([str(i) for i in (icp.get("industries") or []) if isinstance(i, str)])[:4]


def _profile_technologies(strategy: Strategy) -> list[str]:
    dd = strategy.discovery_data or {}
    tools = _split_csv_text(dd.get("alternatives"))
    return [
        t for t in tools
        if not any(x in t.lower() for x in ("gmail", "email", "shared inbox"))
    ]


def _profile_keywords(strategy: Strategy) -> list[str]:
    dd = strategy.discovery_data or {}
    text = " ".join([
        _clean_text(dd.get("pain_points")),
        _clean_text(dd.get("triggers")),
        _clean_text(dd.get("uvp")),
        _clean_text(dd.get("perfect_customer")),
    ]).lower()
    out: list[str] = []
    for needle, label in _SUPPORT_KEYWORD_HINTS:
        if needle in text and label not in out:
            out.append(label)
    return out or ["customer support", "helpdesk", "SLA management", "first-response time"]


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def serialize_experiment(e: Experiment, strategy: Strategy | None = None) -> dict:
    trust = evaluate_experiment_trust(strategy, e.params_json or {}, e.result_summary_json) if strategy else None
    return {
        "id": e.id,
        "batch_id": e.batch_id,
        "strategy_id": e.strategy_id,
        "idx": e.idx,
        "name": e.name,
        "hypothesis": e.hypothesis,
        "params": e.params_json or {},
        "source": e.source,
        "trust": trust,
        "status": e.status,
        "result_summary": e.result_summary_json,
        "leads": e.leads_json or [],
        "relevancy": e.relevancy_json,
        "score": e.score,
        "error": e.error,
        "cohort_size": e.cohort_size,
        "live_launched_at": e.live_launched_at.isoformat() if e.live_launched_at else None,
        "live_metrics": e.live_metrics_json,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


def serialize_batch(db: Session, b: ExperimentBatch, include_experiments: bool = True) -> dict:
    strategy = db.query(Strategy).filter(Strategy.id == b.strategy_id).first()
    out = {
        "id": b.id,
        "strategy_id": b.strategy_id,
        "name": b.name,
        "n_experiments": b.n_experiments,
        "leads_per_experiment": b.leads_per_experiment,
        "status": b.status,
        "hypothesis": b.hypothesis,
        "best_experiment_id": b.best_experiment_id,
        "analysis": b.analysis_json,
        "live_status": b.live_status,
        "window_months": b.window_months,
        "window_started_at": b.window_started_at.isoformat() if b.window_started_at else None,
        "window_ends_at": b.window_ends_at.isoformat() if b.window_ends_at else None,
        "live_winner_experiment_id": b.live_winner_experiment_id,
        "live_analysis": b.live_analysis_json,
        "targeting_contract": discovery_targeting_contract(strategy) if strategy else None,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    }
    if include_experiments:
        rows = (
            db.query(Experiment)
            .filter(Experiment.batch_id == b.id)
            .order_by(Experiment.idx.asc())
            .all()
        )
        out["experiments"] = [serialize_experiment(e, strategy) for e in rows]
    return out


# ---------------------------------------------------------------------------
# Param sanitization
# ---------------------------------------------------------------------------

def sanitize_params(raw: dict) -> dict:
    """Clean a user/AI-supplied facet form into Apollo-safe values."""
    raw = raw if isinstance(raw, dict) else {}
    out: dict = {}

    def _list(key):
        val = raw.get(key)
        if isinstance(val, str):
            val = [v.strip() for v in val.split(",")]
        if not isinstance(val, list):
            return []
        return [str(v).strip() for v in val if v and str(v).strip() and str(v).strip() != "__other__"]

    titles = _list("titles")
    if titles:
        out["titles"] = titles[:10]

    seniorities = [s.lower() for s in _list("seniorities") if s.lower() in _VALID_SENIORITIES]
    if seniorities:
        out["seniorities"] = seniorities

    locations = _normalize_apollo_locations(_list("locations"))
    if locations:
        out["locations"] = locations

    industries = _list("industries")
    if industries:
        out["industries"] = industries[:6]

    # Employee ranges — accept "51,200" or "51-200" forms.
    emp: list[str] = []
    for r in _list("employee_ranges"):
        norm = r.replace("-", ",").replace(" ", "")
        parts = [p for p in norm.split(",") if p.isdigit()]
        if len(parts) == 2:
            emp.append(f"{parts[0]},{parts[1]}")
    if emp:
        out["employee_ranges"] = emp

    techs = _list("technologies")
    if techs:
        out["technologies"] = techs[:6]

    revenue = _list("revenue_ranges")
    if revenue:
        out["revenue_ranges"] = revenue[:4]

    # Free-text keywords (Apollo q_keywords) — broadens reach to buyers whose
    # context matches even when firmographics are sparse.
    keywords = _list("keywords")
    if keywords:
        out["keywords"] = keywords[:8]

    return out


# ---------------------------------------------------------------------------
# Profile grounding helpers (keep experiments anchored to S1 + discovery data)
# ---------------------------------------------------------------------------

def _profile_geographies(strategy: Strategy) -> list[str]:
    """Real target countries for this profile.

    The user's discovery ``target_geos`` selection is ground truth and takes
    precedence — the S1 ICP geographies are AI-inferred and often broader (e.g.
    it may add "Europe" the user never selected), which is exactly what made
    off-target countries like Germany/UK leak into experiments. We only fall
    back to ICP geographies when the user left discovery geographies blank.

    Regions ("Asia-Pacific") are expanded to member countries; non-geographic
    tokens ("Global", "Other") are dropped so Apollo isn't fed junk.
    """
    icp = strategy.icp_json or {}
    dd = strategy.discovery_data or {}

    # If the user's prose narrows the market (for example "in India or North
    # America") treat that as the sharpest expression of intent. Checkbox
    # regions like "Asia-Pacific" are useful fallbacks, but they can be too
    # broad for Apollo experiments.
    perfect_customer = _clean_text(dd.get("perfect_customer"))
    raw: list[str] = _extract_geo_mentions(perfect_customer)

    selected_raw: list[str] = []
    tg = dd.get("target_geos")
    if isinstance(tg, list):
        selected_raw.extend([g for g in tg if isinstance(g, str)])
    elif isinstance(tg, str) and tg.strip():
        selected_raw.append(tg)

    if not raw:
        raw.extend(selected_raw)

    # Only widen with the inferred ICP geographies if discovery had none.
    if not raw:
        for g in (icp.get("geographies") or []):
            if isinstance(g, str):
                raw.append(g)

    raw = [
        g for g in raw
        if g.strip().lower() not in ("global", "other", "__other__", "")
    ]
    return _normalize_apollo_locations(raw)


def _profile_employee_ranges(strategy: Strategy) -> list[str]:
    """Apollo employee ranges derived from the discovery org_size selections."""
    dd = strategy.discovery_data or {}
    sizes = dd.get("org_size")
    if isinstance(sizes, str):
        sizes = [sizes]
    if not isinstance(sizes, list):
        return []
    out: list[str] = []
    for s in sizes:
        if not isinstance(s, str):
            continue
        head = s.split("(")[0].replace(",", "").replace("+", "")
        digits = "".join(ch if ch.isdigit() else " " for ch in head).split()
        if not digits:
            continue
        low = int(digits[0])
        rng = _ORG_SIZE_DIGITS_TO_RANGE.get(low)
        if rng and rng not in out:
            out.append(rng)
    return out


def discovery_targeting_contract(strategy: Strategy) -> dict:
    """Single source of truth for experiment targeting.

    When discovery data exists, experiments should vary a small number of
    facets inside this contract instead of asking the model to re-discover the
    market from scratch.
    """
    if not strategy:
        return {"strict": False}
    dd = strategy.discovery_data or {}
    titles = _profile_titles(strategy)
    industries = _profile_industries(strategy)
    locations = _profile_geographies(strategy)
    employee_ranges = _profile_employee_ranges(strategy)
    technologies = _profile_technologies(strategy)
    keywords = _profile_keywords(strategy)
    strict = bool(
        dd.get("perfect_customer")
        or dd.get("org_size")
        or dd.get("target_geos")
        or dd.get("economic_buyer")
        or dd.get("champion")
    )
    return {
        "strict": strict,
        "source": "discovery_questionnaire" if strict else "inferred_icp",
        "locked": {
            "locations": locations,
            "industries": industries,
            "employee_ranges": employee_ranges,
            "titles": titles["all"],
            "technologies": technologies,
            "keywords": keywords,
        },
        "personas": {
            "economic_buyer": titles["economic_buyer"],
            "champion": titles["champion"],
            "blocker": titles["blocker"],
        },
        "allowed_variation": [
            "industry_subsegment",
            "company_size_band",
            "buyer_persona",
            "competitor_tool",
            "pain_keyword",
        ],
        "notes": [
            "Discovery answers override broad AI-inferred ICP fields.",
            "Geography is held to the explicit perfect-customer prose when it narrows checkbox regions.",
        ],
    }


def _matches_allowed(value: str, allowed: list[str]) -> bool:
    key = _norm(value)
    return any(key == _norm(a) for a in allowed)


def _clamp_to_allowed(values: list[str], allowed: list[str]) -> tuple[list[str], list[str]]:
    if not allowed:
        return values, []
    kept = [v for v in values if _matches_allowed(v, allowed)]
    rejected = [v for v in values if not _matches_allowed(v, allowed)]
    return _dedupe(kept), _dedupe(rejected)


def _is_title_close(value: str, allowed: list[str]) -> bool:
    val = value.lower()
    if _matches_allowed(value, allowed):
        return True
    support_terms = ("support", "customer success", "customer experience", "cx", "customer care", "it operations")
    return any(term in val for term in support_terms)


def apply_discovery_contract(strategy: Strategy, params: dict, fill_missing: bool = True, allowed_override: dict | None = None) -> tuple[dict, dict]:
    """Clamp generated or edited params to the discovery contract.

    The returned metadata is intentionally verbose so the UI and audit trail can
    explain what was kept, corrected, or inferred.

    ``allowed_override`` lets a caller (e.g. the seed-experiments gate where the
    GTM engineer reviewed/edited the base facets) replace the discovery-derived
    allowed sets, so experiments are clamped to the engineer's reviewed values
    instead of the raw discovery contract.
    """
    params = sanitize_params(params)
    contract = discovery_targeting_contract(strategy)
    locked = dict(contract.get("locked") or {})
    if allowed_override:
        for k, v in allowed_override.items():
            cleaned = [str(x) for x in (v or []) if x is not None and str(x).strip()]
            if cleaned:
                locked[k] = cleaned
    corrections: list[dict] = []

    def replace_facet(key: str, fallback_count: int | None = None):
        allowed = locked.get(key) or []
        if not allowed:
            return
        current = params.get(key) or []
        kept, rejected = _clamp_to_allowed(current, allowed)
        if rejected:
            corrections.append({
                "facet": key,
                "removed": rejected,
                "reason": f"Outside discovery {_FACET_LABELS.get(key, key)} contract",
            })
        if kept:
            params[key] = kept
        elif fill_missing:
            params[key] = list(allowed[:fallback_count]) if fallback_count else list(allowed)
            if current:
                corrections.append({
                    "facet": key,
                    "added": params[key],
                    "reason": "Replaced off-profile values with discovery-backed values",
                })

    replace_facet("locations")
    replace_facet("industries", fallback_count=2)
    replace_facet("employee_ranges")
    replace_facet("technologies", fallback_count=3)

    titles = locked.get("titles") or []
    if titles:
        current_titles = params.get("titles") or []
        kept = [t for t in current_titles if _is_title_close(t, titles)]
        rejected = [t for t in current_titles if t not in kept]
        if rejected:
            corrections.append({
                "facet": "titles",
                "removed": rejected,
                "reason": "Title did not map to the discovery buying committee",
            })
        if kept:
            params["titles"] = _dedupe(kept)
        elif fill_missing:
            params["titles"] = titles[:6]
    if not params.get("seniorities") and params.get("titles"):
        params["seniorities"] = _seniorities_for_titles(params["titles"])
    if fill_missing and not params.get("keywords") and locked.get("keywords"):
        params["keywords"] = list(locked["keywords"][:4])

    return params, {
        "contract_source": contract.get("source"),
        "corrections": corrections,
    }


def evaluate_experiment_trust(
    strategy: Strategy | None,
    params: dict,
    result_summary: dict | None = None,
) -> dict:
    if not strategy:
        return {"status": "unknown", "badges": []}
    contract = discovery_targeting_contract(strategy)
    locked = contract.get("locked") or {}
    params = sanitize_params(params)
    violations: list[dict] = []

    for key in ("locations", "industries", "employee_ranges", "technologies"):
        allowed = locked.get(key) or []
        values = params.get(key) or []
        if allowed and values:
            rejected = [v for v in values if not _matches_allowed(v, allowed)]
            if rejected:
                violations.append({
                    "facet": key,
                    "values": rejected,
                    "allowed": allowed,
                    "reason": f"Outside discovery {_FACET_LABELS.get(key, key)} contract",
                })

    titles = locked.get("titles") or []
    title_values = params.get("titles") or []
    if titles and title_values:
        rejected_titles = [t for t in title_values if not _is_title_close(t, titles)]
        if rejected_titles:
            violations.append({
                "facet": "titles",
                "values": rejected_titles,
                "allowed": titles,
                "reason": "Outside discovery buying-committee contract",
            })

    missing_required = [
        key for key in ("locations", "industries", "employee_ranges", "titles")
        if locked.get(key) and not params.get(key)
    ]
    badges: list[str] = []
    if contract.get("strict") and not violations and not missing_required:
        badges.extend(["Discovery-locked", "Controlled"])
        status = "controlled"
    elif violations:
        badges.append("Off-profile")
        status = "off_profile"
    else:
        badges.append("Inferred")
        status = "inferred"
    if result_summary and result_summary.get("relaxed"):
        badges.append("Relaxed by Apollo")

    held_constant = [
        key for key in ("locations", "employee_ranges")
        if locked.get(key) and params.get(key)
    ]
    changed_facets = [
        key for key in ("industries", "titles", "technologies", "keywords")
        if params.get(key)
    ]
    return {
        "status": status,
        "badges": badges,
        "violations": violations,
        "missing_required": missing_required,
        "changed_facets": changed_facets,
        "held_constant": held_constant,
        "contract_source": contract.get("source"),
    }


# ---------------------------------------------------------------------------
# Seeding (AI generates N distinct experiments)
# ---------------------------------------------------------------------------

def _base_contract_params(strategy: Strategy) -> dict:
    contract = discovery_targeting_contract(strategy)
    locked = contract.get("locked") or {}
    titles = locked.get("titles") or []
    return {
        "titles": titles[:6],
        "seniorities": _seniorities_for_titles(titles),
        "locations": list(locked.get("locations") or []),
        "industries": list((locked.get("industries") or [])[:2]),
        "employee_ranges": list(locked.get("employee_ranges") or []),
        "technologies": list((locked.get("technologies") or [])[:3]),
        "keywords": list((locked.get("keywords") or [])[:4]),
    }


def _experiment_row(name: str, hypothesis: str, params: dict, factor: str) -> dict:
    return {
        "name": name,
        "hypothesis": hypothesis,
        "params": {k: v for k, v in params.items() if v},
        "factor": factor,
    }


def _discovery_locked_experiments(strategy: Strategy, n: int) -> list[dict]:
    """Deterministic, one-factor-at-a-time variants for completed discovery.

    This keeps the learning loop clean: if a variant wins, we can explain which
    parameter moved while the rest of the target profile stayed anchored.
    """
    contract = discovery_targeting_contract(strategy)
    if not contract.get("strict"):
        return []
    locked = contract.get("locked") or {}
    personas = contract.get("personas") or {}
    base = _base_contract_params(strategy)
    rows: list[dict] = []

    # ORDER MATTERS: the batch size (n) is ROI-capacity driven and often small
    # (~6), and we truncate to the first n distinct rows below. So the highest
    # buying-signal hypotheses are emitted FIRST — the baseline control, then the
    # competitor-migration cohort (accounts already running a named rival tool are
    # the strongest "ready to switch" signal), then the decision-maker and
    # champion personas — before the lower-signal industry/size/keyword splits.
    rows.append(_experiment_row(
        "Discovery Baseline",
        "Tests the full discovery-backed ICP before isolating individual facets.",
        dict(base),
        "baseline",
    ))

    technologies = locked.get("technologies") or []
    if technologies:
        p = dict(base)
        p["technologies"] = technologies[:4]
        p["keywords"] = _dedupe((p.get("keywords") or []) + ["migration", "vendor consolidation"])[:6]
        rows.append(_experiment_row(
            "Competitor Migration Signals",
            "Isolates accounts already using named support tools that may be ready to switch or consolidate.",
            p,
            "technology",
        ))

    economic = personas.get("economic_buyer") or []
    if economic:
        p = dict(base)
        p["titles"] = economic[:6]
        p["seniorities"] = _seniorities_for_titles(p["titles"])
        rows.append(_experiment_row(
            "Economic Buyer Focus",
            "Isolates executive CX/support buyers while holding market, size, and industry constant.",
            p,
            "persona",
        ))

    champion = personas.get("champion") or []
    if champion:
        p = dict(base)
        p["titles"] = champion[:6]
        p["seniorities"] = _seniorities_for_titles(p["titles"])
        rows.append(_experiment_row(
            "Champion Operator Focus",
            "Isolates frontline support and success champions while holding firmographics constant.",
            p,
            "persona",
        ))

    industries = locked.get("industries") or []
    for industry in industries:
        p = dict(base)
        p["industries"] = [industry]
        rows.append(_experiment_row(
            f"{industry} Support Teams",
            f"Isolates whether {industry} buyers produce higher-fit Freshdesk leads.",
            p,
            "industry",
        ))

    for emp in (locked.get("employee_ranges") or []):
        p = dict(base)
        p["employee_ranges"] = [emp]
        label = emp.replace(",", "-")
        rows.append(_experiment_row(
            f"{label} Company Size",
            f"Isolates whether the {label} employee band produces stronger support-software demand.",
            p,
            "company_size",
        ))

    keywords = locked.get("keywords") or []
    for keyword in keywords[:3]:
        p = dict(base)
        p["keywords"] = [keyword]
        rows.append(_experiment_row(
            f"{keyword.title()} Trigger",
            f"Isolates the pain signal '{keyword}' while keeping the rest of the ICP fixed.",
            p,
            "pain_keyword",
        ))

    deduped: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        sig = json.dumps(row.get("params") or {}, sort_keys=True, default=str)
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(row)
        if len(deduped) >= n:
            break
    return deduped

async def seed_batch(
    db: Session,
    strategy_id: str,
    n: int,
    leads_per_experiment: int = 10,
    hypothesis: Optional[str] = None,
    strict_discovery: bool = True,
    override_facets: Optional[dict] = None,
) -> dict:
    """Create a batch + N AI-seeded experiments with distinct Apollo params."""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return {"_error": "Strategy not found"}

    n = max(1, min(int(n or 3), 12))
    limits = fetch_limits.get_limits(db, strategy.user_id or "user_public")
    leads_per_experiment = fetch_limits.clamp("leads_per_run", leads_per_experiment, limits)

    icp = strategy.icp_json or {}
    dd = strategy.discovery_data or {}
    personas = strategy.personas_json or {}

    allowed_locations = _profile_geographies(strategy)
    profile_emp_ranges = _profile_employee_ranges(strategy)
    profile_industries = _profile_industries(strategy)
    profile_titles = _profile_titles(strategy)["all"]
    profile_tools = _profile_technologies(strategy)

    loc_constraint = (
        "\n\nHARD CONSTRAINT — TARGET GEOGRAPHIES: This product is sold ONLY into "
        f"these countries: {', '.join(allowed_locations)}. EVERY experiment's \"locations\" "
        "MUST be a non-empty subset of this EXACT list — never use any country outside it "
        "(do NOT invent Germany, UK, etc. unless they appear above). Hold geography close "
        "to this list and create lead-quality variation using the OTHER facets (industry, "
        "employee size, seniority, technology, keywords) instead.\n"
        if allowed_locations
        else "\n\nLocations must be specific COUNTRY names, never regions like 'Asia-Pacific'.\n"
    )
    size_hint = (
        f"TARGET COMPANY SIZES — draw employee_ranges from: {', '.join(profile_emp_ranges)}.\n"
        if profile_emp_ranges
        else ""
    )

    industry_hint = (
        f"TARGET INDUSTRIES - draw industries only from: {', '.join(profile_industries)}.\n"
        if profile_industries
        else ""
    )
    title_hint = (
        f"TARGET BUYING COMMITTEE - draw job titles from: {', '.join(profile_titles)}.\n"
        if profile_titles
        else ""
    )
    tool_hint = (
        f"TARGET CURRENT/COMPETITOR TOOLS - draw technologies from: {', '.join(profile_tools)}.\n"
        if profile_tools
        else ""
    )

    prompt = (
        "You are a GTM growth engineer designing a SERIES of Apollo.io people-search "
        "experiments to discover which firmographic parameter combination surfaces the "
        "highest-fit leads for a product. Each experiment must vary the parameters "
        "meaningfully from the others (change industry, employee size, seniority, "
        "technology, or keywords) so we can isolate what drives lead quality. Do NOT "
        "repeat the same combination twice. Every facet you choose MUST be justified by "
        "the product's ICP / personas / discovery data below — do not invent unrelated "
        "industries, geographies, or titles.\n\n"
        "IMPORTANT: The DISCOVERY data contains the user's explicit, ground-truth requirements. "
        "It MUST take precedence over the AI-inferred ICP. If the DISCOVERY data narrows the "
        "target market (e.g. specific company types, industries, or a 'perfect customer' profile), "
        "you MUST strictly obey that narrowing and ignore any broader industries in the ICP.\n\n"
        f"PRODUCT: {strategy.product_name}\n"
        f"DESCRIPTION: {(strategy.description or '')[:500]}\n"
        f"ICP: {json.dumps(icp)[:1100]}\n"
        f"PERSONAS: {json.dumps(personas)[:700] if personas else 'none'}\n"
        f"DISCOVERY: {json.dumps(dd)[:900] if dd else 'none'}\n"
        f"{loc_constraint}{size_hint}{industry_hint}{title_hint}{tool_hint}"
        f"Design EXACTLY {n} experiments.\n\n"
        "When discovery data exists, hold the target profile constant and vary only "
        "one meaningful factor per experiment: industry, company size, buyer persona, "
        "competitor technology, or pain keyword. Do not vary geography unless it is "
        "inside the allowed country list and the experiment is explicitly a geography test.\n\n"
        "Return STRICT JSON: {\"experiments\": [ {\n"
        '  "name": "short label",\n'
        '  "hypothesis": "what this variation tests in one sentence",\n'
        '  "params": {\n'
        '     "titles": [4-8 specific buyer job titles],\n'
        '     "seniorities": [subset of owner,founder,c_suite,partner,vp,head,director,manager],\n'
        '     "locations": [COUNTRY names from the allowed list above],\n'
        '     "industries": [the buyer\'s OWN industry — companies that USE the product],\n'
        '     "employee_ranges": ["min,max" strings e.g. "51,200"],\n'
        '     "technologies": [specific tools these buyers likely use],\n'
        '     "keywords": [1-4 free-text context terms, e.g. "customer support", "helpdesk"]\n'
        "  } } ] }\n"
        "Only include a facet key when it sharpens the experiment; omit empty ones."
    )

    # Prefer the deterministic, one-factor-at-a-time blueprint when discovery is
    # complete (strict contract). It holds the discovery-backed ICP constant and
    # varies a single facet per experiment, so a winning variant is explainable
    # ("industry X won while geo/size/titles were held fixed"). The AI path only
    # fills any remaining slots — or runs entirely when discovery is too thin for
    # a strict contract.
    #
    # When ``strict_discovery`` is False the GTM engineer has chosen the
    # "AI knowledge" mode: skip the discovery-locked blueprint entirely and let
    # the model draft all N experiments from its own reasoning (still grounded in
    # the product context, just not hard-clamped to the discovery answers).
    if strict_discovery:
        raw_experiments: list[dict] = list(_discovery_locked_experiments(strategy, n))
        blueprint_count = len(raw_experiments)
        if blueprint_count < n:
            ai = await chat_json(prompt, max_tokens=1600)
            if isinstance(ai, dict) and isinstance(ai.get("experiments"), list):
                for r in ai["experiments"]:
                    if isinstance(r, dict):
                        raw_experiments.append(r)
                    if len(raw_experiments) >= n:
                        break
    else:
        raw_experiments = []
        blueprint_count = 0
        ai = await chat_json(prompt, max_tokens=1600)
        if isinstance(ai, dict) and isinstance(ai.get("experiments"), list):
            for r in ai["experiments"]:
                if isinstance(r, dict):
                    raw_experiments.append(r)
                if len(raw_experiments) >= n:
                    break

    batch = ExperimentBatch(
        user_id=strategy.user_id,
        strategy_id=strategy_id,
        name=f"Experiment batch · {strategy.product_name}",
        n_experiments=n,
        leads_per_experiment=leads_per_experiment,
        hypothesis=hypothesis,
        status="seeded",
    )
    db.add(batch)
    db.flush()

    created = 0
    for i in range(n):
        raw = raw_experiments[i] if i < len(raw_experiments) else {}
        raw_params = raw.get("params") if isinstance(raw, dict) else {}
        if strict_discovery:
            # Clamp every experiment (blueprint OR AI) to the discovery contract
            # so no off-profile industry/geography/title can leak into the seed.
            # IMPORTANT: do NOT pass the gate's reviewed facets as an override
            # here — the blueprint deliberately varies ONE facet per experiment
            # (e.g. industry=E-commerce vs B2B SaaS), and locking to the single
            # reviewed value would collapse all N experiments to identical params.
            params, _meta = apply_discovery_contract(strategy, raw_params or {})
        else:
            # AI-knowledge mode: keep the model's own firmographic choices. Only
            # sanitize + backfill the essentials so the experiment is runnable, and
            # seed any empty facet from the engineer-reviewed base facets.
            params = sanitize_params(raw_params or {})
            if override_facets:
                for k, v in override_facets.items():
                    cleaned = [str(x) for x in (v or []) if x is not None and str(x).strip()]
                    if cleaned and not params.get(k):
                        params[k] = cleaned
            if params.get("titles") and not params.get("seniorities"):
                params["seniorities"] = _seniorities_for_titles(params["titles"])
        exp = Experiment(
            batch_id=batch.id,
            strategy_id=strategy_id,
            idx=i + 1,
            name=(raw.get("name") if isinstance(raw, dict) else None) or f"Experiment {i + 1}",
            hypothesis=raw.get("hypothesis") if isinstance(raw, dict) else None,
            params_json=params,
            source="ai" if params else "user",
            status="draft",
        )
        db.add(exp)
        created += 1

    db.commit()
    db.refresh(batch)

    seed_mode = (
        "blueprint" if blueprint_count >= n
        else ("blueprint+ai" if blueprint_count else "ai")
    )
    if not strict_discovery:
        seed_mode = "ai_knowledge"
    audit_service.log_pipeline_event(
        stage="experiment_seed",
        service="experiments",
        strategy_id=strategy_id,
        strategy_name=strategy.product_name,
        prompt=prompt,
        inputs={
            "n": n,
            "leads_per_experiment": leads_per_experiment,
            "seed_mode": seed_mode,
            "blueprint_count": blueprint_count,
        },
        outputs={"batch_id": batch.id, "experiments_created": created},
        decision=f"Seeded {created} experiments ({seed_mode}) for \"{strategy.product_name}\"",
        summary=f"Experiments → Seed: {created} variations for \"{strategy.product_name}\" ({seed_mode})",
    )

    return serialize_batch(db, batch)


# ---------------------------------------------------------------------------
# Running a single experiment against Apollo
# ---------------------------------------------------------------------------

def _normalize_lead(p: dict) -> dict:
    org = p.get("organization") or {}
    full_name = (
        p.get("name")
        or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        or "Unknown"
    )
    # Apollo filters by *person* location (person_locations), so the lead may sit
    # in the target geography even when the company HQ is elsewhere. Show the
    # person's own location first (that's what the geo filter actually matched),
    # and keep the company HQ separately for transparency.
    person_loc = ", ".join(
        [x for x in (p.get("city"), p.get("state"), p.get("country")) if x]
    )
    hq_loc = ", ".join(
        [x for x in (org.get("headquarters_city"), org.get("headquarters_country")) if x]
    )
    return {
        "name": full_name,
        "title": p.get("title"),
        "seniority": p.get("seniority"),
        "company": org.get("name") or "Unknown Co",
        "domain": clients.apollo_org_domain(org),
        "industry": org.get("industry"),
        "employee_count": org.get("estimated_num_employees"),
        "revenue_range": org.get("organization_revenue_printed"),
        "location": person_loc or hq_loc or None,
        "hq_location": hq_loc or None,
        "linkedin_url": p.get("linkedin_url"),
        # Apollo person id — carried so a promoted contact can later reveal its
        # work email by id (the reliable path) instead of re-matching by name.
        "apollo_id": p.get("id"),
    }


def _build_ladder(params: dict) -> list[tuple[str, dict]]:
    """Relaxation ladder for one experiment.

    Keeps the experiment's distinguishing anchors (locations + employee size +
    titles/seniority) as long as possible and peels off the fragile free-text
    facets (technologies, industries) that silently zero-out Apollo results.
    """
    base = {k: v for k, v in params.items() if v}
    ladder: list[tuple[str, dict]] = [("precise (all facets)", dict(base))]
    # Peel the fragile free-text facets in order — but keep the TECHNOLOGY signal
    # as long as possible. Technology UIDs resolve cleanly via the bundled Apollo
    # catalogue (supported_technologies.csv), so they are a strong, valid signal
    # (e.g. "uses Zendesk" = a migration target), whereas q_keywords and free-text
    # industries are what actually over-narrow / silently zero-out the query.
    # So peel keywords, then industries, and only drop technologies as a last
    # resort before falling back to the anchors.
    cur = dict(base)
    dropped: list[str] = []
    for facet in ("keywords", "industries", "technologies"):
        if facet in cur:
            cur = {k: v for k, v in cur.items() if k != facet}
            dropped.append(facet)
            ladder.append((f"dropped {', '.join(dropped)}", dict(cur)))
    # Last resort: titles/seniority + geo + size only.
    t3 = {k: v for k, v in cur.items() if k in ("titles", "seniorities", "locations", "employee_ranges")}
    if t3 and t3 != cur:
        ladder.append(("anchors only (titles+geo+size)", t3))
    return ladder


async def run_experiment(db: Session, experiment_id: str) -> dict:
    """Run one experiment's Apollo query and store leads inline."""
    exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        return {"_error": "Experiment not found"}
    strategy = db.query(Strategy).filter(Strategy.id == exp.strategy_id).first()
    if not strategy:
        return {"_error": "Strategy not found"}

    batch = db.query(ExperimentBatch).filter(ExperimentBatch.id == exp.batch_id).first()
    limits = fetch_limits.get_limits(db, strategy.user_id or "user_public")
    n_leads = fetch_limits.clamp(
        "leads_per_run",
        batch.leads_per_experiment if batch else None,
        limits,
    )

    apollo_key = settings_service.get_key(db, strategy.user_id, "apollo")
    params = sanitize_params(exp.params_json or {})
    exp.params_json = params
    exp.status = "running"
    exp.error = None
    db.commit()

    if not apollo_key:
        exp.status = "failed"
        exp.error = "Apollo API key not configured — add it in Settings to run experiments."
        db.commit()
        return serialize_experiment(exp)

    # Resolve fragile facets to Apollo taxonomy before searching.
    run_params = dict(params)
    industry_notes: list[dict] = []
    if params.get("industries"):
        resolved_inds, industry_notes = _resolve_apollo_industries(params["industries"])
        if resolved_inds:
            run_params["industries"] = resolved_inds
        else:
            run_params.pop("industries", None)
    if params.get("technologies"):
        tech_uids = clients.apollo_resolve_technology_uids(
            apollo_key,
            params["technologies"][:5],
            _strategy_id=strategy.id,
            _strategy_name=strategy.product_name,
        )
        if tech_uids:
            run_params["technologies"] = tech_uids[:5]
        else:
            run_params.pop("technologies", None)

    # Relax progressively until we gather a sample large enough for a FAIR
    # comparison. The old behavior stopped at the first non-empty tier, so a
    # narrow variant could be judged on just 2 leads while a loose one had 25.
    # Now we keep peeling the fragile facets until a tier returns at least the
    # requested sample size, otherwise we keep the tier that surfaced the most.
    ladder = _build_ladder(run_params)
    target = n_leads or 10
    apollo_results = None
    used_tier = None
    best_count = 0
    tiers_tried = 0
    seen: set[str] = set()
    for tier_name, tier_filters in ladder:
        cleaned = {k: v for k, v in tier_filters.items() if v}
        sig = json.dumps(cleaned, sort_keys=True, default=str)
        if not cleaned or sig in seen:
            continue
        seen.add(sig)
        tiers_tried += 1
        tier_results = clients.apollo_people_search(
            apollo_key,
            cleaned,
            per_page=min(n_leads or 10, 100),
            _strategy_id=strategy.id,
            _strategy_name=strategy.product_name,
        )
        tier_count = len(tier_results or [])
        # Keep the richest sample seen so far.
        if tier_count > best_count:
            best_count = tier_count
            apollo_results = tier_results
            used_tier = tier_name
        # Stop as soon as a tier yields a full, comparable sample.
        if tier_count >= target:
            break

    leads = [_normalize_lead(p) for p in (apollo_results or [])][: (n_leads or 10)]

    # Firmographic spread — quick descriptive stats for the analysis step.
    industries = {}
    locations = {}
    for lead in leads:
        if lead.get("industry"):
            industries[lead["industry"]] = industries.get(lead["industry"], 0) + 1
        if lead.get("location"):
            locations[lead["location"]] = locations.get(lead["location"], 0) + 1

    summary = {
        "lead_count": len(leads),
        "winning_tier": used_tier,
        "relaxed": bool(used_tier and used_tier != "precise (all facets)"),
        "tiers_tried": tiers_tried,
        "sample_sufficient": len(leads) >= (n_leads or 10),
        "industry_spread": industries,
        "location_spread": locations,
        "industry_resolution": industry_notes,
        "requested_leads": n_leads,
        "_provenance": stamp(
            source="apollo",
            logic=(
                "Ran this experiment's Apollo facets through the relaxation ladder "
                "(peeling fragile free-text facets while keeping geo/size/title "
                "anchors) and stored the returned leads inline for analysis. Leads "
                "are NOT written to the contacts table."
            ),
            steps=[
                "Sanitize + resolve facets (industries, technology UIDs)",
                "Try precise query, then relax fragile facets if 0 results",
                "Normalize returned people into lead rows",
                "Compute industry/location spread for the analysis step",
            ],
            counts={"leads": len(leads)},
            model=None,
        ),
    }

    exp.leads_json = leads
    exp.result_summary_json = summary
    exp.status = "done"
    # Reset stale analysis — must be recomputed for the batch.
    exp.relevancy_json = None
    exp.score = None
    db.commit()

    if batch and batch.status in ("seeded", "draft", "analyzed"):
        batch.best_experiment_id = None
        batch.analysis_json = None
        batch.status = "running"
        db.commit()

    audit_service.log_pipeline_event(
        stage="experiment_run",
        service="experiments",
        strategy_id=strategy.id,
        strategy_name=strategy.product_name,
        inputs={"experiment": exp.name, "params": run_params},
        outputs={"lead_count": len(leads), "winning_tier": used_tier},
        decision=(
            f"Experiment '{exp.name}' returned {len(leads)} leads"
            + (f" (relaxed to '{used_tier}')" if summary["relaxed"] else "")
        ),
        summary=f"Experiments → Run: '{exp.name}' → {len(leads)} leads",
    )

    return serialize_experiment(exp)


async def run_batch(db: Session, batch_id: str) -> dict:
    """Run every not-yet-run experiment in the batch sequentially."""
    batch = db.query(ExperimentBatch).filter(ExperimentBatch.id == batch_id).first()
    if not batch:
        return {"_error": "Batch not found"}
    rows = (
        db.query(Experiment)
        .filter(Experiment.batch_id == batch_id)
        .order_by(Experiment.idx.asc())
        .all()
    )
    for e in rows:
        await run_experiment(db, e.id)
    db.refresh(batch)
    return serialize_batch(db, batch)


# ---------------------------------------------------------------------------
# Analysis + relevancy + best pick
# ---------------------------------------------------------------------------

def _compact_leads_for_relevancy(leads: list[dict], cap: int = 25) -> list[dict]:
    """Compact lead view so the model judges relevancy without raw-dump noise."""
    out = []
    for i, lead in enumerate(leads[:cap]):
        out.append({
            "i": i,
            "company": lead.get("company"),
            "industry": lead.get("industry"),
            "title": lead.get("title"),
        })
    return out


async def _score_relevancy(strategy: Strategy, exp: Experiment) -> dict:
    """Score one experiment's leads for relevancy against the product profile."""
    leads = exp.leads_json or []
    if not leads:
        return {
            "relevancy_score": 0,
            "relevant_count": 0,
            "irrelevant_count": 0,
            "off_target_industries": [],
            "summary": "No leads returned for this experiment.",
            "irrelevant_examples": [],
        }

    icp = strategy.icp_json or {}
    dd = strategy.discovery_data or {}
    compact = _compact_leads_for_relevancy(leads)
    prompt = (
        "You are judging whether a list of leads is RELEVANT to a product. A lead is "
        "relevant only if that company plausibly has the problem this product solves "
        "and could buy it. Penalize off-target industries hard (e.g. a construction "
        "company is irrelevant to a healthcare-AI product).\n\n"
        "IMPORTANT: The DISCOVERY data contains the user's explicit, ground-truth requirements, "
        "which MUST take precedence over the AI-inferred ICP INDUSTRIES. If a lead's industry "
        "or company type conflicts with the DISCOVERY data (e.g. 'perfect_customer' or 'company_type'), "
        "it is IRRELEVANT, even if it appears in the broader ICP INDUSTRIES list.\n\n"
        f"PRODUCT: {strategy.product_name}\n"
        f"WHAT IT DOES: {(strategy.description or '')[:500]}\n"
        f"ICP INDUSTRIES: {json.dumps(icp.get('industries'))[:300]}\n"
        f"DISCOVERY DATA: {json.dumps(dd)[:900] if dd else 'none'}\n\n"
        f"LEADS (index, company, industry, title):\n{json.dumps(compact)[:2200]}\n\n"
        "Return STRICT JSON: {\n"
        '  "relevancy_score": 0-100 (share of leads that are a genuine fit, quality-weighted),\n'
        '  "relevant_indices": [int],\n'
        '  "irrelevant_indices": [int],\n'
        '  "off_target_industries": [strings actually present that do not fit],\n'
        '  "irrelevant_examples": [ {"company": str, "industry": str, "reason": str} ],\n'
        '  "summary": "1-2 sentences on overall fit"\n'
        "}"
    )
    ai = await chat_json(prompt, max_tokens=700)
    if not isinstance(ai, dict) or "_error" in ai:
        return {
            "relevancy_score": None,
            "summary": "Relevancy scoring failed.",
            "_error": (ai or {}).get("_error", "unknown"),
        }

    rel_idx = ai.get("relevant_indices") if isinstance(ai.get("relevant_indices"), list) else []
    irr_idx = ai.get("irrelevant_indices") if isinstance(ai.get("irrelevant_indices"), list) else []
    score = ai.get("relevancy_score")
    try:
        score = max(0, min(100, float(score)))
    except (TypeError, ValueError):
        # Derive from counts if the model didn't return a usable score.
        judged = len(rel_idx) + len(irr_idx)
        score = round(100 * len(rel_idx) / judged, 1) if judged else 0

    return {
        "relevancy_score": score,
        "relevant_count": len(rel_idx),
        "irrelevant_count": len(irr_idx),
        "off_target_industries": ai.get("off_target_industries") or [],
        "irrelevant_examples": (ai.get("irrelevant_examples") or [])[:5],
        "summary": ai.get("summary") or "",
    }


async def analyze_batch(db: Session, batch_id: str) -> dict:
    """Score relevancy per experiment, rank them, and pick the best."""
    batch = db.query(ExperimentBatch).filter(ExperimentBatch.id == batch_id).first()
    if not batch:
        return {"_error": "Batch not found"}
    strategy = db.query(Strategy).filter(Strategy.id == batch.strategy_id).first()
    if not strategy:
        return {"_error": "Strategy not found"}

    rows = (
        db.query(Experiment)
        .filter(Experiment.batch_id == batch_id)
        .order_by(Experiment.idx.asc())
        .all()
    )
    run_rows = [e for e in rows if e.status == "done"]
    if not run_rows:
        return {"_error": "Run at least one experiment before analyzing."}

    # ---- 1. Per-experiment relevancy (systematic, one experiment at a time) ----
    # Fairness anchor: every experiment was asked for the same number of leads
    # (the batch's requested size). Comparing a variant that only surfaced 9
    # leads against one that returned the full 25 is not apples-to-apples, so we
    # judge each relevancy score's trustworthiness by how COMPLETE its sample is
    # versus what was requested — floored at the statistical-reliability minimum.
    requested = max(1, batch.leads_per_experiment or 0)
    confidence_denominator = max(MIN_CONFIDENT_SAMPLE, requested)
    max_leads = max((len(e.leads_json or []) for e in run_rows), default=0) or 1
    for e in run_rows:
        rel = await _score_relevancy(strategy, e)
        e.relevancy_json = rel
        # Composite: relevancy dominates, but a tiny or partial sample can't claim
        # full relevancy credit. sample_confidence shrinks the relevancy of a
        # variant in proportion to how far its lead count falls short of the
        # requested sample, so a 9/25 sample can't beat a full 25/25 on a slightly
        # lower relevancy.
        rel_score = rel.get("relevancy_score")
        rel_score = rel_score if isinstance(rel_score, (int, float)) else 0
        lead_count = len(e.leads_json or [])
        sample_confidence = min(1.0, lead_count / confidence_denominator)
        adjusted_relevancy = rel_score * sample_confidence
        volume_factor = lead_count / max_leads
        rel["requested_leads"] = requested
        rel["sample_completeness"] = round(min(1.0, lead_count / requested), 2)
        rel["sample_confidence"] = round(sample_confidence, 2)
        rel["adjusted_relevancy"] = round(adjusted_relevancy, 1)
        rel["low_confidence"] = sample_confidence < 1.0
        e.relevancy_json = rel
        e.score = round(adjusted_relevancy * 0.85 + (volume_factor * 100) * 0.15, 1)
        db.commit()

    # ---- 2. Cross-experiment ranking (compact rows, never raw lead dump) ----
    digest = []
    for e in run_rows:
        rel = e.relevancy_json or {}
        summ = e.result_summary_json or {}
        digest.append({
            "id": e.id,
            "name": e.name,
            "hypothesis": e.hypothesis,
            "params": e.params_json or {},
            "lead_count": summ.get("lead_count", len(e.leads_json or [])),
            "requested_leads": rel.get("requested_leads"),
            "sample_completeness": rel.get("sample_completeness"),
            "relaxed": summ.get("relaxed"),
            "relevancy_score": rel.get("relevancy_score"),
            "sample_confidence": rel.get("sample_confidence"),
            "adjusted_relevancy": rel.get("adjusted_relevancy"),
            "off_target_industries": rel.get("off_target_industries"),
            "composite_score": e.score,
        })

    prompt = (
        "You are analyzing a series of Apollo lead-search experiments to recommend the "
        "single best-performing parameter set for a product. Weigh RELEVANCY (leads that "
        "actually fit the product) far above raw volume — a smaller, on-target experiment "
        "beats a large one full of off-target industries. BUT a relevancy score from a "
        "tiny or PARTIAL sample is unreliable. Every experiment was asked for the same "
        "number of leads ('requested_leads'); 'sample_completeness' is the fraction it "
        "actually returned (1.0 = full sample, 0.36 = only 9 of 25). Treat an experiment "
        "that returned far fewer leads than its peers as a weaker, less comparable sample. "
        "Each experiment also includes 'sample_confidence' (1.0 = trustworthy sample, lower "
        "= partial/too few) and 'adjusted_relevancy' (relevancy already discounted by that "
        "confidence). Prefer the highest 'composite_score'; never crown an experiment with "
        "low sample_completeness or sample_confidence as the winner unless every alternative "
        "is worse on adjusted_relevancy.\n\n"
        f"PRODUCT: {strategy.product_name}\n"
        f"WHAT IT DOES: {(strategy.description or '')[:400]}\n\n"
        f"EXPERIMENTS (already scored):\n{json.dumps(digest, default=str)[:3000]}\n\n"
        "Return STRICT JSON: {\n"
        '  "best_experiment_id": "id of the winner",\n'
        '  "why_best": "2-3 sentences justifying the winner vs the others",\n'
        '  "ranking": [ {"experiment_id": str, "rank": int, "verdict": "short note"} ],\n'
        '  "winning_parameters_insight": "which specific facets (location/industry/size/titles) drove the best results",\n'
        '  "recommendations": ["short next-step strings"]\n'
        "}"
    )
    ai = await chat_json(prompt, max_tokens=1000)

    # Deterministic fallback / guard: the highest composite score is the winner
    # unless the model picked a valid run experiment id. Winner eligibility is
    # restricted to experiments with enough leads to trust the score (tiny
    # samples can't be crowned) — falling back to all runs only if none clear it.
    winner_pool = [e for e in run_rows if len(e.leads_json or []) >= MIN_LEADS_FOR_WINNER] or run_rows
    best_by_score = max(winner_pool, key=lambda e: (e.score or 0))
    best_id = best_by_score.id
    analysis = ai if isinstance(ai, dict) and "_error" not in ai else {}
    model_pick = analysis.get("best_experiment_id")
    if model_pick and any(e.id == model_pick for e in winner_pool):
        best_id = model_pick

    analysis_payload = {
        "best_experiment_id": best_id,
        "why_best": analysis.get("why_best"),
        "ranking": analysis.get("ranking"),
        "winning_parameters_insight": analysis.get("winning_parameters_insight"),
        "recommendations": analysis.get("recommendations") or [],
        "scored_at": None,
        "experiment_digest": digest,
        "_provenance": stamp(
            source="ai_generated",
            logic=(
                "Scored each experiment's leads for relevancy to the product, discounted "
                "that relevancy by sample confidence measured against the requested sample "
                "size (a partial 9-of-25 sample can't claim full credit versus a complete "
                "25-of-25), then ranked experiments by a composite of adjusted relevancy "
                "(85%) and volume (15%). The model justified the winner from a compact "
                "per-experiment digest — raw leads are never dumped wholesale to avoid "
                "hallucination."
            ),
            steps=[
                "Score relevancy per experiment (one at a time)",
                "Discount relevancy by sample_confidence = min(1, leads/max("
                f"{MIN_CONFIDENT_SAMPLE}, requested_leads)) so partial samples rank fairly",
                "Compute composite = 0.85*adjusted_relevancy + 0.15*volume",
                "Rank experiments from a compact digest",
                "Pick best (model choice validated against top composite score)",
            ],
            counts={"experiments_analyzed": len(run_rows)},
            model=MODEL_NAME,
        ),
    }

    batch.analysis_json = analysis_payload
    batch.best_experiment_id = best_id
    batch.status = "analyzed"
    db.commit()
    db.refresh(batch)

    # Distill the result into the centralized learnings memory (best-effort).
    try:
        from app.agents.learnings import capture_from_experiment_batch

        capture_from_experiment_batch(db, batch.id)
    except Exception as exc:  # never block analysis on memory capture
        log.warning("learning capture failed for batch %s: %s", batch.id, exc)

    best_exp = next((e for e in run_rows if e.id == best_id), best_by_score)
    audit_service.log_pipeline_event(
        stage="experiment_analysis",
        service="experiments",
        strategy_id=strategy.id,
        strategy_name=strategy.product_name,
        prompt=prompt,
        inputs={"experiment_digest": digest},
        outputs=analysis_payload,
        decision=f"Best experiment: '{best_exp.name}' (score {best_exp.score})",
        summary=(
            f"Experiments → Analysis: best '{best_exp.name}' "
            f"({best_exp.score}) of {len(run_rows)}"
        ),
    )

    return serialize_batch(db, batch)
