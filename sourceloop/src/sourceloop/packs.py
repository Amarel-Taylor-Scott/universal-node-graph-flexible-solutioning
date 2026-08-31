"""Data-driven vertical-pack discovery, governance, and response contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .domain import CaseKind, ContactRoute, FindingKind, InvestigationMode, RiskTier, Severity


class ResponseField(BaseModel):
    """A field the practitioner should attempt to obtain from a respondent."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    question: str
    markers: list[str] = Field(default_factory=list)
    critical: bool = False
    aliases: list[str] = Field(default_factory=list)

    @field_validator("markers", "aliases")
    @classmethod
    def normalize_markers(cls, values: list[str]) -> list[str]:
        return [value.strip().lower() for value in values if value.strip()]


class FindingRule(BaseModel):
    """Declarative evidence rule. A match creates a reviewable finding, not a verdict."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: FindingKind
    severity: Severity = Severity.INFO
    title: str
    summary: str
    patterns: list[str] = Field(default_factory=list)
    missing_field: str | None = None
    value_pattern: str | None = None
    confidence: float = Field(default=0.75, ge=0, le=1)
    requires_human_review: bool = True
    negative_patterns: list[str] = Field(default_factory=list)


class DemoReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str
    subject: str | None = None


class VerticalPack(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    case_kind: CaseKind
    description: str = ""
    investigation_mode: InvestigationMode | None = None
    risk_tier: RiskTier = RiskTier.STANDARD
    institutional_only: bool = False
    requires_requester_email: bool = False
    required_acknowledgements: list[str] = Field(default_factory=list)
    allowed_channels: list[str] = Field(default_factory=lambda: ["email"])
    max_contacts: int = Field(default=5, ge=1, le=25)
    max_followups: int = Field(default=1, ge=0, le=3)
    completion_target: int = Field(default=1, ge=1, le=25)
    completion_basis: str = "results"
    required_fields: list[str] = Field(default_factory=list)
    optional_fields: list[str] = Field(default_factory=list)
    specialist_roles: list[str] = Field(default_factory=list)
    stage_roles: dict[str, list[str]] = Field(default_factory=dict)
    prohibited_actions: list[str] = Field(default_factory=list)
    prohibited_request_patterns: list[str] = Field(default_factory=list)
    sensitive_data_categories: list[str] = Field(default_factory=list)
    question_prompts: list[str] = Field(default_factory=list)
    response_fields: list[ResponseField] = Field(default_factory=list)
    finding_rules: list[FindingRule] = Field(default_factory=list)
    critical_quote_fields: list[str] = Field(default_factory=list)
    followup_approval_required: bool = True
    message_purpose: str = "transparent information request"
    respondent_value: str = "reduce misrouted or repeated inquiries"
    reuse_policy: str = "case_scoped"
    demo_contacts: list[ContactRoute] = Field(default_factory=list)
    demo_replies: list[DemoReply] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)

    @field_validator("completion_basis")
    @classmethod
    def validate_completion_basis(cls, value: str) -> str:
        allowed = {"results", "responses", "quotes", "findings"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            raise ValueError(f"completion_basis must be one of {sorted(allowed)}")
        return normalized

    def roles_for(self, stage: str, fallback: list[str]) -> list[str]:
        return self.stage_roles.get(stage, fallback)

    def field(self, field_id: str) -> ResponseField | None:
        return next((item for item in self.response_fields if item.id == field_id), None)


class PackRegistry:
    def __init__(self, search_path: Path | None = None) -> None:
        package_path = Path(__file__).resolve().parent / "vertical_packs"
        workspace_path = Path(__file__).resolve().parents[2] / "packs"
        self.search_paths = [search_path] if search_path else [package_path, workspace_path]
        self._packs = self._load()

    def _load(self) -> dict[str, VerticalPack]:
        packs: dict[str, VerticalPack] = {}
        for search_path in self.search_paths:
            if search_path is None or not search_path.exists():
                continue
            for path in sorted(search_path.glob("*.yaml")):
                payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                payload["raw"] = payload.copy()
                pack = VerticalPack.model_validate(payload)
                packs[pack.id] = pack
        return packs

    def list(self) -> list[VerticalPack]:
        return sorted(self._packs.values(), key=lambda pack: (pack.risk_tier.value, pack.name.lower()))

    def get(self, pack_id: str | None) -> VerticalPack | None:
        if pack_id is None:
            return None
        return self._packs.get(pack_id)

    def require(self, pack_id: str | None) -> VerticalPack:
        pack = self.get(pack_id)
        if pack is None:
            raise KeyError(f"Unknown SourceLoop pack: {pack_id}")
        return pack

    def default_for(self, kind: CaseKind) -> VerticalPack | None:
        return next((pack for pack in self.list() if pack.case_kind is kind), None)
