"""Pydantic v2 schema layer mirroring the SQLAlchemy models in ``app.db``.

Each schema covers the read shape returned by the API; create / update bodies
live alongside as ``*Create`` / ``*Update`` variants where mutation routes
exist. Routers should accept and return these models so the API contract
is explicit and validated at the edge instead of via ad-hoc dict shaping.
"""
from .strategies import (
    StrategyCreate,
    StrategyUpdate,
    StrategyOut,
    StrategyRunRequest,
)
from .accounts import AccountOut
from .contacts import ContactOut, ContactSnoozeOut, ContactSnoozeBody
from .signals import SignalOut
from .sequences import (
    SequenceOut,
    SequenceStepOut,
    SequenceCreate,
    SequenceLaunchOut,
)
from .outreach import OutreachEventOut
from .copilot import CopilotFeedItem
from .intelligence import (
    EngagementEventIn,
    FeedbackIn,
    AttributionIn,
    QualifyOut,
    LoopBackOut,
)
from .settings import (
    SettingPutBody,
    SettingTestBody,
    SettingTestResult,
    SettingStatus,
)

__all__ = [
    "StrategyCreate", "StrategyUpdate", "StrategyOut", "StrategyRunRequest",
    "AccountOut",
    "ContactOut", "ContactSnoozeOut", "ContactSnoozeBody",
    "SignalOut",
    "SequenceOut", "SequenceStepOut", "SequenceCreate", "SequenceLaunchOut",
    "OutreachEventOut",
    "CopilotFeedItem",
    "EngagementEventIn", "FeedbackIn", "AttributionIn", "QualifyOut", "LoopBackOut",
    "SettingPutBody", "SettingTestBody", "SettingTestResult", "SettingStatus",
]
