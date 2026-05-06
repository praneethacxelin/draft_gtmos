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

    brief = (
        f"Product: {strategy.product_name}\n"
        f"Description: {strategy.description}\n"
        f"Target Market: {strategy.target_market or 'unspecified'}\n"
        f"Pain Points: {strategy.pain_points_raw or 'unspecified'}"
    )

    # 1. ICP Modeling
    yield {"event": "stage_start", "data": {"stage": "icp"}}
    icp = chat_json(
        f"Build an Ideal Customer Profile for the following product. {brief}\n\n"
        "Return JSON with keys: industries (array of strings), employee_size_range "
        "(e.g. '50-500'), revenue_range (e.g. '$10M-$50M'), geographies (array), "
        "tech_stack_signals (array), segments (array of {name, fit_score 0-100, "
        "rationale}), scoring_rules (array of {signal, weight 0-1})."
    )
    _persist("icp_json", icp, strategy, db)
    yield {"event": "stage_complete", "data": {"stage": "icp", "result": icp}}

    # 2. Persona Mapping
    yield {"event": "stage_start", "data": {"stage": "personas"}}
    personas = chat_json(
        f"Given this ICP: {json.dumps(icp)[:1500]}, build a persona matrix for "
        f"product '{strategy.product_name}'. Return JSON with keys: champion, "
        "economic_buyer, blocker. Each persona has: title, goals (array), "
        "frustrations (array), success_metrics (array), communication_style, "
        "objections (array). Also include 'influence_edges': array of "
        "{from, to, label} describing influence relationships."
    )
    _persist("personas_json", personas, strategy, db)
    yield {"event": "stage_complete", "data": {"stage": "personas", "result": personas}}

    # 3. Problem Identification
    yield {"event": "stage_start", "data": {"stage": "problems"}}
    problems = chat_json(
        f"Product: {strategy.product_name}. Personas: {json.dumps(personas)[:1500]}. "
        "Build a Problem-Solution Map. Return JSON with key 'problems' = array of "
        "{persona, pain, trigger, product_angle, urgency 'low'|'medium'|'high'}."
    )
    _persist("problems_json", problems, strategy, db)
    yield {"event": "stage_complete", "data": {"stage": "problems", "result": problems}}

    # 4. Industry Segmentation (NAICS)
    yield {"event": "stage_start", "data": {"stage": "naics"}}
    naics = chat_json(
        f"For product '{strategy.product_name}' targeting {strategy.target_market or 'businesses'}, "
        "produce NAICS industry segmentation. Return JSON with key 'segments' = array of "
        "{naics_code, name, sub_vertical, opportunity_score 0-100, est_company_count, rationale}. "
        "Provide 5-7 segments."
    )
    _persist("naics_json", naics, strategy, db)
    yield {"event": "stage_complete", "data": {"stage": "naics", "result": naics}}

    # 5. Buying Center Mapping
    yield {"event": "stage_start", "data": {"stage": "stakeholders"}}
    stakeholders = chat_json(
        f"Personas: {json.dumps(personas)[:1500]}. Build a stakeholder graph for the "
        "buying center. Return JSON with keys 'nodes' = array of {id, label, role, "
        "tier 'champion'|'blocker'|'economic_buyer'|'influencer', influence 0-100} "
        "and 'edges' = array of {from, to, label}. Include 5-7 stakeholders covering "
        "the typical enterprise buying committee."
    )
    _persist("stakeholder_map_json", stakeholders, strategy, db)
    yield {"event": "stage_complete", "data": {"stage": "stakeholders", "result": stakeholders}}

    # 6. Use Case Library
    yield {"event": "stage_start", "data": {"stage": "use_cases"}}
    use_cases = chat_json(
        f"Product: {strategy.product_name}. Segments: {json.dumps(naics)[:800]}. "
        "Personas: {json.dumps(personas)[:800]}. Build a Use Case Library. "
        "Return JSON with key 'use_cases' = array of {title, vertical, persona, "
        "scenario, value_prop, proof_point_placeholder}. 6-8 use cases total."
    )
    _persist("use_cases_json", use_cases, strategy, db)
    yield {"event": "stage_complete", "data": {"stage": "use_cases", "result": use_cases}}

    # Embed the ICP for pgvector pattern recognition
    summary = json.dumps({"icp": icp, "naics": naics})[:4000]
    embedding = deterministic_embedding(summary)
    db.query(IcpEmbedding).filter(IcpEmbedding.strategy_id == strategy_id).delete()
    db.add(IcpEmbedding(strategy_id=strategy_id, embedding=embedding, summary=summary[:1000]))
    strategy.status = "ready"
    db.commit()

    yield {"event": "complete", "data": {"strategy_id": strategy_id}}
