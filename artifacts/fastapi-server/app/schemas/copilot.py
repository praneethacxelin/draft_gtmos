from typing import Any, Optional
from pydantic import BaseModel


class CopilotFeedItem(BaseModel):
    contact_id: str
    contact_name: str
    company: Optional[str] = None
    score: Optional[float] = None
    next_action: str
    rationale: Optional[str] = None
    related_signal: Optional[dict[str, Any]] = None
