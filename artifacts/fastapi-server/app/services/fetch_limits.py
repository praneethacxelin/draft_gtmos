"""Per-deployment fetch caps for live-data agents.

Stored as a JSON blob in the existing ``app_settings`` table under the
sentinel ``integration_name = "_fetch_limits"`` so we don't need a
schema migration. The blob lives in the ``api_key_encrypted`` column
(a plain ``Text`` column — the value is *not* encrypted here because
fetch limits are not sensitive).

Each limit has a soft default and a hard maximum. ``clamp()`` below
combines a per-run override with the configured cap.
"""
from __future__ import annotations

import json
from sqlalchemy.orm import Session

from app.db import AppSetting

_SENTINEL = "_fetch_limits"

DEFAULTS: dict[str, int] = {
    "leads_per_run": 5,
    "signals_per_account": 3,
    "market_sizing_results": 3,
}

MAXIMUMS: dict[str, int] = {
    "leads_per_run": 10,
    "signals_per_account": 10,
    "market_sizing_results": 10,
}


def _row(db: Session, user_id: str) -> AppSetting | None:
    return (
        db.query(AppSetting)
        .filter(
            AppSetting.user_id == user_id,
            AppSetting.integration_name == _SENTINEL,
        )
        .first()
    )


def get_limits(db: Session, user_id: str) -> dict[str, int]:
    row = _row(db, user_id)
    raw: dict = {}
    if row and row.api_key_encrypted:
        try:
            raw = json.loads(row.api_key_encrypted)
        except Exception:
            raw = {}
    out = dict(DEFAULTS)
    for k in DEFAULTS:
        if k in raw:
            try:
                out[k] = max(1, min(int(raw[k]), MAXIMUMS[k]))
            except (TypeError, ValueError):
                pass
    return out


def get_limits_with_max(db: Session, user_id: str) -> dict:
    cur = get_limits(db, user_id)
    return {
        "limits": cur,
        "maximums": dict(MAXIMUMS),
        "defaults": dict(DEFAULTS),
    }


def set_limits(db: Session, user_id: str, values: dict) -> dict[str, int]:
    cur = get_limits(db, user_id)
    for k, v in (values or {}).items():
        if k in DEFAULTS and v is not None:
            try:
                cur[k] = max(1, min(int(v), MAXIMUMS[k]))
            except (TypeError, ValueError):
                continue
    row = _row(db, user_id)
    if not row:
        row = AppSetting(
            user_id=user_id, integration_name=_SENTINEL, is_enabled=False
        )
        db.add(row)
    row.api_key_encrypted = json.dumps(cur)
    db.commit()
    return cur


def clamp(name: str, requested: int | None, limits: dict[str, int]) -> int:
    """Combine a per-run ``requested`` override with the configured cap.

    The configured deployment limit is the **hard ceiling** — per-run
    overrides may go below it but never above it. The static
    ``MAXIMUMS`` only cap what an admin can save in the first place.
    """
    base = limits.get(name, DEFAULTS.get(name, 5))
    if requested is None:
        return base
    try:
        return max(1, min(int(requested), int(base)))
    except (TypeError, ValueError):
        return base
