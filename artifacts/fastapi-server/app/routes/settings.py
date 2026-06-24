from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_session, User
from app.auth import current_user
from app.services import settings_service, clients, fetch_limits, rate_limit

router = APIRouter(prefix="/settings", tags=["settings"])


class IntegrationUpdate(BaseModel):
    api_key: str | None = None
    is_enabled: bool = True


@router.get("/integrations")
def list_integrations(
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    return settings_service.list_integrations(db, user.id)


@router.put("/integrations/{name}")
def update_integration(
    name: str,
    body: IntegrationUpdate,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    try:
        return settings_service.upsert_integration(db, user.id, name, body.api_key, body.is_enabled)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/integrations/{name}/test")
def test_integration(
    name: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    import time
    row = settings_service.get_raw(db, user.id, name)
    if not row or not row.api_key_encrypted:
        raise HTTPException(400, "No saved key for this integration")
    from app.crypto import decrypt
    try:
        key = decrypt(row.api_key_encrypted)
    except Exception:
        raise HTTPException(400, "Stored key could not be decrypted")
    started = time.perf_counter()
    ok, msg = clients.test_connection(name, key)
    latency_ms = int((time.perf_counter() - started) * 1000)
    settings_service.record_test_result(db, user.id, name, ok, msg)
    return {"ok": ok, "message": msg, "latency_ms": latency_ms}


class FetchLimitsUpdate(BaseModel):
    leads_per_run: int | None = None
    signals_per_account: int | None = None
    market_sizing_results: int | None = None


@router.get("/fetch-limits")
def get_fetch_limits(
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    return fetch_limits.get_limits_with_max(db, user.id)


@router.put("/fetch-limits")
def put_fetch_limits(
    body: FetchLimitsUpdate,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    updated = fetch_limits.set_limits(
        db, user.id, body.model_dump(exclude_none=True)
    )
    return {
        "limits": updated,
        "maximums": dict(fetch_limits.MAXIMUMS),
        "defaults": dict(fetch_limits.DEFAULTS),
    }


@router.get("/sender-status")
def get_sender_status(
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    instantly_key = settings_service.get_key(db, user.id, "instantly")
    if not instantly_key:
        return {
            "connected": False,
            "email": None,
            "provider": "Instantly",
            "status": "Not Configured",
            "warmup_info": "Warmup information unavailable."
        }

    accounts_data = clients.instantly_get_accounts(instantly_key)
    if not accounts_data or not isinstance(accounts_data, dict):
        return {
            "connected": False,
            "email": None,
            "provider": "Instantly",
            "status": "Error Fetching Accounts",
            "warmup_info": "Warmup information unavailable."
        }

    items = accounts_data.get("items", [])
    if not items or len(items) == 0:
        return {
            "connected": True,
            "email": None,
            "provider": "Instantly",
            "status": "Connected (No Sender Accounts)",
            "warmup_info": "Warmup information unavailable."
        }

    first_acc = items[0]
    email = first_acc.get("email")
    status_code = first_acc.get("status")
    status_str = "Connected" if status_code == 1 else "Inactive"

    return {
        "connected": True,
        "email": email,
        "provider": "Instantly",
        "status": status_str,
        "warmup_info": "Warmup information unavailable."
    }


@router.get("/rate-limits/status")
def rate_limit_status(
    user: User = Depends(current_user),
) -> dict:
    return {"buckets": rate_limit.status()}
