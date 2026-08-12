"""Linked graph and feedback-firewall contracts for evaluation harnesses.

An evaluation harness is not one oversized executable DAG.  It is a bundle of
ordinary, independently compiled graphs with explicit authority and data-flow
boundaries.  The records in this module describe that bundle; they do not
execute graphs, isolate candidate code, or approve their own proposals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from solutiongraph.campaign import EvaluationBoundary
from solutiongraph.model import DIGEST_RE, ID_RE, canonical_json, sha256_digest

HARNESS_MODEL_VERSION = "0.1"
FLOW_EXPOSURES = ("full", "aggregate", "digest", "deny")
CANDIDATE_VISIBILITIES = (
    "none",
    "inputs-only",
    "outputs-only",
    "development",
    "aggregate-only",
)


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


__all__ = [
    "CANDIDATE_VISIBILITIES",
    "FLOW_EXPOSURES",
    "HARNESS_MODEL_VERSION",
    "HarnessBundle",
    "HarnessFlow",
    "HarnessGraph",
]
