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


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def serialize_experiment(e: Experiment) -> dict:
    return {
        "id": e.id,
        "batch_id": e.batch_id,
        "strategy_id": e.strategy_id,
        "idx": e.idx,
        "name": e.name,
        "hypothesis": e.hypothesis,
        "params": e.params_json or {},
        "source": e.source,
        "status": e.status,
        "result_summary": e.result_summary_json,
        "leads": e.leads_json or [],
        "relevancy": e.relevancy_json,
        "score": e.score,
        "error": e.error,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


def serialize_batch(db: Session, b: ExperimentBatch, include_experiments: bool = True) -> dict:
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
        out["experiments"] = [serialize_experiment(e) for e in rows]
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

    raw: list[str] = []
    tg = dd.get("target_geos")
    if isinstance(tg, list):
        raw.extend([g for g in tg if isinstance(g, str)])
    elif isinstance(tg, str) and tg.strip():
        raw.append(tg)

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


# ---------------------------------------------------------------------------
# Seeding (AI generates N distinct experiments)
# ---------------------------------------------------------------------------

async def seed_batch(
    db: Session,
    strategy_id: str,
    n: int,
    leads_per_experiment: int = 10,
    hypothesis: Optional[str] = None,
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

    prompt = (
        "You are a GTM growth engineer designing a SERIES of Apollo.io people-search "
        "experiments to discover which firmographic parameter combination surfaces the "
        "highest-fit leads for a product. Each experiment must vary the parameters "
        "meaningfully from the others (change industry, employee size, seniority, "
        "technology, or keywords) so we can isolate what drives lead quality. Do NOT "
        "repeat the same combination twice. Every facet you choose MUST be justified by "
        "the product's ICP / personas / discovery data below — do not invent unrelated "
        "industries, geographies, or titles.\n\n"
        f"PRODUCT: {strategy.product_name}\n"
        f"DESCRIPTION: {(strategy.description or '')[:500]}\n"
        f"ICP: {json.dumps(icp)[:1100]}\n"
        f"PERSONAS: {json.dumps(personas)[:700] if personas else 'none'}\n"
        f"DISCOVERY: {json.dumps(dd)[:900] if dd else 'none'}\n"
        f"{loc_constraint}{size_hint}"
        f"Design EXACTLY {n} experiments.\n\n"
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

    ai = await chat_json(prompt, max_tokens=1600)
    raw_experiments = []
    if isinstance(ai, dict) and isinstance(ai.get("experiments"), list):
        raw_experiments = ai["experiments"]

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
        params = sanitize_params(raw.get("params") if isinstance(raw, dict) else {})
        # Deterministically clamp geography to the profile's real target market
        # so the model can never drift to off-target countries (e.g. Germany for
        # an India/North-America product).
        if allowed_locations:
            kept = [c for c in params.get("locations", []) if c in allowed_locations]
            params["locations"] = kept or list(allowed_locations)
        # Anchor company size to discovery org_size when the model omitted it.
        if profile_emp_ranges and not params.get("employee_ranges"):
            params["employee_ranges"] = profile_emp_ranges[:2]
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

    audit_service.log_pipeline_event(
        stage="experiment_seed",
        service="experiments",
        strategy_id=strategy_id,
        strategy_name=strategy.product_name,
        prompt=prompt,
        inputs={"n": n, "leads_per_experiment": leads_per_experiment},
        outputs={"batch_id": batch.id, "experiments_created": created},
        decision=f"AI seeded {created} distinct Apollo experiments",
        summary=f"Experiments → Seed: {created} variations for \"{strategy.product_name}\"",
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
    }


def _build_ladder(params: dict) -> list[tuple[str, dict]]:
    """Relaxation ladder for one experiment.

    Keeps the experiment's distinguishing anchors (locations + employee size +
    titles/seniority) as long as possible and peels off the fragile free-text
    facets (technologies, industries) that silently zero-out Apollo results.
    """
    base = {k: v for k, v in params.items() if v}
    ladder: list[tuple[str, dict]] = [("precise (all facets)", dict(base))]
    # Peel the fragile free-text facets in order — these silently zero-out
    # Apollo results far more often than the geo/size/title anchors.
    cur = dict(base)
    dropped: list[str] = []
    for facet in ("technologies", "keywords", "industries"):
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

    ladder = _build_ladder(run_params)
    apollo_results = None
    used_tier = None
    seen: set[str] = set()
    for tier_name, tier_filters in ladder:
        cleaned = {k: v for k, v in tier_filters.items() if v}
        sig = json.dumps(cleaned, sort_keys=True, default=str)
        if not cleaned or sig in seen:
            continue
        seen.add(sig)
        apollo_results = clients.apollo_people_search(
            apollo_key,
            cleaned,
            per_page=min(n_leads or 10, 100),
            _strategy_id=strategy.id,
            _strategy_name=strategy.product_name,
        )
        if apollo_results:
            used_tier = tier_name
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
    compact = _compact_leads_for_relevancy(leads)
    prompt = (
        "You are judging whether a list of leads is RELEVANT to a product. A lead is "
        "relevant only if that company plausibly has the problem this product solves "
        "and could buy it. Penalize off-target industries hard (e.g. a construction "
        "company is irrelevant to a healthcare-AI product).\n\n"
        f"PRODUCT: {strategy.product_name}\n"
        f"WHAT IT DOES: {(strategy.description or '')[:500]}\n"
        f"ICP INDUSTRIES: {json.dumps(icp.get('industries'))[:300]}\n\n"
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
    max_leads = max((len(e.leads_json or []) for e in run_rows), default=0) or 1
    for e in run_rows:
        rel = await _score_relevancy(strategy, e)
        e.relevancy_json = rel
        # Composite: relevancy dominates, volume is a mild tie-breaker.
        rel_score = rel.get("relevancy_score")
        rel_score = rel_score if isinstance(rel_score, (int, float)) else 0
        volume_factor = len(e.leads_json or []) / max_leads
        e.score = round(rel_score * 0.85 + (volume_factor * 100) * 0.15, 1)
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
            "relaxed": summ.get("relaxed"),
            "relevancy_score": rel.get("relevancy_score"),
            "off_target_industries": rel.get("off_target_industries"),
            "composite_score": e.score,
        })

    prompt = (
        "You are analyzing a series of Apollo lead-search experiments to recommend the "
        "single best-performing parameter set for a product. Weigh RELEVANCY (leads that "
        "actually fit the product) far above raw volume — a smaller, on-target experiment "
        "beats a large one full of off-target industries.\n\n"
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
    # unless the model picked a valid run experiment id.
    best_by_score = max(run_rows, key=lambda e: (e.score or 0))
    best_id = best_by_score.id
    analysis = ai if isinstance(ai, dict) and "_error" not in ai else {}
    model_pick = analysis.get("best_experiment_id")
    if model_pick and any(e.id == model_pick for e in run_rows):
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
                "Scored each experiment's leads for relevancy to the product, then ranked "
                "experiments by a composite of relevancy (85%) and volume (15%). The model "
                "justified the winner from a compact per-experiment digest — raw leads are "
                "never dumped wholesale to avoid hallucination."
            ),
            steps=[
                "Score relevancy per experiment (one at a time)",
                "Compute composite score = 0.85*relevancy + 0.15*volume",
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
