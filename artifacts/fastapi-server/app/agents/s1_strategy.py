"""S1 — Strategy & Discovery agent.

Sequential pipeline that, given a product brief, produces:
  - ICP firmographics
  - Persona matrix (Champion / Economic Buyer / Blocker)
  - Problem map
  - Industry segmentation (NAICS-coded)
  - Buying-center stakeholder graph
  - Use case library

Each stage emits an SSE event for the UI.
"""
import json
from typing import AsyncIterator
from sqlalchemy.orm import Session
from app.db import Strategy, IcpEmbedding
from app.llm import chat_json, deterministic_embedding
from app.services import audit_service


def _persist(field, payload, strategy, db):
    """Only persist payload if it isn't an LLM error envelope."""
    if isinstance(payload, dict) and "_error" in payload:
        return False
    setattr(strategy, field, payload)
    db.commit()
    return True


async def run_s1(db: Session, strategy_id: str) -> AsyncIterator[dict]:
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        yield {"event": "error", "data": {"message": "Strategy not found"}}
        return

    if strategy.status == "generating":
        yield {"event": "error", "data": {"message": "Generation already in progress for this strategy"}}
        return

    strategy.status = "generating"
    db.commit()

    # Build a rich brief from discovery_data + legacy fields
    dd = strategy.discovery_data or {}
    
    def _dd(key, fallback="unspecified"):
        """Get a discovery data value, handling arrays and strings."""
        val = dd.get(key)
        if val is None:
            return fallback
        if isinstance(val, list):
            clean = [v for v in val if v and v != "__other__"]
            return ", ".join(clean) if clean else fallback
        if isinstance(val, str) and val.strip() and val != "__other__":
            return val.strip()
        return fallback
    
    # Product description: prefer discovery, fallback to legacy field
    product_desc = _dd("product_description", strategy.description or "unspecified")
    target_market = _dd("target_geos", strategy.target_market or "unspecified")
    pain_points = _dd("pain_points", strategy.pain_points_raw or "unspecified")
    
    brief_parts = [
        f"Product: {strategy.product_name}",
        f"Description: {product_desc}",
        f"Company Type: {_dd('company_type')}",
        f"Target Market / Geographies: {target_market}",
        f"Target Org Size: {_dd('org_size')}",
        f"Pain Points: {pain_points}",
        f"Perfect Customer: {_dd('perfect_customer')}",
        f"Economic Buyer: {_dd('economic_buyer')}",
        f"Champion: {_dd('champion')}",
        f"Deal Blockers: {_dd('deal_blockers')}",
        f"Buying Signals: {_dd('buying_signals')}",
        f"Purchase Triggers: {_dd('triggers')}",
        f"Alternative Tools: {_dd('alternatives')}",
        f"Unique Value Proposition: {_dd('uvp')}",
        f"Sales Cycle: {_dd('sales_cycle')}",
    ]
    brief = "\n".join(brief_parts)

    # Also update the legacy fields if they're empty but discovery has data
    if not strategy.description and dd.get("product_description"):
        strategy.description = _dd("product_description", "")
    if not strategy.target_market and dd.get("target_geos"):
        strategy.target_market = _dd("target_geos", "")
    if not strategy.pain_points_raw and dd.get("pain_points"):
        strategy.pain_points_raw = _dd("pain_points", "")
    db.commit()

    # Log the user's raw input that kicks off the entire pipeline
    audit_service.log_pipeline_event(
        stage="user_input",
        service="s1_strategy",
        strategy_id=strategy_id,
        strategy_name=strategy.product_name,
        inputs={
            "product_name": strategy.product_name,
            "description": product_desc,
            "target_market": target_market,
            "pain_points_raw": pain_points,
            "discovery_data": dd,
        },
        outputs={"brief_text": brief},
        summary=f"S1 → User Input: \"{strategy.product_name}\" brief assembled from discovery data",
    )

    # 1. ICP Modeling
    yield {"event": "stage_start", "data": {"stage": "icp"}}
    icp_prompt = (
        f"Build an Ideal Customer Profile for the following product. {brief}\n\n"
        "Return JSON with keys: industries (array of strings), employee_size_range "
        "(e.g. '50-500'), revenue_range (e.g. '$10M-$50M'), geographies (array), "
        "tech_stack_signals (array), segments (array of {name, fit_score 0-100, "
        "rationale}), scoring_rules (array of {signal, weight 0-1})."
    )
    icp = await chat_json(icp_prompt)
    _persist("icp_json", icp, strategy, db)
    audit_service.log_pipeline_event(
        stage="icp",
        service="s1_strategy",
        strategy_id=strategy_id,
        strategy_name=strategy.product_name,
        inputs={"brief": brief},
        outputs=icp,
        prompt=icp_prompt,
        summary=f"S1 → ICP Modeling: Generated firmographics from user brief",
    )
    yield {"event": "stage_complete", "data": {"stage": "icp", "result": icp}}

    # 2. Persona Mapping
    yield {"event": "stage_start", "data": {"stage": "personas"}}
    personas_prompt = (
        f"Given this ICP: {json.dumps(icp)[:1500]}, build a persona matrix for "
        f"product '{strategy.product_name}'. {brief}\n"
        "The persona titles MUST align with the buyer personas and target market described above. "
        "Return JSON with keys: champion, "
        "economic_buyer, blocker. Each persona has: title, goals (array), "
        "frustrations (array), success_metrics (array), communication_style, "
        "objections (array). Also include 'influence_edges': array of "
        "{from, to, label} describing influence relationships."
    )
    personas = await chat_json(personas_prompt)
    _persist("personas_json", personas, strategy, db)
    audit_service.log_pipeline_event(
        stage="personas",
        service="s1_strategy",
        strategy_id=strategy_id,
        strategy_name=strategy.product_name,
        inputs={"icp_json": icp},
        outputs=personas,
        prompt=personas_prompt,
        decision="ICP output from previous stage is injected as the input context for persona generation",
        summary=f"S1 → Persona Mapping: Generated Champion/Economic Buyer/Blocker from ICP",
    )
    yield {"event": "stage_complete", "data": {"stage": "personas", "result": personas}}

    # 3. Problem Identification
    yield {"event": "stage_start", "data": {"stage": "problems"}}
    problems_prompt = (
        f"Product: {strategy.product_name}. Personas: {json.dumps(personas)[:1500]}. "
        "Build a Problem-Solution Map. Return JSON with key 'problems' = array of "
        "{persona, pain, trigger, product_angle, urgency 'low'|'medium'|'high'}."
    )
    problems = await chat_json(problems_prompt)
    _persist("problems_json", problems, strategy, db)
    audit_service.log_pipeline_event(
        stage="problems",
        service="s1_strategy",
        strategy_id=strategy_id,
        strategy_name=strategy.product_name,
        inputs={"personas_json": personas},
        outputs=problems,
        prompt=problems_prompt,
        decision="Personas from previous stage feed into problem identification",
        summary=f"S1 → Problem Map: Mapped pain points per persona",
    )
    yield {"event": "stage_complete", "data": {"stage": "problems", "result": problems}}

    # 4. Industry Segmentation (NAICS)
    yield {"event": "stage_start", "data": {"stage": "naics"}}
    naics_prompt = (
        f"Product: '{strategy.product_name}'. {brief}\n"
        f"Target Market: {strategy.target_market or 'businesses'}. "
        "Produce NAICS industry segmentation. Return JSON with key 'segments' = array of "
        "{naics_code, name, sub_vertical, opportunity_score 0-100, est_company_count, rationale}. "
        "Provide 5-7 segments."
    )
    naics = await chat_json(naics_prompt)
    _persist("naics_json", naics, strategy, db)
    audit_service.log_pipeline_event(
        stage="naics",
        service="s1_strategy",
        strategy_id=strategy_id,
        strategy_name=strategy.product_name,
        inputs={"product_name": strategy.product_name, "target_market": strategy.target_market},
        outputs=naics,
        prompt=naics_prompt,
        summary=f"S1 → NAICS Segmentation: Industry codes generated",
    )
    yield {"event": "stage_complete", "data": {"stage": "naics", "result": naics}}

    # 5. Buying Center Mapping
    yield {"event": "stage_start", "data": {"stage": "stakeholders"}}
    stakeholders_prompt = (
        f"Product: {strategy.product_name}. {brief}\n"
        f"Personas: {json.dumps(personas)[:1500]}. Build a stakeholder graph for the "
        "buying center. The stakeholder titles MUST match the personas above. "
        "Return JSON with keys 'nodes' = array of {id, label, role, "
        "tier 'champion'|'blocker'|'economic_buyer'|'influencer', influence 0-100} "
        "and 'edges' = array of {from, to, label}. Include 5-7 stakeholders covering "
        "the typical enterprise buying committee."
    )
    stakeholders = await chat_json(stakeholders_prompt)
    _persist("stakeholder_map_json", stakeholders, strategy, db)
    audit_service.log_pipeline_event(
        stage="stakeholders",
        service="s1_strategy",
        strategy_id=strategy_id,
        strategy_name=strategy.product_name,
        inputs={"personas_json": personas},
        outputs=stakeholders,
        prompt=stakeholders_prompt,
        summary=f"S1 → Stakeholder Graph: Buying center mapped",
    )
    yield {"event": "stage_complete", "data": {"stage": "stakeholders", "result": stakeholders}}

    # 6. Use Case Library
    yield {"event": "stage_start", "data": {"stage": "use_cases"}}
    use_cases_prompt = (
        f"Product: {strategy.product_name}. {brief}\n"
        f"Segments: {json.dumps(naics)[:800]}. "
        f"Personas: {json.dumps(personas)[:800]}. Build a Use Case Library. "
        "Return JSON with key 'use_cases' = array of {title, vertical, persona, "
        "scenario, value_prop, proof_point_placeholder}. 6-8 use cases total."
    )
    use_cases = await chat_json(use_cases_prompt)
    _persist("use_cases_json", use_cases, strategy, db)
    audit_service.log_pipeline_event(
        stage="use_cases",
        service="s1_strategy",
        strategy_id=strategy_id,
        strategy_name=strategy.product_name,
        inputs={"naics_json": naics, "personas_json_keys": list(personas.keys()) if isinstance(personas, dict) else None},
        outputs=use_cases,
        prompt=use_cases_prompt,
        decision="NAICS segments + Personas combined as input for use case generation",
        summary=f"S1 → Use Cases: Library of {len(use_cases.get('use_cases', [])) if isinstance(use_cases, dict) else '?'} use cases built",
    )
    yield {"event": "stage_complete", "data": {"stage": "use_cases", "result": use_cases}}

    # Embed the ICP for pgvector pattern recognition
    summary = json.dumps({"icp": icp, "naics": naics})[:4000]
    embedding = deterministic_embedding(summary)
    db.query(IcpEmbedding).filter(IcpEmbedding.strategy_id == strategy_id).delete()
    db.add(IcpEmbedding(strategy_id=strategy_id, embedding=embedding, summary=summary[:1000]))
    strategy.status = "ready"
    db.commit()

    audit_service.log_pipeline_event(
        stage="complete",
        service="s1_strategy",
        strategy_id=strategy_id,
        strategy_name=strategy.product_name,
        inputs={"stages_completed": ["icp", "personas", "problems", "naics", "stakeholders", "use_cases"]},
        outputs={"status": "ready", "embedding_dims": len(embedding)},
        summary=f"S1 → Complete: All 6 stages finished, ICP embedded for pattern recognition",
    )

    yield {"event": "complete", "data": {"strategy_id": strategy_id}}
