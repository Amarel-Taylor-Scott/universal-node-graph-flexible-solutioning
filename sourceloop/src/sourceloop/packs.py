"""Data-driven vertical-pack discovery and defaults."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .domain import CaseKind


class VerticalPack(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    case_kind: CaseKind
    description: str = ""
    max_contacts: int = Field(default=5, ge=1, le=25)
    max_followups: int = Field(default=1, ge=0, le=3)
    completion_target: int = Field(default=1, ge=1, le=25)
    required_fields: list[str] = Field(default_factory=list)
    optional_fields: list[str] = Field(default_factory=list)
    specialist_roles: list[str] = Field(default_factory=list)
    prohibited_actions: list[str] = Field(default_factory=list)
    question_prompts: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class PackRegistry:
    def __init__(self, search_path: Path | None = None) -> None:
        self.search_path = search_path or Path(__file__).resolve().parents[2] / "packs"
        self._packs = self._load()

    def _load(self) -> dict[str, VerticalPack]:
        packs: dict[str, VerticalPack] = {}
        if not self.search_path.exists():
            return packs
        for path in sorted(self.search_path.glob("*.yaml")):
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            payload["raw"] = payload.copy()
            pack = VerticalPack.model_validate(payload)
            packs[pack.id] = pack
        return packs

    def list(self) -> list[VerticalPack]:
        return list(self._packs.values())

    def get(self, pack_id: str | None) -> VerticalPack | None:
        if pack_id is None:
            return None
        return self._packs.get(pack_id)

    def default_for(self, kind: CaseKind) -> VerticalPack | None:
        return next((pack for pack in self._packs.values() if pack.case_kind is kind), None)
