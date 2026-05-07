from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class EngagementEventIn(BaseModel):
    contact_id: str
    event_type: str
    metadata: Optional[dict[str, Any]] = None


class FeedbackIn(BaseModel):
    contact_id: Optional[str] = None
    sequence_id: Optional[str] = None
    rating: Optional[int] = None
    text: str


class AttributionIn(BaseModel):
    strategy_id: str
    source_channel: str
    conversion_event: str
    conversion_value: Optional[float] = 0


class QualifyOut(BaseModel):
    contact_id: str
    qualification: str
    score: float
    reasons: list[str] = []


class LoopBackOut(BaseModel):
    suggestions: list[dict[str, Any]] = []
