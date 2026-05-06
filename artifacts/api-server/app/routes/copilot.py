from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_session
from app.agents.sdr_copilot import feed

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.get("/feed")
def get_feed(strategy_id: str, db: Session = Depends(get_session)) -> list[dict]:
    return feed(db, strategy_id)
