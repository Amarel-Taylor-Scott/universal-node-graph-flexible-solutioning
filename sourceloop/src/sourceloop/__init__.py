"""SourceLoop direct-source intelligence runtime."""

from .domain import CaseKind, CaseRecord, CaseStatus, PractitionerStage
from .engine import SourceLoopEngine

__all__ = [
    "CaseKind",
    "CaseRecord",
    "CaseStatus",
    "PractitionerStage",
    "SourceLoopEngine",
]

__version__ = "0.1.0"
