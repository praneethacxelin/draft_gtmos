from typing import Optional
from pydantic import BaseModel


class SettingPutBody(BaseModel):
    api_key: str


class SettingTestBody(BaseModel):
    api_key: Optional[str] = None


class SettingTestResult(BaseModel):
    ok: bool
    message: str


class SettingStatus(BaseModel):
    name: str
    configured: bool
