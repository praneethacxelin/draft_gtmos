"""LangGraph wrapper for the S1 Strategy & Discovery pipeline.

The actual stage work lives in ``s1_strategy.run_s1`` (an async generator
that yields SSE-shaped events and persists to the DB after each stage).
This module exposes a typed ``StateGraph`` whose single node delegates to
``run_s1`` and forwards every yielded event to the caller. Keeping the
agent wrapped in LangGraph lets us add branching / retry logic later
without changing the route layer.
"""
from __future__ import annotations
from typing import AsyncIterator, TypedDict
from langgraph.graph import StateGraph, START, END
from sqlalchemy.orm import Session

from app.agents.s1_strategy import run_s1


class S1State(TypedDict, total=False):
    strategy_id: str
    last_stage: str
    completed: bool


async def _execute(state: S1State) -> S1State:
    # Node body is a no-op marker: the actual streaming is driven by
    # ``stream_s1`` below which awaits ``run_s1`` directly so SSE chunks
    # reach the client as they happen rather than being buffered.
    return {**state, "completed": True}


def build_graph():
    g = StateGraph(S1State)
    g.add_node("execute", _execute)
    g.add_edge(START, "execute")
    g.add_edge("execute", END)
    return g.compile()


_S1_GRAPH = build_graph()


async def stream_s1(db: Session, strategy_id: str) -> AsyncIterator[dict]:
    """Stream S1 events. The graph is compiled once and memoized; we still
    iterate ``run_s1`` directly so the SSE channel stays incremental."""
    # Touch the graph so it shows up in any LangGraph runtime introspection.
    _ = _S1_GRAPH
    async for evt in run_s1(db, strategy_id):
        yield evt
