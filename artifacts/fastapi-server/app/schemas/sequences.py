from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel
from ._base import ORMBase, JsonDict


class SequenceCreate(BaseModel):
    contact_id: str


class SequenceStepOut(ORMBase):
    id: str
    sequence_id: str
    step_number: int
    channel: str
    subject: Optional[str] = None
    body: Optional[str] = None
    wait_days: Optional[int] = None
    send_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    status: Optional[str] = None


class SequenceOut(ORMBase):
    id: str
    contact_id: str
    strategy_id: str
    status: str
    deliverability_score: Optional[float] = None
    deliverability_report_json: Optional[JsonDict] = None
    channel_plan_json: Optional[Any] = None
    instantly_campaign_id: Optional[str] = None


class SequenceLaunchOut(BaseModel):
    status: str
    instantly_pushed: bool
    campaign_id: Optional[str] = None
    events: Optional[int] = None
