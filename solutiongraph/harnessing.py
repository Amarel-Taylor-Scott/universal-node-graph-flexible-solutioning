"""Linked graph and feedback-firewall contracts for evaluation harnesses.

An evaluation harness is not one oversized executable DAG.  It is a bundle of
ordinary, independently compiled graphs with explicit authority and data-flow
boundaries.  The records in this module describe that bundle; they do not
execute graphs, isolate candidate code, or approve their own proposals.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from solutiongraph.campaign import EvaluationBoundary
from solutiongraph.model import DIGEST_RE, ID_RE, canonical_json, sha256_digest

HARNESS_MODEL_VERSION = "0.1"
HARNESS_EVIDENCE_MODEL_VERSION = "0.1"
FLOW_EXPOSURES = ("full", "aggregate", "digest", "deny")
CANDIDATE_VISIBILITIES = (
    "none",
    "inputs-only",
    "outputs-only",
    "development",
    "aggregate-only",
)
JUDGMENT_VERDICTS = ("pass", "fail", "error", "abstain")
PANEL_DISPOSITIONS = ("accept", "reject", "review", "insufficient")
PROMOTION_DECISIONS = ("approve", "reject", "defer", "rollback")
FAILURE_SEVERITIES = ("low", "medium", "high", "critical")


def _extension_problems(extensions: tuple[tuple[str, Any], ...], path: str) -> list[str]:
    problems: list[str] = []
    keys = [key for key, _ in extensions]
    if len(keys) != len(set(keys)):
        problems.append(f"{path} keys must be unique")
    for key, value in extensions:
        if not ID_RE.fullmatch(key) or "." not in key:
            problems.append(f"{path}.{key} must use a namespaced key")
        try:
            canonical_json(value)
        except (TypeError, ValueError):
            problems.append(f"{path}.{key} must be JSON serialisable")
    return problems


@dataclass(frozen=True)
class HarnessGraph:
    """One exact graph participating in a larger harness architecture."""

    id: str
    role: str
    program_digest: str
    registry_digest: str
    purpose: str
    authorities: tuple[str, ...]
    candidate_visibility: str = "none"
    human_approval_required: bool = False
    extensions: tuple[tuple[str, Any], ...] = ()

    def validate(self, path: str = "graph") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not ID_RE.fullmatch(self.role):
            problems.append(f"{path}.id and role must be namespaced identifiers")
        for label, digest in (
            ("program_digest", self.program_digest),
            ("registry_digest", self.registry_digest),
        ):
            if not DIGEST_RE.fullmatch(digest):
                problems.append(f"{path}.{label} must be a sha256 digest")
        if not self.purpose.strip():
            problems.append(f"{path}.purpose must not be empty")
        if not self.authorities:
            problems.append(f"{path}.authorities must not be empty")
        if len(self.authorities) != len(set(self.authorities)):
            problems.append(f"{path}.authorities must be unique")
        if any(not ID_RE.fullmatch(item) for item in self.authorities):
            problems.append(f"{path}.authorities must contain namespaced identifiers")
        if self.candidate_visibility not in CANDIDATE_VISIBILITIES:
            problems.append(
                f"{path}.candidate_visibility must be one of " + ", ".join(CANDIDATE_VISIBILITIES)
            )
        authority = set(self.authorities)
        if "harness.evaluate-outer" in authority and self.candidate_visibility != "none":
            problems.append(f"{path}: an outer evaluator must not be candidate-visible")
        if {
            "harness.propose-improvement",
            "harness.approve-promotion",
        }.issubset(authority):
            problems.append(f"{path}: proposal and promotion authority must remain separate")
        if "harness.approve-promotion" in authority and not self.human_approval_required:
            problems.append(f"{path}: promotion authority requires an explicit human approval gate")
        problems.extend(_extension_problems(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "program_digest": self.program_digest,
            "registry_digest": self.registry_digest,
            "purpose": self.purpose,
            "authorities": list(self.authorities),
            "candidate_visibility": self.candidate_visibility,
            "human_approval_required": self.human_approval_required,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class HarnessFlow:
    """One declared artifact flow or explicit feedback firewall."""

    source_graph_id: str
    target_graph_id: str
    artifact_class: str
    exposure: str
    purpose: str
    extensions: tuple[tuple[str, Any], ...] = ()

    def validate(self, path: str = "flow") -> list[str]:
        problems: list[str] = []
        for label, value in (
            ("source_graph_id", self.source_graph_id),
            ("target_graph_id", self.target_graph_id),
            ("artifact_class", self.artifact_class),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be a namespaced identifier")
        if self.source_graph_id == self.target_graph_id:
            problems.append(f"{path} must connect distinct graphs")
        if self.exposure not in FLOW_EXPOSURES:
            problems.append(f"{path}.exposure must be one of {', '.join(FLOW_EXPOSURES)}")
        if not self.purpose.strip():
            problems.append(f"{path}.purpose must not be empty")
        problems.extend(_extension_problems(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_graph_id": self.source_graph_id,
            "target_graph_id": self.target_graph_id,
            "artifact_class": self.artifact_class,
            "exposure": self.exposure,
            "purpose": self.purpose,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class HarnessBundle:
    """Content-addressed linked-graph harness with sealed outer evaluation."""

    id: str
    version: str
    title: str
    description: str
    graphs: tuple[HarnessGraph, ...]
    flows: tuple[HarnessFlow, ...]
    development_boundary: EvaluationBoundary
    outer_boundary: EvaluationBoundary
    development_case_ids: tuple[str, ...]
    holdout_case_ids: tuple[str, ...]
    claim_scope: str = "claim.mechanism-fixture"
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "harness") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or "." not in self.id:
            problems.append(f"{path}.id must be a namespaced identifier")
        if not self.version.strip() or not self.title.strip() or not self.description.strip():
            problems.append(f"{path}.version, title, and description must not be empty")
        if not ID_RE.fullmatch(self.claim_scope):
            problems.append(f"{path}.claim_scope must be a namespaced identifier")
        if not self.graphs:
            problems.append(f"{path}.graphs must not be empty")

        graph_ids = [graph.id for graph in self.graphs]
        if len(graph_ids) != len(set(graph_ids)):
            problems.append(f"{path}.graphs ids must be unique")
        by_id = {graph.id: graph for graph in self.graphs}
        for index, graph in enumerate(self.graphs):
            problems.extend(graph.validate(f"{path}.graphs[{index}]"))

        authorities = {authority for graph in self.graphs for authority in graph.authorities}
        required = {
            "harness.generate-scenarios",
            "harness.execute-solution",
            "harness.evaluate-development",
            "harness.propose-improvement",
            "harness.approve-promotion",
            "harness.evaluate-outer",
        }
        missing_authorities = sorted(required - authorities)
        if missing_authorities:
            problems.append(
                f"{path}.graphs missing harness authorities: " + ", ".join(missing_authorities)
            )

        flow_keys: list[tuple[str, str, str]] = []
        for index, flow in enumerate(self.flows):
            problems.extend(flow.validate(f"{path}.flows[{index}]"))
            flow_keys.append((flow.source_graph_id, flow.target_graph_id, flow.artifact_class))
            if flow.source_graph_id not in by_id or flow.target_graph_id not in by_id:
                problems.append(f"{path}.flows[{index}] references an unknown graph")
                continue
            target = by_id[flow.target_graph_id]
            if (
                "hidden" in flow.artifact_class
                and flow.exposure == "full"
                and target.candidate_visibility != "none"
            ):
                problems.append(
                    f"{path}.flows[{index}]: hidden artifacts cannot be fully exposed "
                    "to a candidate-visible graph"
                )
        if len(flow_keys) != len(set(flow_keys)):
            problems.append(f"{path}.flows source/target/artifact identities must be unique")

        outer_ids = {
            graph.id for graph in self.graphs if "harness.evaluate-outer" in graph.authorities
        }
        improvement_ids = {
            graph.id for graph in self.graphs if "harness.propose-improvement" in graph.authorities
        }
        for outer_id in outer_ids:
            for improvement_id in improvement_ids:
                matching = [
                    flow
                    for flow in self.flows
                    if flow.source_graph_id == outer_id and flow.target_graph_id == improvement_id
                ]
                if not matching or any(flow.exposure != "deny" for flow in matching):
                    problems.append(
                        f"{path}: outer evaluation to improvement requires an explicit "
                        "deny-only feedback firewall"
                    )

        if not self.development_case_ids or not self.holdout_case_ids:
            problems.append(f"{path} development and holdout cases must not be empty")
        if len(self.development_case_ids) != len(set(self.development_case_ids)):
            problems.append(f"{path}.development_case_ids must be unique")
        if len(self.holdout_case_ids) != len(set(self.holdout_case_ids)):
            problems.append(f"{path}.holdout_case_ids must be unique")
        if any(
            not ID_RE.fullmatch(case_id)
            for case_id in (*self.development_case_ids, *self.holdout_case_ids)
        ):
            problems.append(f"{path} case ids must be namespaced identifiers")
        if set(self.development_case_ids) & set(self.holdout_case_ids):
            problems.append(f"{path} development and holdout cases must be disjoint")
        if set(self.outer_boundary.hidden_case_ids) != set(self.holdout_case_ids):
            problems.append(
                f"{path}.outer_boundary hidden cases must exactly match holdout_case_ids"
            )

        problems.extend(self.development_boundary.validate(f"{path}.development_boundary"))
        problems.extend(self.outer_boundary.validate(f"{path}.outer_boundary"))
        problems.extend(_extension_problems(self.extensions, f"{path}.extensions"))
        return problems

    def assert_valid(self) -> HarnessBundle:
        problems = self.validate()
        if problems:
            raise ValueError("invalid harness bundle: " + "; ".join(problems))
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "harness_model_version": HARNESS_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "graphs": [graph.to_dict() for graph in self.graphs],
            "flows": [flow.to_dict() for flow in self.flows],
            "development_boundary": self.development_boundary.to_dict(),
            "outer_boundary": self.outer_boundary.to_dict(),
            "development_case_ids": list(self.development_case_ids),
            "holdout_case_ids": list(self.holdout_case_ids),
            "claim_scope": self.claim_scope,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class AtomicJudgment:
    """One criterion-level judgment with exact evaluator and evidence identity."""

    id: str
    case_id: str
    criterion_id: str
    evaluator_graph_id: str
    evaluator_digest: str
    score: float
    verdict: str
    evidence_digests: tuple[str, ...]
    failure_codes: tuple[str, ...] = ()
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def passed(self) -> bool:
        return self.verdict == "pass"

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "judgment") -> list[str]:
        problems: list[str] = []
        for label, value in (
            ("id", self.id),
            ("case_id", self.case_id),
            ("criterion_id", self.criterion_id),
            ("evaluator_graph_id", self.evaluator_graph_id),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be a namespaced identifier")
        if not DIGEST_RE.fullmatch(self.evaluator_digest):
            problems.append(f"{path}.evaluator_digest must be a sha256 digest")
        if not isfinite(self.score) or not 0.0 <= self.score <= 1.0:
            problems.append(f"{path}.score must be finite and between zero and one")
        if self.verdict not in JUDGMENT_VERDICTS:
            problems.append(f"{path}.verdict must be one of {', '.join(JUDGMENT_VERDICTS)}")
        if not self.evidence_digests:
            problems.append(f"{path}.evidence_digests must not be empty")
        if len(self.evidence_digests) != len(set(self.evidence_digests)) or any(
            not DIGEST_RE.fullmatch(digest) for digest in self.evidence_digests
        ):
            problems.append(f"{path}.evidence_digests must contain unique sha256 digests")
        if len(self.failure_codes) != len(set(self.failure_codes)) or any(
            not ID_RE.fullmatch(code) for code in self.failure_codes
        ):
            problems.append(f"{path}.failure_codes must contain unique namespaced identifiers")
        if self.verdict == "pass" and self.failure_codes:
            problems.append(f"{path}: passing judgments cannot carry failure codes")
        problems.extend(_extension_problems(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "criterion_id": self.criterion_id,
            "evaluator_graph_id": self.evaluator_graph_id,
            "evaluator_digest": self.evaluator_digest,
            "score": self.score,
            "verdict": self.verdict,
            "evidence_digests": list(self.evidence_digests),
            "failure_codes": list(self.failure_codes),
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class JudgePanelReceipt:
    """Blinded aggregation of separately identified atomic judgments."""

    id: str
    case_id: str
    member_judgment_ids: tuple[str, ...]
    aggregation_method: str
    aggregate_score: float
    disagreement: float
    disposition: str
    blind_to_candidate_identity: bool = True
    tie_breaker_judgment_id: str = ""
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "panel") -> list[str]:
        problems: list[str] = []
        for label, value in (("id", self.id), ("case_id", self.case_id)):
            if not ID_RE.fullmatch(value):
                problems.append(f"{path}.{label} must be a namespaced identifier")
        if len(self.member_judgment_ids) < 2:
            problems.append(f"{path}.member_judgment_ids must contain at least two judgments")
        if len(self.member_judgment_ids) != len(set(self.member_judgment_ids)) or any(
            not ID_RE.fullmatch(value) for value in self.member_judgment_ids
        ):
            problems.append(
                f"{path}.member_judgment_ids must contain unique namespaced identifiers"
            )
        if not ID_RE.fullmatch(self.aggregation_method):
            problems.append(f"{path}.aggregation_method must be a namespaced identifier")
        for label, value in (
            ("aggregate_score", self.aggregate_score),
            ("disagreement", self.disagreement),
        ):
            if not isfinite(value) or not 0.0 <= value <= 1.0:
                problems.append(f"{path}.{label} must be finite and between zero and one")
        if self.disposition not in PANEL_DISPOSITIONS:
            problems.append(f"{path}.disposition must be one of {', '.join(PANEL_DISPOSITIONS)}")
        if self.tie_breaker_judgment_id and not ID_RE.fullmatch(self.tie_breaker_judgment_id):
            problems.append(f"{path}.tie_breaker_judgment_id must be empty or namespaced")
        problems.extend(_extension_problems(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "member_judgment_ids": list(self.member_judgment_ids),
            "aggregation_method": self.aggregation_method,
            "aggregate_score": self.aggregate_score,
            "disagreement": self.disagreement,
            "disposition": self.disposition,
            "blind_to_candidate_identity": self.blind_to_candidate_identity,
            "tie_breaker_judgment_id": self.tie_breaker_judgment_id,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class FailureCluster:
    """A leakage-safe grouping of development failures for improvement work."""

    id: str
    member_judgment_ids: tuple[str, ...]
    signature: str
    severity: str
    sanitized_summary: str
    prohibited_detail_classes: tuple[str, ...]
    development_only: bool = True
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "failure_cluster") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if (
            not self.member_judgment_ids
            or len(self.member_judgment_ids) != len(set(self.member_judgment_ids))
            or any(not ID_RE.fullmatch(value) for value in self.member_judgment_ids)
        ):
            problems.append(
                f"{path}.member_judgment_ids must contain unique namespaced identifiers"
            )
        if not self.signature.strip() or not self.sanitized_summary.strip():
            problems.append(f"{path}.signature and sanitized_summary must not be empty")
        if self.severity not in FAILURE_SEVERITIES:
            problems.append(f"{path}.severity must be one of {', '.join(FAILURE_SEVERITIES)}")
        if (
            not self.prohibited_detail_classes
            or len(self.prohibited_detail_classes) != len(set(self.prohibited_detail_classes))
            or any(not ID_RE.fullmatch(value) for value in self.prohibited_detail_classes)
        ):
            problems.append(
                f"{path}.prohibited_detail_classes must contain unique namespaced identifiers"
            )
        problems.extend(_extension_problems(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "member_judgment_ids": list(self.member_judgment_ids),
            "signature": self.signature,
            "severity": self.severity,
            "sanitized_summary": self.sanitized_summary,
            "prohibited_detail_classes": list(self.prohibited_detail_classes),
            "development_only": self.development_only,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class SanitizedOuterSummary:
    """Aggregate-only holdout evidence safe for a promotion gate, not optimization."""

    id: str
    harness_bundle_digest: str
    evaluator_digest: str
    disclosure_policy_digest: str
    holdout_case_count: int
    aggregate_metrics: tuple[tuple[str, float], ...]
    accepted: bool
    receipt_digests: tuple[str, ...]
    omitted_detail_classes: tuple[str, ...]
    feedback_exposure: str = "deny"
    case_ids_included: bool = False
    candidate_visible: bool = False
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "outer_summary") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        for label, digest in (
            ("harness_bundle_digest", self.harness_bundle_digest),
            ("evaluator_digest", self.evaluator_digest),
            ("disclosure_policy_digest", self.disclosure_policy_digest),
        ):
            if not DIGEST_RE.fullmatch(digest):
                problems.append(f"{path}.{label} must be a sha256 digest")
        if self.holdout_case_count <= 0:
            problems.append(f"{path}.holdout_case_count must be positive")
        metric_names = [name for name, _ in self.aggregate_metrics]
        if not self.aggregate_metrics or len(metric_names) != len(set(metric_names)):
            problems.append(f"{path}.aggregate_metrics must contain unique metrics")
        if any(not ID_RE.fullmatch(name) for name in metric_names) or any(
            not isfinite(value) for _, value in self.aggregate_metrics
        ):
            problems.append(f"{path}.aggregate_metrics must use namespaced names and finite values")
        if (
            not self.receipt_digests
            or len(self.receipt_digests) != len(set(self.receipt_digests))
            or any(not DIGEST_RE.fullmatch(value) for value in self.receipt_digests)
        ):
            problems.append(f"{path}.receipt_digests must contain unique sha256 digests")
        if (
            not self.omitted_detail_classes
            or len(self.omitted_detail_classes) != len(set(self.omitted_detail_classes))
            or any(not ID_RE.fullmatch(value) for value in self.omitted_detail_classes)
        ):
            problems.append(
                f"{path}.omitted_detail_classes must contain unique namespaced identifiers"
            )
        if self.feedback_exposure != "deny":
            problems.append(f"{path}.feedback_exposure must remain deny")
        if self.case_ids_included or self.candidate_visible:
            problems.append(f"{path} cannot include case identities or become candidate-visible")
        problems.extend(_extension_problems(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "harness_bundle_digest": self.harness_bundle_digest,
            "evaluator_digest": self.evaluator_digest,
            "disclosure_policy_digest": self.disclosure_policy_digest,
            "holdout_case_count": self.holdout_case_count,
            "aggregate_metrics": dict(self.aggregate_metrics),
            "accepted": self.accepted,
            "receipt_digests": list(self.receipt_digests),
            "omitted_detail_classes": list(self.omitted_detail_classes),
            "feedback_exposure": self.feedback_exposure,
            "case_ids_included": self.case_ids_included,
            "candidate_visible": self.candidate_visible,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class HarnessPromotionDecision:
    """Human-governed promotion decision over an exact proposal and evidence set."""

    id: str
    harness_bundle_digest: str
    proposal_digest: str
    policy_digest: str
    decision: str
    approver_ids: tuple[str, ...]
    evidence_digests: tuple[str, ...]
    outer_summary_digest: str = ""
    rollback_plan_digest: str = ""
    human_authority: bool = True
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "promotion") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        for label, digest in (
            ("harness_bundle_digest", self.harness_bundle_digest),
            ("proposal_digest", self.proposal_digest),
            ("policy_digest", self.policy_digest),
        ):
            if not DIGEST_RE.fullmatch(digest):
                problems.append(f"{path}.{label} must be a sha256 digest")
        for label, digest in (
            ("outer_summary_digest", self.outer_summary_digest),
            ("rollback_plan_digest", self.rollback_plan_digest),
        ):
            if digest and not DIGEST_RE.fullmatch(digest):
                problems.append(f"{path}.{label} must be empty or a sha256 digest")
        if self.decision not in PROMOTION_DECISIONS:
            problems.append(f"{path}.decision must be one of {', '.join(PROMOTION_DECISIONS)}")
        if (
            not self.approver_ids
            or len(self.approver_ids) != len(set(self.approver_ids))
            or any(not ID_RE.fullmatch(value) for value in self.approver_ids)
        ):
            problems.append(f"{path}.approver_ids must contain named human authorities")
        if (
            not self.evidence_digests
            or len(self.evidence_digests) != len(set(self.evidence_digests))
            or any(not DIGEST_RE.fullmatch(value) for value in self.evidence_digests)
        ):
            problems.append(f"{path}.evidence_digests must contain unique sha256 digests")
        if not self.human_authority:
            problems.append(f"{path}.human_authority must be true")
        if self.decision == "approve" and not self.rollback_plan_digest:
            problems.append(f"{path}: approval requires a rollback plan digest")
        problems.extend(_extension_problems(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "harness_bundle_digest": self.harness_bundle_digest,
            "proposal_digest": self.proposal_digest,
            "policy_digest": self.policy_digest,
            "decision": self.decision,
            "approver_ids": list(self.approver_ids),
            "evidence_digests": list(self.evidence_digests),
            "outer_summary_digest": self.outer_summary_digest,
            "rollback_plan_digest": self.rollback_plan_digest,
            "human_authority": self.human_authority,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class HarnessEvidenceBundle:
    """Exact closure over development judgments, promotion, and sealed aggregates."""

    id: str
    version: str
    harness_bundle_digest: str
    atomic_judgments: tuple[AtomicJudgment, ...]
    panels: tuple[JudgePanelReceipt, ...]
    failure_clusters: tuple[FailureCluster, ...]
    promotion_decisions: tuple[HarnessPromotionDecision, ...]
    outer_summaries: tuple[SanitizedOuterSummary, ...]
    component_receipt_digests: tuple[str, ...]
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self, path: str = "harness_evidence") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or "." not in self.id:
            problems.append(f"{path}.id must be a namespaced identifier")
        if not self.version.strip():
            problems.append(f"{path}.version must not be empty")
        if not DIGEST_RE.fullmatch(self.harness_bundle_digest):
            problems.append(f"{path}.harness_bundle_digest must be a sha256 digest")
        collections = (
            ("atomic_judgments", self.atomic_judgments),
            ("panels", self.panels),
            ("failure_clusters", self.failure_clusters),
            ("promotion_decisions", self.promotion_decisions),
            ("outer_summaries", self.outer_summaries),
        )
        all_ids: list[str] = []
        for label, values in collections:
            for index, value in enumerate(values):
                problems.extend(value.validate(f"{path}.{label}[{index}]"))
                all_ids.append(value.id)
        if len(all_ids) != len(set(all_ids)):
            problems.append(f"{path} evidence ids must be globally unique")
        judgment_by_id = {value.id: value for value in self.atomic_judgments}
        for index, panel in enumerate(self.panels):
            unknown = sorted(set(panel.member_judgment_ids) - set(judgment_by_id))
            if unknown:
                problems.append(
                    f"{path}.panels[{index}] references unknown judgments: {', '.join(unknown)}"
                )
            elif any(
                judgment_by_id[judgment_id].case_id != panel.case_id
                for judgment_id in panel.member_judgment_ids
            ):
                problems.append(f"{path}.panels[{index}] judgments must share its case id")
            if (
                panel.tie_breaker_judgment_id
                and panel.tie_breaker_judgment_id not in judgment_by_id
            ):
                problems.append(f"{path}.panels[{index}] tie breaker must reference a judgment")
        for index, cluster in enumerate(self.failure_clusters):
            unknown = sorted(set(cluster.member_judgment_ids) - set(judgment_by_id))
            if unknown:
                problems.append(
                    f"{path}.failure_clusters[{index}] references unknown judgments: "
                    + ", ".join(unknown)
                )
        outer_by_digest = {summary.digest: summary for summary in self.outer_summaries}
        for index, summary in enumerate(self.outer_summaries):
            if summary.harness_bundle_digest != self.harness_bundle_digest:
                problems.append(
                    f"{path}.outer_summaries[{index}] must reference this harness bundle"
                )
        for index, decision in enumerate(self.promotion_decisions):
            if decision.harness_bundle_digest != self.harness_bundle_digest:
                problems.append(
                    f"{path}.promotion_decisions[{index}] must reference this harness bundle"
                )
            if (
                decision.outer_summary_digest
                and decision.outer_summary_digest not in outer_by_digest
            ):
                problems.append(
                    f"{path}.promotion_decisions[{index}] references an unknown outer summary"
                )
        if (
            not self.component_receipt_digests
            or len(self.component_receipt_digests) != len(set(self.component_receipt_digests))
            or any(not DIGEST_RE.fullmatch(value) for value in self.component_receipt_digests)
        ):
            problems.append(f"{path}.component_receipt_digests must contain unique sha256 digests")
        problems.extend(_extension_problems(self.extensions, f"{path}.extensions"))
        return problems

    def assert_valid(self) -> HarnessEvidenceBundle:
        problems = self.validate()
        if problems:
            raise ValueError("invalid harness evidence bundle: " + "; ".join(problems))
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "harness_evidence_model_version": HARNESS_EVIDENCE_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "harness_bundle_digest": self.harness_bundle_digest,
            "atomic_judgments": [value.to_dict() for value in self.atomic_judgments],
            "panels": [value.to_dict() for value in self.panels],
            "failure_clusters": [value.to_dict() for value in self.failure_clusters],
            "promotion_decisions": [value.to_dict() for value in self.promotion_decisions],
            "outer_summaries": [value.to_dict() for value in self.outer_summaries],
            "component_receipt_digests": list(self.component_receipt_digests),
            "extensions": dict(self.extensions),
        }


__all__ = [
    "CANDIDATE_VISIBILITIES",
    "FAILURE_SEVERITIES",
    "FLOW_EXPOSURES",
    "HARNESS_EVIDENCE_MODEL_VERSION",
    "HARNESS_MODEL_VERSION",
    "JUDGMENT_VERDICTS",
    "PANEL_DISPOSITIONS",
    "PROMOTION_DECISIONS",
    "AtomicJudgment",
    "FailureCluster",
    "HarnessBundle",
    "HarnessEvidenceBundle",
    "HarnessFlow",
    "HarnessGraph",
    "HarnessPromotionDecision",
    "JudgePanelReceipt",
    "SanitizedOuterSummary",
]
