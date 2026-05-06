"""In-app integration settings.

API keys are stored encrypted in the DB. `get_key(name)` returns the
plaintext key (or None) so other services can decide to call the real API
or fall back to AI-mocked data.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.db import AppSetting
from app.crypto import encrypt, decrypt

INTEGRATIONS = ["serpapi", "apollo", "clay", "instantly"]

INTEGRATION_META = {
    "serpapi": {
        "display_name": "SerpAPI",
        "description": "Live Google search for buying signals, market sizing, and competitor news.",
        "key_label": "API Key",
    },
    "apollo": {
        "display_name": "Apollo.io",
        "description": "Real lead discovery and contact lookup with verified emails.",
        "key_label": "API Key",
    },
    "clay": {
        "display_name": "Clay",
        "description": "Enrichment waterfall on top of Apollo for tech stack, funding, and verified data.",
        "key_label": "API Key",
    },
    "instantly": {
        "display_name": "Instantly.ai",
        "description": "Email outreach automation, deliverability monitoring, and response tracking.",
        "key_label": "API Key",
    },
}


def list_integrations(db: Session) -> list[dict]:
    rows = {r.integration_name: r for r in db.query(AppSetting).all()}
    out = []
    for name in INTEGRATIONS:
        meta = INTEGRATION_META[name]
        row = rows.get(name)
        out.append({
            "name": name,
            "display_name": meta["display_name"],
            "description": meta["description"],
            "key_label": meta["key_label"],
            "is_connected": bool(row and row.api_key_encrypted),
            "is_enabled": bool(row and row.is_enabled),
            "last_tested_at": row.last_tested_at.isoformat() if row and row.last_tested_at else None,
            "test_status": row.test_status if row else None,
            "test_message": row.test_message if row else None,
        })
    return out


def upsert_integration(
    db: Session,
    name: str,
    api_key: Optional[str],
    is_enabled: bool,
) -> dict:
    if name not in INTEGRATIONS:
        raise ValueError(f"Unknown integration: {name}")
    row = db.query(AppSetting).filter(AppSetting.integration_name == name).first()
    if not row:
        row = AppSetting(integration_name=name)
        db.add(row)
    if api_key is not None and api_key.strip():
        row.api_key_encrypted = encrypt(api_key.strip())
    elif api_key == "":
        # Empty string means "clear the key"
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


def get_key(db: Session, name: str) -> Optional[str]:
    row = db.query(AppSetting).filter(AppSetting.integration_name == name).first()
    if not row or not row.is_enabled or not row.api_key_encrypted:
        return None
    try:
        return decrypt(row.api_key_encrypted)
    except Exception:
        return None


def record_test_result(db: Session, name: str, ok: bool, message: str) -> None:
    row = db.query(AppSetting).filter(AppSetting.integration_name == name).first()
    if not row:
        return
    row.last_tested_at = datetime.utcnow()
    row.test_status = "ok" if ok else "failed"
    row.test_message = message
    db.commit()
