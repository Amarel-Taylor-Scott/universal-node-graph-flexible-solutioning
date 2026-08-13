"""Domain-neutral engineering design and capability-coverage contracts.

These records describe *where* SolutionGraph can be applied and what evidence
exists for a capability.  They do not change compiler admission, grant runtime
authority, or turn a catalog entry into implementation evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from solutiongraph.model import DIGEST_RE, ID_RE, canonical_json, sha256_digest

UNIVERSAL_ENGINEERING_MODEL_VERSION = "0.1"
COVERAGE_STATUSES = ("strong", "thin", "catalog-only", "blocked", "empty")
MATURITY_LEVELS = tuple(f"C{index}" for index in range(8))
QUESTION_STATUSES = ("selected", "deferred", "blocked", "not-applicable")
RESPONSE_MODES = ("deterministic", "human", "llm", "external")
FINGERPRINT_CHANNEL_IDS = (
    "fingerprint.outcome",
    "fingerprint.interface",
    "fingerprint.workload",
    "fingerprint.topology",
    "fingerprint.effects",
    "fingerprint.temporal",
    "fingerprint.risk",
    "fingerprint.environment",
    "fingerprint.evidence",
    "fingerprint.semantics",
)


def _unique(values: tuple[str, ...], path: str, *, ids: bool = False) -> list[str]:
    problems: list[str] = []
    if len(values) != len(set(values)):
        problems.append(f"{path} must be unique")
    if any(not value.strip() for value in values):
        problems.append(f"{path} must not contain empty values")
    if ids and any(not ID_RE.fullmatch(value) for value in values):
        problems.append(f"{path} must contain namespaced identifiers")
    return problems


def _json_problems(value: Any, path: str) -> list[str]:
    try:
        canonical_json(value)
    except (TypeError, ValueError):
        return [f"{path} must be JSON serialisable"]
    return []


@dataclass(frozen=True)
class ObligationFamily:
    """A reusable semantic obligation, independent of any engineering domain."""

    id: str
    title: str
    description: str
    design_prompt: str
    capability_examples: tuple[str, ...]
    category_ids: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "obligation") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not self.id.startswith("obligation."):
            problems.append(f"{path}.id must begin with obligation.")
        for label, value in (
            ("title", self.title),
            ("description", self.description),
            ("design_prompt", self.design_prompt),
        ):
            if not value.strip():
                problems.append(f"{path}.{label} must not be empty")
        if not self.capability_examples:
            problems.append(f"{path}.capability_examples must not be empty")
        problems.extend(_unique(self.capability_examples, f"{path}.capability_examples"))
        problems.extend(_unique(self.category_ids, f"{path}.category_ids", ids=True))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "design_prompt": self.design_prompt,
            "capability_examples": list(self.capability_examples),
            "category_ids": list(self.category_ids),
        }


@dataclass(frozen=True)
class CapabilityRequirement:
    """One domain capability and the exact repository assets claimed for it."""

    id: str
    title: str
    obligation_id: str
    intent: str
    template_ids: tuple[str, ...] = ()
    example_ids: tuple[str, ...] = ()
    benchmark_ids: tuple[str, ...] = ()
    agent_benchmark_ids: tuple[str, ...] = ()
    question_pack_ids: tuple[str, ...] = ()
    adapter_ids: tuple[str, ...] = ()
    operational_evidence_refs: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    def validate(self, path: str = "capability") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not self.id.startswith("capability."):
            problems.append(f"{path}.id must begin with capability.")
        if not ID_RE.fullmatch(self.obligation_id) or not self.obligation_id.startswith(
            "obligation."
        ):
            problems.append(f"{path}.obligation_id must begin with obligation.")
        if not self.title.strip() or not self.intent.strip():
            problems.append(f"{path}.title and intent must not be empty")
        for label in (
            "template_ids",
            "example_ids",
            "benchmark_ids",
            "agent_benchmark_ids",
            "question_pack_ids",
            "adapter_ids",
        ):
            problems.extend(_unique(getattr(self, label), f"{path}.{label}", ids=True))
        problems.extend(
            _unique(self.operational_evidence_refs, f"{path}.operational_evidence_refs")
        )
        problems.extend(_unique(self.blockers, f"{path}.blockers"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "obligation_id": self.obligation_id,
            "intent": self.intent,
            "template_ids": list(self.template_ids),
            "example_ids": list(self.example_ids),
            "benchmark_ids": list(self.benchmark_ids),
            "agent_benchmark_ids": list(self.agent_benchmark_ids),
            "question_pack_ids": list(self.question_pack_ids),
            "adapter_ids": list(self.adapter_ids),
            "operational_evidence_refs": list(self.operational_evidence_refs),
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True)
class DomainPack:
    """A curated domain view over the same universal graph representations."""

    id: str
    version: str
    title: str
    description: str
    required_obligation_ids: tuple[str, ...]
    capabilities: tuple[CapabilityRequirement, ...]
    standard_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(
        self,
        obligation_ids: tuple[str, ...],
        path: str = "domain_pack",
    ) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not self.id.startswith("domain-pack."):
            problems.append(f"{path}.id must begin with domain-pack.")
        if not self.version.strip() or not self.title.strip() or not self.description.strip():
            problems.append(f"{path}.version, title, and description must not be empty")
        if not self.required_obligation_ids:
            problems.append(f"{path}.required_obligation_ids must not be empty")
        problems.extend(
            _unique(
                self.required_obligation_ids,
                f"{path}.required_obligation_ids",
                ids=True,
            )
        )
        unknown = sorted(set(self.required_obligation_ids) - set(obligation_ids))
        if unknown:
            problems.append(f"{path} references unknown obligations: {', '.join(unknown)}")
        capability_ids = [item.id for item in self.capabilities]
        if len(capability_ids) != len(set(capability_ids)):
            problems.append(f"{path}.capabilities ids must be unique")
        for index, capability in enumerate(self.capabilities):
            problems.extend(capability.validate(f"{path}.capabilities[{index}]"))
            if capability.obligation_id not in self.required_obligation_ids:
                problems.append(
                    f"{path}.capabilities[{index}] maps outside required obligations"
                )
        problems.extend(_unique(self.standard_ids, f"{path}.standard_ids", ids=True))
        problems.extend(_unique(self.limitations, f"{path}.limitations"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "universal_engineering_model_version": UNIVERSAL_ENGINEERING_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "required_obligation_ids": list(self.required_obligation_ids),
            "capabilities": [item.to_dict() for item in self.capabilities],
            "standard_ids": list(self.standard_ids),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class FingerprintChannel:
    """One domain-neutral task-similarity channel with explicit evidence quality."""

    id: str
    values: tuple[tuple[str, Any], ...]
    evidence_kind: str = "evidence.declared"
    confidence: float = 1.0

    def validate(self, path: str = "channel") -> list[str]:
        problems: list[str] = []
        if self.id not in FINGERPRINT_CHANNEL_IDS:
            problems.append(f"{path}.id is not a universal fingerprint channel")
        keys = [key for key, _ in self.values]
        if len(keys) != len(set(keys)) or any(not ID_RE.fullmatch(key) for key in keys):
            problems.append(f"{path}.values keys must be unique namespaced identifiers")
        problems.extend(_json_problems(dict(self.values), f"{path}.values"))
        if not ID_RE.fullmatch(self.evidence_kind):
            problems.append(f"{path}.evidence_kind must be a namespaced identifier")
        if not isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            problems.append(f"{path}.confidence must be between zero and one")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "values": dict(self.values),
            "evidence_kind": self.evidence_kind,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class UniversalDesignContext:
    """Content-addressed task context used by the universal design checklist."""

    id: str
    task_contract_digest: str
    task_id: str
    domain_pack_ids: tuple[str, ...]
    obligation_ids: tuple[str, ...]
    channels: tuple[FingerprintChannel, ...]
    warnings: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "universal_context") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not DIGEST_RE.fullmatch(self.task_contract_digest):
            problems.append(f"{path}.task_contract_digest must be a sha256 digest")
        if not ID_RE.fullmatch(self.task_id):
            problems.append(f"{path}.task_id must be a namespaced identifier")
        problems.extend(_unique(self.domain_pack_ids, f"{path}.domain_pack_ids", ids=True))
        problems.extend(_unique(self.obligation_ids, f"{path}.obligation_ids", ids=True))
        channel_ids = [item.id for item in self.channels]
        if tuple(channel_ids) != FINGERPRINT_CHANNEL_IDS:
            problems.append(
                f"{path}.channels must contain every universal channel in canonical order"
            )
        for index, channel in enumerate(self.channels):
            problems.extend(channel.validate(f"{path}.channels[{index}]"))
        problems.extend(_unique(self.warnings, f"{path}.warnings"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "universal_engineering_model_version": UNIVERSAL_ENGINEERING_MODEL_VERSION,
            "id": self.id,
            "task_contract_digest": self.task_contract_digest,
            "task_id": self.task_id,
            "domain_pack_ids": list(self.domain_pack_ids),
            "obligation_ids": list(self.obligation_ids),
            "channels": [item.to_dict() for item in self.channels],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class EngineeringDesignQuestion:
    """One all-visible question an engineer, deterministic tool, or model can answer."""

    id: str
    obligation_id: str
    prompt: str
    why_it_matters: str
    evidence_requests: tuple[str, ...]
    suggested_checks: tuple[str, ...]
    response_modes: tuple[str, ...]
    required_permissions: tuple[str, ...] = ()
    priority: int = 5
    effort_cost: int = 1

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "engineering_question") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not self.id.startswith("engineering-question."):
            problems.append(f"{path}.id must begin with engineering-question.")
        if not ID_RE.fullmatch(self.obligation_id):
            problems.append(f"{path}.obligation_id must be namespaced")
        if not self.prompt.strip() or not self.why_it_matters.strip():
            problems.append(f"{path}.prompt and why_it_matters must not be empty")
        if not self.evidence_requests or not self.suggested_checks:
            problems.append(f"{path} must request evidence and suggest checks")
        problems.extend(_unique(self.evidence_requests, f"{path}.evidence_requests"))
        problems.extend(_unique(self.suggested_checks, f"{path}.suggested_checks"))
        problems.extend(_unique(self.response_modes, f"{path}.response_modes"))
        if any(mode not in RESPONSE_MODES for mode in self.response_modes):
            problems.append(f"{path}.response_modes contains an unsupported mode")
        problems.extend(
            _unique(
                self.required_permissions,
                f"{path}.required_permissions",
                ids=True,
            )
        )
        if not 1 <= self.priority <= 10 or not 1 <= self.effort_cost <= 10:
            problems.append(f"{path}.priority and effort_cost must be between 1 and 10")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "universal_engineering_model_version": UNIVERSAL_ENGINEERING_MODEL_VERSION,
            "id": self.id,
            "obligation_id": self.obligation_id,
            "prompt": self.prompt,
            "why_it_matters": self.why_it_matters,
            "evidence_requests": list(self.evidence_requests),
            "suggested_checks": list(self.suggested_checks),
            "response_modes": list(self.response_modes),
            "required_permissions": list(self.required_permissions),
            "priority": self.priority,
            "effort_cost": self.effort_cost,
        }


@dataclass(frozen=True)
class EngineeringPlanItem:
    question_id: str
    status: str
    response_mode: str
    reason: str
    priority: int
    effort_cost: int

    def validate(self, path: str = "plan_item") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.question_id):
            problems.append(f"{path}.question_id must be namespaced")
        if self.status not in QUESTION_STATUSES:
            problems.append(f"{path}.status is unsupported")
        if self.response_mode and self.response_mode not in RESPONSE_MODES:
            problems.append(f"{path}.response_mode is unsupported")
        if self.status == "selected" and not self.response_mode:
            problems.append(f"{path} selected questions require a response mode")
        if not self.reason.strip():
            problems.append(f"{path}.reason must not be empty")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "status": self.status,
            "response_mode": self.response_mode,
            "reason": self.reason,
            "priority": self.priority,
            "effort_cost": self.effort_cost,
        }


@dataclass(frozen=True)
class EngineeringDesignPlan:
    context_digest: str
    domain_pack_id: str
    effort: str
    random_seed: int
    items: tuple[EngineeringPlanItem, ...]
    claim_boundary: str = (
        "This checklist allocates design attention. It does not compile a graph, "
        "authorize effects, or establish empirical superiority."
    )

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    @property
    def summary(self) -> dict[str, int]:
        return {
            status: sum(item.status == status for item in self.items)
            for status in QUESTION_STATUSES
        }

    def validate(self, path: str = "engineering_plan") -> list[str]:
        problems: list[str] = []
        if not DIGEST_RE.fullmatch(self.context_digest):
            problems.append(f"{path}.context_digest must be a sha256 digest")
        if not ID_RE.fullmatch(self.domain_pack_id):
            problems.append(f"{path}.domain_pack_id must be namespaced")
        if self.effort not in ("E1", "E3", "E5", "E7", "E10"):
            problems.append(f"{path}.effort is unsupported")
        ids = [item.question_id for item in self.items]
        if len(ids) != len(set(ids)):
            problems.append(f"{path}.items must contain unique questions")
        for index, item in enumerate(self.items):
            problems.extend(item.validate(f"{path}.items[{index}]"))
        if not self.claim_boundary.strip():
            problems.append(f"{path}.claim_boundary must not be empty")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "universal_engineering_model_version": UNIVERSAL_ENGINEERING_MODEL_VERSION,
            "context_digest": self.context_digest,
            "domain_pack_id": self.domain_pack_id,
            "effort": self.effort,
            "random_seed": self.random_seed,
            "items": [item.to_dict() for item in self.items],
            "summary": self.summary,
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class CapabilityAssessment:
    capability_id: str
    obligation_id: str
    status: str
    maturity_level: str
    satisfied_gates: tuple[str, ...]
    next_gate: str
    resolved_assets: tuple[str, ...]
    missing_assets: tuple[str, ...]
    route_count_upper_bound: int
    blockers: tuple[str, ...]
    evidence_digest: str

    def validate(self, path: str = "capability_assessment") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.capability_id) or not ID_RE.fullmatch(
            self.obligation_id
        ):
            problems.append(f"{path} capability and obligation ids must be namespaced")
        if self.status not in COVERAGE_STATUSES:
            problems.append(f"{path}.status is unsupported")
        if self.maturity_level not in MATURITY_LEVELS:
            problems.append(f"{path}.maturity_level is unsupported")
        problems.extend(_unique(self.satisfied_gates, f"{path}.satisfied_gates"))
        problems.extend(_unique(self.resolved_assets, f"{path}.resolved_assets"))
        problems.extend(_unique(self.missing_assets, f"{path}.missing_assets"))
        problems.extend(_unique(self.blockers, f"{path}.blockers"))
        if self.route_count_upper_bound < 0:
            problems.append(f"{path}.route_count_upper_bound must be non-negative")
        if not DIGEST_RE.fullmatch(self.evidence_digest):
            problems.append(f"{path}.evidence_digest must be a sha256 digest")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "obligation_id": self.obligation_id,
            "status": self.status,
            "maturity_level": self.maturity_level,
            "satisfied_gates": list(self.satisfied_gates),
            "next_gate": self.next_gate,
            "resolved_assets": list(self.resolved_assets),
            "missing_assets": list(self.missing_assets),
            "route_count_upper_bound": self.route_count_upper_bound,
            "blockers": list(self.blockers),
            "evidence_digest": self.evidence_digest,
        }


@dataclass(frozen=True)
class DomainCoverageAssessment:
    domain_pack_id: str
    domain_pack_digest: str
    capabilities: tuple[CapabilityAssessment, ...]
    status_counts: tuple[tuple[str, int], ...]
    lowest_maturity_level: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_pack_id": self.domain_pack_id,
            "domain_pack_digest": self.domain_pack_digest,
            "capabilities": [item.to_dict() for item in self.capabilities],
            "status_counts": dict(self.status_counts),
            "lowest_maturity_level": self.lowest_maturity_level,
        }


@dataclass(frozen=True)
class UniversalCoverageReport:
    id: str
    generated_from: str
    domains: tuple[DomainCoverageAssessment, ...]
    status_counts: tuple[tuple[str, int], ...]
    claim_boundary: str

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "coverage_report") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be namespaced")
        if not DIGEST_RE.fullmatch(self.generated_from):
            problems.append(f"{path}.generated_from must be a sha256 digest")
        domain_ids = [item.domain_pack_id for item in self.domains]
        if len(domain_ids) != len(set(domain_ids)):
            problems.append(f"{path}.domains must be unique")
        for domain_index, domain in enumerate(self.domains):
            if not DIGEST_RE.fullmatch(domain.domain_pack_digest):
                problems.append(
                    f"{path}.domains[{domain_index}].domain_pack_digest is invalid"
                )
            for capability_index, capability in enumerate(domain.capabilities):
                problems.extend(
                    capability.validate(
                        f"{path}.domains[{domain_index}].capabilities[{capability_index}]"
                    )
                )
        if tuple(key for key, _ in self.status_counts) != COVERAGE_STATUSES:
            problems.append(f"{path}.status_counts must use canonical status order")
        if not self.claim_boundary.strip():
            problems.append(f"{path}.claim_boundary must not be empty")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "universal_engineering_model_version": UNIVERSAL_ENGINEERING_MODEL_VERSION,
            "id": self.id,
            "generated_from": self.generated_from,
            "domains": [item.to_dict() for item in self.domains],
            "status_counts": dict(self.status_counts),
            "claim_boundary": self.claim_boundary,
        }


__all__ = [
    "COVERAGE_STATUSES",
    "CapabilityAssessment",
    "CapabilityRequirement",
    "DomainCoverageAssessment",
    "DomainPack",
    "EngineeringDesignPlan",
    "EngineeringDesignQuestion",
    "EngineeringPlanItem",
    "FINGERPRINT_CHANNEL_IDS",
    "FingerprintChannel",
    "MATURITY_LEVELS",
    "ObligationFamily",
    "QUESTION_STATUSES",
    "RESPONSE_MODES",
    "UNIVERSAL_ENGINEERING_MODEL_VERSION",
    "UniversalCoverageReport",
    "UniversalDesignContext",
]
