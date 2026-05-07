from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


class ORMBase(BaseModel):
    """Pydantic v2 base that allows building from SQLAlchemy ORM rows."""
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


JsonDict = dict[str, Any]
