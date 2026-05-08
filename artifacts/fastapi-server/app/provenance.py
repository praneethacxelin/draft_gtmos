"""Provenance stamp helper.

Every agent that writes to the database calls ``stamp(...)`` to record
*how* a payload was produced (which model, which steps, which external
calls) so the UI can render a "How this was generated" panel and a
source badge alongside every artifact.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional


def stamp(
    source: str,
    logic: str,
    steps: Optional[list[str]] = None,
    counts: Optional[dict] = None,
    model: Optional[str] = None,
    extra: Optional[dict] = None,
) -> dict:
    """Build a provenance dict.

    ``source`` is one of: ``ai_generated``, ``serpapi``, ``apollo``,
    ``instantly``, ``clay``, ``computed`` (deterministic post-processing
    in our own code), ``legacy`` (pre-existing data with no provenance
    captured at write time).
    """
    p: dict = {
        "source": source,
        "logic": logic,
        "steps": list(steps or []),
        "counts": dict(counts or {}),
        "generated_at": datetime.utcnow().isoformat(),
    }
    if model:
        p["model"] = model
    if extra:
        p["extra"] = extra
    return p
