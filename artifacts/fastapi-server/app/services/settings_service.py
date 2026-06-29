"""In-app integration settings (per-user).

API keys are stored encrypted in the DB, scoped to the owning user. Each
caller passes an explicit ``user_id`` so one user's keys never leak into
another user's pipeline.
"""
from datetime import datetime
from typing import Optional
import os
from sqlalchemy.orm import Session
from app.db import AppSetting
from app.crypto import encrypt, decrypt

INTEGRATIONS = ["serpapi", "apollo", "hunter", "clay", "instantly"]

INTEGRATION_META = {
    "serpapi": {
        "display_name": "SerpAPI",
        "description": "Live Google search for buying signals, market sizing, and competitor news.",
        "key_label": "API Key",
        "supported": True,
    },
    "apollo": {
        "display_name": "Apollo.io",
        "description": "Real lead discovery and contact lookup with verified emails.",
        "key_label": "API Key",
        "supported": True,
    },
    "hunter": {
        "display_name": "Hunter.io",
        "description": "On-demand email verification — used to validate bounced addresses after analytics so you only spend credits on emails that actually need re-checking.",
        "key_label": "API Key",
        "supported": True,
    },
    "clay": {
        "display_name": "Clay",
        "description": (
            "Not supported. Clay is a no-code orchestration canvas without a stable "
            "public enrichment API we can drive programmatically, so it cannot plug "
            "into the automated GTM pipeline. We instead provide the equivalent "
            "intelligence, scoring logic, and end-to-end flow natively via Apollo + "
            "SerpAPI + Hunter."
        ),
        "key_label": "API Key",
        "supported": False,
    },
    "instantly": {
        "display_name": "Instantly.ai",
        "description": "Email outreach automation, deliverability monitoring, and response tracking.",
        "key_label": "API Key",
        "supported": True,
    },
}


def _safe_last_four(encrypted: str) -> str | None:
    """Decrypt ``encrypted`` and return the last 4 chars, or ``None`` on failure."""
    if not encrypted:
        return None
    try:
        plain = decrypt(encrypted)
        return plain[-4:] if len(plain) >= 4 else plain
    except Exception:
        return None


def list_integrations(db: Session, user_id: str) -> list[dict]:
    rows = {
        r.integration_name: r
        for r in db.query(AppSetting).filter(AppSetting.user_id == user_id).all()
    }
    out = []
    for name in INTEGRATIONS:
        meta = INTEGRATION_META[name]
        row = rows.get(name)
        out.append({
            "name": name,
            "display_name": meta["display_name"],
            "description": meta["description"],
            "key_label": meta["key_label"],
            "supported": meta.get("supported", True),
            "is_connected": bool(row and row.api_key_encrypted),
            "is_enabled": bool(row and row.is_enabled),
            "key_last_four": _safe_last_four(row.api_key_encrypted) if row else None,
            "last_tested_at": row.last_tested_at.isoformat() if row and row.last_tested_at else None,
            "test_status": row.test_status if row else None,
            "test_message": row.test_message if row else None,
        })
    return out


def upsert_integration(
    db: Session,
    user_id: str,
    name: str,
    api_key: Optional[str],
    is_enabled: bool,
) -> dict:
    if name not in INTEGRATIONS:
        raise ValueError(f"Unknown integration: {name}")
    row = (
        db.query(AppSetting)
        .filter(AppSetting.user_id == user_id, AppSetting.integration_name == name)
        .first()
    )
    if not row:
        row = AppSetting(user_id=user_id, integration_name=name)
        db.add(row)
    if api_key is not None and api_key.strip():
        row.api_key_encrypted = encrypt(api_key.strip())
    elif api_key == "":
        row.api_key_encrypted = None
        row.is_enabled = False
    row.is_enabled = is_enabled and bool(row.api_key_encrypted)
    db.commit()
    db.refresh(row)
    return {
        "name": name,
        "is_connected": bool(row.api_key_encrypted),
        "is_enabled": row.is_enabled,
    }


def get_raw(db: Session, user_id: str, name: str) -> Optional[AppSetting]:
    return (
        db.query(AppSetting)
        .filter(AppSetting.user_id == user_id, AppSetting.integration_name == name)
        .first()
    )


def _env_key(name: str) -> Optional[str]:
    """Fallback API key from the environment (e.g. INSTANTLY_API_KEY).

    Used for single-tenant / local deployments so a key set in ``.env`` works
    out of the box without re-entering it in Settings. A per-user key stored in
    the DB always takes precedence over this.
    """
    val = os.getenv(f"{name.upper()}_API_KEY")
    return val.strip() if val and val.strip() else None


def get_key(db: Session, user_id: Optional[str], name: str) -> Optional[str]:
    """Return the plaintext API key for ``user_id``'s ``name`` integration.

    Resolution order: the per-user key stored encrypted in the DB takes
    precedence; if none is set we fall back to the ``<NAME>_API_KEY`` env var so
    a key configured in ``.env`` works without re-entering it in Settings.
    """
    if user_id:
        row = (
            db.query(AppSetting)
            .filter(AppSetting.user_id == user_id, AppSetting.integration_name == name)
            .first()
        )
        if row and row.is_enabled and row.api_key_encrypted:
            try:
                return decrypt(row.api_key_encrypted)
            except Exception:
                pass
    return _env_key(name)


def record_test_result(db: Session, user_id: str, name: str, ok: bool, message: str) -> None:
    row = (
        db.query(AppSetting)
        .filter(AppSetting.user_id == user_id, AppSetting.integration_name == name)
        .first()
    )
    if not row:
        return
    row.last_tested_at = datetime.utcnow()
    row.test_status = "ok" if ok else "failed"
    row.test_message = message
    db.commit()
