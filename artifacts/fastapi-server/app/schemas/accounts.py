from datetime import datetime
from typing import Optional
from ._base import ORMBase, JsonDict


class AccountOut(ORMBase):
    id: str
    strategy_id: str
    company_name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    revenue_range: Optional[str] = None
    tier: Optional[int] = None
    enrichment_json: Optional[JsonDict] = None
    created_at: datetime
