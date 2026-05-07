from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_session
from app.services import settings_service, clients

router = APIRouter(prefix="/settings", tags=["settings"])


class IntegrationUpdate(BaseModel):
    api_key: str | None = None
    is_enabled: bool = True


@router.get("/integrations")
def list_integrations(db: Session = Depends(get_session)) -> list[dict]:
    return settings_service.list_integrations(db)


@router.put("/integrations/{name}")
def update_integration(name: str, body: IntegrationUpdate, db: Session = Depends(get_session)) -> dict:
    try:
        return settings_service.upsert_integration(db, name, body.api_key, body.is_enabled)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/integrations/{name}/test")
def test_integration(name: str, db: Session = Depends(get_session)) -> dict:
    import time
    row = settings_service.get_raw(db, name)
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
    settings_service.record_test_result(db, name, ok, msg)
    return {"ok": ok, "message": msg, "latency_ms": latency_ms}
