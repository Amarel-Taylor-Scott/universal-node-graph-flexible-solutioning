"""SourceLoop direct-source intelligence runtime."""

from .config import Settings
from .domain import CaseCreate, CaseKind, CaseRecord, InvestigationMode, RiskTier
from .extended_engine import InvestigativeSourceLoopEngine

SourceLoopEngine = InvestigativeSourceLoopEngine

__all__ = [
    "CaseCreate",
    "CaseKind",
    "CaseRecord",
    "InvestigationMode",
    "InvestigativeSourceLoopEngine",
    "RiskTier",
    "Settings",
    "SourceLoopEngine",
]
__version__ = "0.3.0"
