from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from ._base import ORMBase


class ContactOut(ORMBase):
    id: str
    account_id: str
    strategy_id: str
    full_name: str
    title: Optional[str] = None
    email: Optional[str] = None
    seniority: Optional[str] = None
    persona_type: Optional[str] = None
    icp_fit_score: Optional[float] = None
    signal_score: Optional[float] = None
    total_score: Optional[float] = None
    tier: Optional[int] = None
    is_demo: Optional[bool] = None


class ContactSnoozeBody(BaseModel):
    hours: int = Field(default=24, ge=1, le=24 * 30)
    reason: Optional[str] = None


class ContactSnoozeOut(ORMBase):
    id: str
    contact_id: str
    strategy_id: str
    snoozed_until: datetime
    reason: Optional[str] = None
