from datetime import datetime
from typing import Optional
from ._base import ORMBase, JsonDict


class OutreachEventOut(ORMBase):
    id: str
    sequence_id: str
    sequence_step_id: Optional[str] = None
    event_type: str
    occurred_at: datetime
    raw_data_json: Optional[JsonDict] = None
