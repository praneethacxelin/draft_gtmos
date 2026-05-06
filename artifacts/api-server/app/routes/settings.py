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
    key = settings_service.get_key(db, name)
    if not key:
        raise HTTPException(400, "No saved key for this integration")
    ok, msg = clients.test_connection(name, key)
    settings_service.record_test_result(db, name, ok, msg)
    return {"ok": ok, "message": msg}
