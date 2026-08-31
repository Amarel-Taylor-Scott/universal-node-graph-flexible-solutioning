"""Typed domain contracts for cases, conversations, claims, quotes, and mailbox events."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:20]}"


def stable_key(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def case_token(case_id: str) -> str:
    """Return a short, deterministic token suitable for an email subject."""

    return stable_key("case-token", case_id)[:12].upper()


class PractitionerStage(StrEnum):
    ORIENT = "orient"
    RECONCILE_HORIZON = "reconcile_horizon"
    ASSESS_PREPARE = "assess_prepare"
    DECIDE_NEXT = "decide_next"
    HOW = "how"
    ACT = "act"
    VERIFY = "verify"
    INTEGRATE_COMMIT = "integrate_commit"
    ROUTE = "route"


STAGE_ORDER: tuple[PractitionerStage, ...] = tuple(PractitionerStage)


class CaseKind(StrEnum):
    CIVIC_INTELLIGENCE = "civic_intelligence"
    QUOTE_INTELLIGENCE = "quote_intelligence"
    DATA_VERIFICATION = "data_verification"


class CaseStatus(StrEnum):
    ACTIVE = "active"
    WAITING_INPUT = "waiting_input"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_EXTERNAL = "waiting_external"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActionType(StrEnum):
    SEND_EMAIL = "send_email"


class ActionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DISPATCHED = "dispatched"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class Direction(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ClaimKind(StrEnum):
    FACT_CONFIRMATION = "fact_confirmation"
    RESPONDENT_REPORT = "respondent_report"
    ESTIMATE = "estimate"
    OPINION = "opinion"
    FORWARD_LOOKING_PLAN = "forward_looking_plan"
    REFERRAL = "referral"
    DENIAL = "denial"
    UNCERTAINTY = "uncertainty"
    REFUSAL = "refusal"
    SYSTEM_INFERENCE = "system_inference"


class GeoPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    label: str = ""
    precision: str = "public_venue"


class AttachmentInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: new_id("attachment"))
    filename: str
    content_type: str = "application/octet-stream"
    size_bytes: int = Field(ge=0)
    sha256: str
    evidence_path: str | None = None
    status: str = "stored"


class ContactRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: new_id("contact"))
    organization_name: str
    role_title: str
    endpoint: str
    channel: str = "email"
    source: str = "customer_supplied"
    source_public: bool = True
    confidence: float = Field(default=0.8, ge=0, le=1)
    geography: str | None = None
    location: GeoPoint | None = None
    topics: list[str] = Field(default_factory=list)

    @field_validator("endpoint")
    @classmethod
    def normalize_endpoint(cls, value: str) -> str:
        return value.strip().lower()


class AgentRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: new_id("run"))
    role: str
    stage: PractitionerStage
    runtime: str
    status: AgentRunStatus = AgentRunStatus.RUNNING
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    output: dict[str, Any] = Field(default_factory=dict)
    raw_output: str = ""
    error: str | None = None


class ActionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: new_id("action"))
    action_type: ActionType = ActionType.SEND_EMAIL
    status: ActionStatus = ActionStatus.PENDING
    recipient: str
    recipient_name: str = ""
    organization_name: str = ""
    subject: str
    body: str
    approval_required: bool = True
    followup: bool = False
    thread_id: str = ""
    in_reply_to: str | None = None
    references: list[str] = Field(default_factory=list)
    reply_to: str | None = None
    idempotency_key: str = ""
    proposed_by_run_ids: list[str] = Field(default_factory=list)
    policy_receipt: dict[str, Any] = Field(default_factory=dict)
    approved_by: str | None = None
    approved_at: datetime | None = None
    dispatched_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Interaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: new_id("interaction"))
    thread_id: str
    direction: Direction
    endpoint: str
    subject: str
    body: str
    evidence_id: str = Field(default_factory=lambda: new_id("evidence"))
    raw_evidence_path: str | None = None
    provider_message_id: str | None = None
    in_reply_to: str | None = None
    references: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    attachments: list[AttachmentInfo] = Field(default_factory=list)
    related_action_id: str | None = None
    processed: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: new_id("claim"))
    subject_id: str
    predicate: str
    value: Any
    kind: ClaimKind
    confidence: float = Field(ge=0, le=1)
    geography_scope: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    asserted_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime | None = None
    corroboration_status: str = "unreviewed"
    reuse_scope: str = "case_only"


class QuoteLineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    unit: str
    quantity: float | None = None
    unit_price: float
    currency: str = "USD"
    one_time: bool = False
    assumptions: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)


class Quote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: new_id("quote"))
    supplier_name: str
    contact_id: str | None = None
    quote_type: str = "non_binding"
    line_items: list[QuoteLineItem] = Field(default_factory=list)
    commercial_terms: dict[str, Any] = Field(default_factory=dict)
    operational_terms: dict[str, Any] = Field(default_factory=dict)
    exclusions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    currency: str = "USD"
    valid_until: datetime | None = None
    received_at: datetime = Field(default_factory=utcnow)
    evidence_ids: list[str] = Field(default_factory=list)
    extraction_confidence: float = Field(default=0.8, ge=0, le=1)
    unresolved_fields: list[str] = Field(default_factory=list)
    normalization_lineage: list[str] = Field(default_factory=list)

    @property
    def normalized_total(self) -> float:
        return round(
            sum((item.quantity if item.quantity is not None else 1.0) * item.unit_price for item in self.line_items),
            2,
        )


class CaseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: new_id("case"))
    version: int = 0
    title: str
    kind: CaseKind
    objective: str
    requester_name: str
    requester_email: str | None = None
    pack: str | None = None
    demo: bool = False
    location: GeoPoint | None = None
    requirements: dict[str, Any] = Field(default_factory=dict)
    unknowns: list[str] = Field(default_factory=list)
    stage: PractitionerStage = PractitionerStage.ORIENT
    status: CaseStatus = CaseStatus.ACTIVE
    max_contacts: int = 5
    max_followups: int = 1
    completion_target: int = 1
    contacts: list[ContactRoute] = Field(default_factory=list)
    agent_runs: list[AgentRun] = Field(default_factory=list)
    actions: list[ActionProposal] = Field(default_factory=list)
    interactions: list[Interaction] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    quotes: list[Quote] = Field(default_factory=list)
    stage_outputs: dict[str, Any] = Field(default_factory=dict)
    graph_committed: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    kind: CaseKind
    objective: str
    requester_name: str
    requester_email: str | None = None
    pack: str | None = None
    demo: bool = False
    location: GeoPoint | None = None
    requirements: dict[str, Any] = Field(default_factory=dict)
    contacts: list[ContactRoute] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approver: str
    note: str = ""


class InboundEmail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    thread_id: str
    sender: str
    subject: str
    body: str
    provider_message_id: str | None = None
    in_reply_to: str | None = None
    references: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    evidence_id: str | None = None
    raw_evidence_path: str | None = None
    attachments: list[AttachmentInfo] = Field(default_factory=list)


class CaseEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: new_id("event"))
    case_id: str
    sequence: int
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


class OutboxRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: new_id("message"))
    case_id: str
    action_id: str
    idempotency_key: str
    recipient: str
    sender: str
    subject: str
    body: str
    status: str
    provider_message_id: str | None = None
    thread_id: str = ""
    in_reply_to: str | None = None
    references: list[str] = Field(default_factory=list)
    last_error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class MailboxSyncResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fetched: int = 0
    processed: int = 0
    duplicates: int = 0
    unmatched: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)


class WorkerHeartbeat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    worker_id: str
    status: str
    details: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=utcnow)


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    role: str
    stage: PractitionerStage
    instruction: str
    payload: dict[str, Any]
    output_contract: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output: dict[str, Any]
    raw_output: str = ""
    runtime: str
