from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field
from ._base import ORMBase, JsonDict


class StrategyCreate(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    target_market: Optional[str] = None
    pain_points_raw: Optional[str] = None


class StrategyUpdate(BaseModel):
    product_name: Optional[str] = None
    description: Optional[str] = None
    target_market: Optional[str] = None
    pain_points_raw: Optional[str] = None


class StrategyRunRequest(BaseModel):
    """Body for POST /strategies/{id}/run — currently no fields, but reserved
    for future controls (e.g. force_regenerate, focus_segments)."""
    force: bool = False


class StrategyOut(ORMBase):
    id: str
    product_name: str
    description: str
    target_market: Optional[str] = None
    pain_points_raw: Optional[str] = None
    status: str
    icp_json: Optional[JsonDict] = None
    personas_json: Optional[JsonDict] = None
    problems_json: Optional[JsonDict] = None
    naics_json: Optional[JsonDict] = None
    stakeholder_map_json: Optional[JsonDict] = None
    use_cases_json: Optional[JsonDict] = None
    tam_sam_som_json: Optional[JsonDict] = None
    created_at: datetime
    updated_at: datetime
