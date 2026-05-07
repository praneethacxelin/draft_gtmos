from datetime import datetime
from typing import Optional
from ._base import ORMBase, JsonDict


class SignalOut(ORMBase):
    id: str
    strategy_id: str
    account_id: Optional[str] = None
    signal_type: str
    source: Optional[str] = None
    summary: str
    strength_score: Optional[float] = None
    raw_data_json: Optional[JsonDict] = None
    detected_at: datetime
