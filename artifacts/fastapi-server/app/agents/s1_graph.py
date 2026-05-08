"""Multi-node LangGraph StateGraph for the S1 Strategy & Discovery pipeline.

Each S1 stage (icp / personas / problems / naics / stakeholders /
use_cases) is its own node so future revisions can add per-stage retry,
conditional routing, or human-in-the-loop checkpoints without touching
the route layer. The graph publishes events to an ``asyncio.Queue`` so
SSE chunks reach the client incrementally; the route's ``stream_s1``
generator drains that queue while the graph is running.
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, Awaitable, Callable, TypedDict

from langgraph.graph import StateGraph, START, END
from sqlalchemy.orm import Session

from app.db import Strategy, IcpEmbedding
from app.llm import chat_json, deterministic_embedding, MODEL_NAME
from app.provenance import stamp
from app.services.rate_limit import RateLimitExceeded


_STAGE_LOGIC: dict[str, tuple[str, list[str]]] = {
    "icp": (
        "Asked the model to draft an Ideal Customer Profile from the product brief.",
        ["Read product brief", "Prompt model with ICP schema", "Persist firmographics + segments"],
    ),
    "personas": (
        "Generated a champion / economic-buyer / blocker persona matrix grounded in the ICP.",
        ["Read latest ICP", "Prompt model with persona schema", "Persist persona matrix + influence edges"],
    ),
    "problems": (
        "Mapped persona pains, triggers, and product angles into a problem-solution table.",
        ["Read personas", "Prompt model with problem-map schema", "Persist problem rows"],
    ),
    "naics": (
        "Segmented the ICP into NAICS industry codes with opportunity scores.",
        ["Read ICP", "Prompt model with NAICS schema", "Persist 5–7 segments"],
    ),
    "stakeholders": (
        "Built a buying-committee graph with influence edges between stakeholders.",
        ["Read personas", "Prompt model with graph schema", "Persist nodes + edges"],
    ),
    "use_cases": (
        "Generated a use-case library cross-referencing personas and segments.",
        ["Read NAICS + personas", "Prompt model with use-case schema", "Persist 6–8 use cases"],
    ),
}


class S1State(TypedDict, total=False):
    strategy_id: str
    brief: str
    icp: dict
    personas: dict
    problems: dict
    naics: dict
    stakeholders: dict
    use_cases: dict
    db: Session
    queue: asyncio.Queue
    last_stage: str


def _persist(db: Session, strategy_id: str, field: str, payload: dict) -> bool:
    if isinstance(payload, dict) and "_error" in payload:
        return False
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return False
    setattr(strategy, field, payload)
    db.commit()
    return True


async def _emit(state: S1State, event: str, data: dict) -> None:
    queue: asyncio.Queue = state["queue"]
    await queue.put({"event": event, "data": data})


def _make_stage(
    stage: str,
    field: str,
    prompt_fn: Callable[[S1State], str],
) -> Callable[[S1State], Awaitable[S1State]]:
    async def node(state: S1State) -> S1State:
        await _emit(state, "stage_start", {"stage": stage})
        result = await chat_json(prompt_fn(state), max_tokens=1500)
        if isinstance(result, dict) and "_error" not in result:
            logic, steps = _STAGE_LOGIC.get(
                stage,
                (f"Generated {stage} payload via LLM.", ["Prompt model", "Persist payload"]),
            )
            result["_provenance"] = stamp(
                source="ai_generated",
                logic=logic,
                steps=steps,
                model=MODEL_NAME,
            )
        _persist(state["db"], state["strategy_id"], field, result)
        await _emit(state, "stage_complete", {"stage": stage, "result": result})
        return {**state, stage: result, "last_stage": stage}
    return node


# ---------- prompt builders (one per stage) ----------

def _icp_prompt(s: S1State) -> str:
    return (
        f"Build an Ideal Customer Profile. {s['brief']}\n\n"
        "Return JSON with: industries, employee_size_range, revenue_range, "
        "geographies, tech_stack_signals, segments (array of "
        "{name, fit_score 0-100, rationale}), scoring_rules."
    )


def _personas_prompt(s: S1State) -> str:
    return (
        f"Given ICP: {json.dumps(s.get('icp', {}))[:1500]}, build a persona "
        "matrix. Return JSON with keys: champion, economic_buyer, blocker. "
        "Each: title, goals, frustrations, success_metrics, "
        "communication_style, objections. Plus 'influence_edges': array of "
        "{from, to, label}."
    )


def _problems_prompt(s: S1State) -> str:
    return (
        f"Personas: {json.dumps(s.get('personas', {}))[:1500]}. Build a "
        "Problem-Solution Map. Return JSON with key 'problems' = array of "
        "{persona, pain, trigger, product_angle, urgency low|medium|high}."
    )


def _naics_prompt(s: S1State) -> str:
    return (
        f"For ICP {json.dumps(s.get('icp', {}))[:800]} produce NAICS "
        "industry segmentation. Return JSON 'segments' = array of "
        "{naics_code, name, sub_vertical, opportunity_score 0-100, "
        "est_company_count, rationale}. 5-7 segments."
    )


def _stakeholders_prompt(s: S1State) -> str:
    return (
        f"Personas: {json.dumps(s.get('personas', {}))[:1500]}. Build a "
        "stakeholder graph for the buying center. Return JSON with 'nodes' "
        "= array of {id, label, role, tier "
        "champion|blocker|economic_buyer|influencer, influence 0-100} and "
        "'edges' = array of {from, to, label}. 5-7 stakeholders."
    )


def _use_cases_prompt(s: S1State) -> str:
    return (
        f"Segments: {json.dumps(s.get('naics', {}))[:800]}. Personas: "
        f"{json.dumps(s.get('personas', {}))[:800]}. Build a Use Case "
        "Library. Return JSON 'use_cases' = array of "
        "{title, vertical, persona, scenario, value_prop, "
        "proof_point_placeholder}. 6-8 use cases."
    )


async def _embed_node(state: S1State) -> S1State:
    db: Session = state["db"]
    strategy_id = state["strategy_id"]
    # Don't mark ready if any stage produced an error envelope — surface failure.
    stage_keys = ("icp", "personas", "problems", "naics", "stakeholders", "use_cases")
    failed = [k for k in stage_keys if isinstance(state.get(k), dict) and "_error" in state[k]]
    summary = json.dumps({"icp": state.get("icp"), "naics": state.get("naics")})[:4000]
    embedding = deterministic_embedding(summary)
    db.query(IcpEmbedding).filter(IcpEmbedding.strategy_id == strategy_id).delete()
    db.add(IcpEmbedding(strategy_id=strategy_id, embedding=embedding, summary=summary[:1000]))
    strat = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if strat:
        strat.status = "error" if failed else "ready"
    db.commit()
    if failed:
        await _emit(state, "error", {"failed_stages": failed})
    return state


def build_graph():
    g = StateGraph(S1State)
    g.add_node("n_icp", _make_stage("icp", "icp_json", _icp_prompt))
    g.add_node("n_personas", _make_stage("personas", "personas_json", _personas_prompt))
    g.add_node("n_problems", _make_stage("problems", "problems_json", _problems_prompt))
    g.add_node("n_naics", _make_stage("naics", "naics_json", _naics_prompt))
    g.add_node("n_stakeholders", _make_stage("stakeholders", "stakeholder_map_json", _stakeholders_prompt))
    g.add_node("n_use_cases", _make_stage("use_cases", "use_cases_json", _use_cases_prompt))
    g.add_node("n_embed", _embed_node)

    g.add_edge(START, "n_icp")
    g.add_edge("n_icp", "n_personas")
    g.add_edge("n_personas", "n_problems")
    g.add_edge("n_problems", "n_naics")
    g.add_edge("n_naics", "n_stakeholders")
    g.add_edge("n_stakeholders", "n_use_cases")
    g.add_edge("n_use_cases", "n_embed")
    g.add_edge("n_embed", END)
    return g.compile()


_S1_GRAPH = build_graph()


async def stream_s1(db: Session, strategy_id: str) -> AsyncIterator[dict]:
    """Drive the multi-node LangGraph and forward events to the SSE stream."""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        yield {"event": "error", "data": {"message": "Strategy not found"}}
        return
    if strategy.status == "generating":
        yield {"event": "error", "data": {"message": "Generation already in progress"}}
        return

    strategy.status = "generating"
    db.commit()

    queue: asyncio.Queue = asyncio.Queue()
    initial: S1State = {
        "strategy_id": strategy_id,
        "brief": (
            f"Product: {strategy.product_name}\n"
            f"Description: {strategy.description}\n"
            f"Target Market: {strategy.target_market or 'unspecified'}\n"
            f"Pain Points: {strategy.pain_points_raw or 'unspecified'}"
        ),
        "db": db,
        "queue": queue,
    }

    async def runner() -> None:
        try:
            await _S1_GRAPH.ainvoke(initial)
            await queue.put({"event": "complete", "data": {"strategy_id": strategy_id}})
        except RateLimitExceeded as rle:
            await queue.put({
                "event": "error",
                "data": {
                    "status": 429,
                    "integration": rle.name,
                    "retry_after_seconds": int(rle.retry_after),
                    "message": (
                        f"Free-tier rate limit reached for {rle.name}. "
                        f"Retry in ~{int(rle.retry_after)}s."
                    ),
                },
            })
        except Exception as exc:  # pragma: no cover
            await queue.put({"event": "error", "data": {"message": str(exc)}})
        finally:
            await queue.put(None)  # sentinel

    task = asyncio.create_task(runner())
    while True:
        item = await queue.get()
        if item is None:
            break
        yield item
    await task
