"""SourceLoop direct-source intelligence runtime."""

from .config import Settings
from .domain import CaseCreate, CaseKind, CaseRecord
from .engine import SourceLoopEngine

__all__ = ["CaseCreate", "CaseKind", "CaseRecord", "Settings", "SourceLoopEngine"]
__version__ = "0.2.0"
