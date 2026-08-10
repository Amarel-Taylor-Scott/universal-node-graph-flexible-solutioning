"""Immutable run evidence, experiment design, Pareto ranking, and prior learning."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from math import isfinite, log, sqrt
from statistics import fmean, pvariance
from typing import Any

from solutiongraph.model import DIGEST_RE, ID_RE, PORT_RE
from solutiongraph.search import BeliefModel, CandidateWeight, InteractionWeight

RUN_OUTCOMES = ("accepted", "rejected", "failed", "completed_unverified")
NODE_RUN_OUTCOMES = ("succeeded", "failed", "blocked")


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return isfinite(value)
    except OverflowError:
        return False


def _metric_problems(metrics: Mapping[str, float], path: str) -> list[str]:
    problems: list[str] = []
    for name, value in metrics.items():
        if not isinstance(name, str) or not name.strip():
            problems.append(f"{path} metric names must be nonempty strings")
        if not _is_finite_number(value):
            problems.append(f"{path}.{name} must be a finite number")
    return problems


@dataclass(frozen=True)
class Objective:
    metric: str
    direction: str
    weight: float = 1.0
    hard_minimum: float | None = None
    hard_maximum: float | None = None

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not isinstance(self.metric, str) or not self.metric.strip():
            problems.append("objective metric must not be empty")
        if self.direction not in ("maximize", "minimize"):
            problems.append("objective direction must be maximize or minimize")
        if not _is_finite_number(self.weight) or self.weight < 0:
            problems.append("objective weight must be finite and non-negative")
        for label, value in (
            ("hard_minimum", self.hard_minimum),
            ("hard_maximum", self.hard_maximum),
        ):
            if value is not None and not _is_finite_number(value):
                problems.append(f"objective {label} must be null or finite")
        if (
            _is_finite_number(self.hard_minimum)
            and _is_finite_number(self.hard_maximum)
            and self.hard_minimum > self.hard_maximum
        ):
            problems.append("objective hard_minimum exceeds hard_maximum")
        return problems


@dataclass(frozen=True)
class NodeRunReceipt:
    slot_id: str
    candidate_id: str
    outcome: str
    started_at: str = ""
    completed_at: str = ""
    metrics: Mapping[str, float] = field(default_factory=dict)
    failure_class: str = ""
    artifact_digests: tuple[str, ...] = ()
    attempt: int = 1
    node_id: str = ""
    implementation_digest: str = ""
    runtime: str = ""
    runtime_adapter: str = ""
    isolation: str = ""
    input_digest: str = ""

    def validate(self, path: str = "node_receipt") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.slot_id) or not ID_RE.fullmatch(self.candidate_id):
            problems.append(f"{path} slot_id and candidate_id must be identifiers")
        if self.node_id and not ID_RE.fullmatch(self.node_id):
            problems.append(f"{path}.node_id must be empty or an identifier")
        if self.runtime_adapter and not ID_RE.fullmatch(self.runtime_adapter):
            problems.append(f"{path}.runtime_adapter must be empty or an identifier")
        if self.isolation and (
            not isinstance(self.isolation, str) or not self.isolation.strip()
        ):
            problems.append(f"{path}.isolation must be empty or a nonempty string")
        if self.outcome not in NODE_RUN_OUTCOMES:
            problems.append(f"{path}.outcome must be one of {', '.join(NODE_RUN_OUTCOMES)}")
        if (
            isinstance(self.attempt, bool)
            or not isinstance(self.attempt, int)
            or self.attempt <= 0
        ):
            problems.append(f"{path}.attempt must be positive")
        if self.failure_class and not ID_RE.fullmatch(self.failure_class):
            problems.append(f"{path}.failure_class must be empty or an identifier")
        problems.extend(_metric_problems(self.metrics, f"{path}.metrics"))
        for digest in (
            self.implementation_digest,
            self.input_digest,
            *self.artifact_digests,
        ):
            if digest and not DIGEST_RE.fullmatch(digest):
                problems.append(f"{path} digests must be sha256 digests")
        return problems

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> NodeRunReceipt:
        required = {
            "slot_id", "candidate_id", "outcome", "started_at", "completed_at",
            "metrics", "failure_class", "artifact_digests", "attempt", "node_id",
            "implementation_digest", "runtime", "input_digest",
        }
        optional = {"runtime_adapter", "isolation"}
        keys = set(payload)
        if required - keys or keys - required - optional:
            raise ValueError("node receipt has missing or unknown fields")
        receipt = cls(
            slot_id=payload["slot_id"],
            candidate_id=payload["candidate_id"],
            outcome=payload["outcome"],
            started_at=payload["started_at"],
            completed_at=payload["completed_at"],
            metrics=dict(payload["metrics"]),
            failure_class=payload["failure_class"],
            artifact_digests=tuple(payload["artifact_digests"]),
            attempt=payload["attempt"],
            node_id=payload["node_id"],
            implementation_digest=payload["implementation_digest"],
            runtime=payload["runtime"],
            runtime_adapter=payload.get("runtime_adapter", ""),
            isolation=payload.get("isolation", ""),
            input_digest=payload["input_digest"],
        )
        problems = receipt.validate()
        if problems:
            raise ValueError("invalid node receipt: " + "; ".join(problems))
        return receipt


@dataclass(frozen=True)
class RunReceipt:
    """Append-only evidence for one frozen plan on one task case and seed."""

    id: str
    plan_digest: str
    program_digest: str
    task_case_id: str
    outcome: str
    accepted: bool | None
    verifier: str
    assignments: tuple[tuple[str, str], ...]
    verifier_digest: str = ""
    metrics: Mapping[str, float] = field(default_factory=dict)
    node_receipts: tuple[NodeRunReceipt, ...] = ()
    seed: int | None = None
    started_at: str = ""
    completed_at: str = ""
    failure_class: str = ""
    executor: str = ""
    environment_digest: str = ""
    input_digest: str = ""
    belief_revision: str = ""
    admitted_space_digest: str = ""
    output_artifacts: tuple[tuple[str, str], ...] = ()
    verification_details: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append("receipt id must be a lowercase namespaced identifier")
        for label, digest in (
            ("plan_digest", self.plan_digest),
            ("program_digest", self.program_digest),
            ("environment_digest", self.environment_digest),
            ("input_digest", self.input_digest),
            ("admitted_space_digest", self.admitted_space_digest),
            ("verifier_digest", self.verifier_digest),
        ):
            if digest and not DIGEST_RE.fullmatch(digest):
                problems.append(f"{label} must be sha256:<64 lowercase hex chars>")
        if not self.plan_digest or not self.program_digest:
            problems.append("plan_digest and program_digest are required")
        if not ID_RE.fullmatch(self.task_case_id):
            problems.append("task_case_id must be a lowercase namespaced identifier")
        if self.outcome not in RUN_OUTCOMES:
            problems.append(f"outcome must be one of {', '.join(RUN_OUTCOMES)}")
        expected_acceptance = {
            "accepted": True,
            "rejected": False,
            "failed": False,
            "completed_unverified": None,
        }.get(self.outcome)
        if self.outcome in RUN_OUTCOMES and self.accepted is not expected_acceptance:
            problems.append("accepted value is inconsistent with outcome")
        if self.verifier and not ID_RE.fullmatch(self.verifier):
            problems.append("verifier must be empty or a lowercase namespaced identifier")
        slots = [slot for slot, _ in self.assignments]
        if len(slots) != len(set(slots)):
            problems.append("assignments must contain one candidate per slot")
        if any(
            not ID_RE.fullmatch(slot) or not ID_RE.fullmatch(candidate)
            for slot, candidate in self.assignments
        ):
            problems.append("assignment slots and candidates must be identifiers")
        if self.accepted is not None and not isinstance(self.accepted, bool):
            problems.append("accepted must be boolean or null")
        if self.failure_class and not ID_RE.fullmatch(self.failure_class):
            problems.append("failure_class must be empty or an identifier")
        problems.extend(_metric_problems(self.metrics, "metrics"))
        output_names = [name for name, _ in self.output_artifacts]
        if len(output_names) != len(set(output_names)):
            problems.append("output_artifacts must contain unique graph output names")
        for name, digest in self.output_artifacts:
            if not PORT_RE.fullmatch(name):
                problems.append("output artifact names must be snake_case")
            if not DIGEST_RE.fullmatch(digest):
                problems.append("output artifact digests must be sha256 digests")
        for index, node_receipt in enumerate(self.node_receipts):
            problems.extend(node_receipt.validate(f"node_receipts[{index}]"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "plan_digest": self.plan_digest,
            "program_digest": self.program_digest,
            "task_case_id": self.task_case_id,
            "outcome": self.outcome,
            "accepted": self.accepted,
            "verifier": self.verifier,
            "verifier_digest": self.verifier_digest,
            "assignments": dict(self.assignments),
            "metrics": dict(self.metrics),
            "node_receipts": [
                {
                    "slot_id": item.slot_id,
                    "candidate_id": item.candidate_id,
                    "outcome": item.outcome,
                    "started_at": item.started_at,
                    "completed_at": item.completed_at,
                    "metrics": dict(item.metrics),
                    "failure_class": item.failure_class,
                    "artifact_digests": list(item.artifact_digests),
                    "attempt": item.attempt,
                    "node_id": item.node_id,
                    "implementation_digest": item.implementation_digest,
                    "runtime": item.runtime,
                    "runtime_adapter": item.runtime_adapter,
                    "isolation": item.isolation,
                    "input_digest": item.input_digest,
                }
                for item in self.node_receipts
            ],
            "seed": self.seed,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "failure_class": self.failure_class,
            "executor": self.executor,
            "environment_digest": self.environment_digest,
            "input_digest": self.input_digest,
            "belief_revision": self.belief_revision,
            "admitted_space_digest": self.admitted_space_digest,
            "output_artifacts": dict(self.output_artifacts),
            "verification_details": dict(self.verification_details),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RunReceipt:
        required = {
            "id", "plan_digest", "program_digest", "task_case_id", "outcome",
            "accepted", "verifier", "verifier_digest", "assignments", "metrics",
            "node_receipts", "seed", "started_at", "completed_at", "failure_class",
            "executor", "environment_digest", "input_digest", "belief_revision",
            "admitted_space_digest", "output_artifacts", "verification_details",
        }
        if set(payload) != required:
            raise ValueError("run receipt has missing or unknown fields")
        assignments = payload["assignments"]
        output_artifacts = payload["output_artifacts"]
        node_receipts = payload["node_receipts"]
        if (
            not isinstance(assignments, Mapping)
            or not isinstance(output_artifacts, Mapping)
            or not isinstance(node_receipts, list)
        ):
            raise ValueError("run receipt mappings or node receipts are malformed")
        receipt = cls(
            id=payload["id"],
            plan_digest=payload["plan_digest"],
            program_digest=payload["program_digest"],
            task_case_id=payload["task_case_id"],
            outcome=payload["outcome"],
            accepted=payload["accepted"],
            verifier=payload["verifier"],
            assignments=tuple(sorted(assignments.items())),
            verifier_digest=payload["verifier_digest"],
            metrics=dict(payload["metrics"]),
            node_receipts=tuple(NodeRunReceipt.from_dict(item) for item in node_receipts),
            seed=payload["seed"],
            started_at=payload["started_at"],
            completed_at=payload["completed_at"],
            failure_class=payload["failure_class"],
            executor=payload["executor"],
            environment_digest=payload["environment_digest"],
            input_digest=payload["input_digest"],
            belief_revision=payload["belief_revision"],
            admitted_space_digest=payload["admitted_space_digest"],
            output_artifacts=tuple(sorted(output_artifacts.items())),
            verification_details=dict(payload["verification_details"]),
        )
        problems = receipt.validate()
        if problems:
            raise ValueError("invalid run receipt: " + "; ".join(problems))
        return receipt


@dataclass(frozen=True)
class ExperimentDesign:
    """A reproducible benchmark allocation, separate from the routes themselves."""

    id: str
    task_case_ids: tuple[str, ...]
    plan_digests: tuple[str, ...]
    seeds: tuple[int, ...]
    repetitions: int
    objectives: tuple[Objective, ...]
    control_plan_digest: str = ""
    holdout_case_ids: tuple[str, ...] = ()

    @property
    def scheduled_runs(self) -> int:
        return (
            len(self.task_case_ids)
            * len(self.plan_digests)
            * len(self.seeds)
            * self.repetitions
        )

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append("experiment id must be a lowercase namespaced identifier")
        if not self.task_case_ids or not self.plan_digests or not self.seeds:
            problems.append("task cases, plans, and seeds must not be empty")
        for label, values in (
            ("task_case_ids", self.task_case_ids),
            ("plan_digests", self.plan_digests),
            ("seeds", self.seeds),
            ("holdout_case_ids", self.holdout_case_ids),
        ):
            if len(values) != len(set(values)):
                problems.append(f"{label} must be unique")
        if any(not ID_RE.fullmatch(case_id) for case_id in self.task_case_ids):
            problems.append("task case ids must be lowercase namespaced identifiers")
        if any(not DIGEST_RE.fullmatch(digest) for digest in self.plan_digests):
            problems.append("plan digests must be sha256 digests")
        if any(isinstance(seed, bool) or not isinstance(seed, int) for seed in self.seeds):
            problems.append("seeds must be integers")
        if (
            isinstance(self.repetitions, bool)
            or not isinstance(self.repetitions, int)
            or self.repetitions <= 0
        ):
            problems.append("repetitions must be positive")
        if self.control_plan_digest and self.control_plan_digest not in self.plan_digests:
            problems.append("control plan must be in plan_digests")
        if set(self.holdout_case_ids) - set(self.task_case_ids):
            problems.append("holdout cases must be a subset of task cases")
        if not self.objectives:
            problems.append("objectives must not be empty")
        objective_metrics = [objective.metric for objective in self.objectives]
        if len(objective_metrics) != len(set(objective_metrics)):
            problems.append("objective metrics must be unique")
        for objective in self.objectives:
            problems.extend(objective.validate())
        return problems


@dataclass(frozen=True)
class RouteAggregate:
    plan_digest: str
    runs: int
    accepted_runs: int
    acceptance_rate: float
    metric_means: Mapping[str, float]
    metric_variances: Mapping[str, float]
    failure_classes: Mapping[str, int]


@dataclass(frozen=True)
class EvidenceLedger:
    """An immutable ledger; append returns a new value and never rewrites history."""

    receipts: tuple[RunReceipt, ...] = ()

    def append(self, *receipts: RunReceipt) -> EvidenceLedger:
        problems = [problem for receipt in receipts for problem in receipt.validate()]
        existing = {receipt.id for receipt in self.receipts}
        incoming = [receipt.id for receipt in receipts]
        if len(incoming) != len(set(incoming)) or existing.intersection(incoming):
            problems.append("receipt ids must be globally unique")
        if problems:
            raise ValueError("invalid evidence: " + "; ".join(problems))
        return EvidenceLedger(self.receipts + tuple(receipts))

    def aggregates(self) -> tuple[RouteAggregate, ...]:
        grouped: dict[str, list[RunReceipt]] = {}
        for receipt in self.receipts:
            grouped.setdefault(receipt.plan_digest, []).append(receipt)
        aggregates: list[RouteAggregate] = []
        for plan_digest, receipts in sorted(grouped.items()):
            metric_names = sorted({name for receipt in receipts for name in receipt.metrics})
            means: dict[str, float] = {}
            variances: dict[str, float] = {}
            for metric in metric_names:
                values = [float(receipt.metrics[metric]) for receipt in receipts
                          if metric in receipt.metrics]
                means[metric] = fmean(values)
                variances[metric] = pvariance(values) if len(values) > 1 else 0.0
            failures: dict[str, int] = {}
            for receipt in receipts:
                if receipt.failure_class:
                    failures[receipt.failure_class] = failures.get(receipt.failure_class, 0) + 1
            accepted = sum(receipt.accepted is True for receipt in receipts)
            aggregates.append(RouteAggregate(
                plan_digest=plan_digest,
                runs=len(receipts),
                accepted_runs=accepted,
                acceptance_rate=accepted / len(receipts),
                metric_means=means,
                metric_variances=variances,
                failure_classes=failures,
            ))
        return tuple(aggregates)


def pareto_front(
    aggregates: Iterable[RouteAggregate], objectives: tuple[Objective, ...]
) -> tuple[RouteAggregate, ...]:
    """Return nondominated routes after applying hard objective constraints."""
    candidates = [item for item in aggregates if _meets_constraints(item, objectives)]

    def dominates(left: RouteAggregate, right: RouteAggregate) -> bool:
        weakly_better = True
        strictly_better = False
        for objective in objectives:
            left_value = left.metric_means.get(objective.metric)
            right_value = right.metric_means.get(objective.metric)
            if left_value is None or right_value is None:
                return False
            if objective.direction == "maximize":
                weakly_better &= left_value >= right_value
                strictly_better |= left_value > right_value
            else:
                weakly_better &= left_value <= right_value
                strictly_better |= left_value < right_value
        return weakly_better and strictly_better

    return tuple(
        item for item in candidates
        if not any(other is not item and dominates(other, item) for other in candidates)
    )


def _meets_constraints(item: RouteAggregate, objectives: tuple[Objective, ...]) -> bool:
    for objective in objectives:
        value = item.metric_means.get(objective.metric)
        if value is None:
            return False
        if objective.hard_minimum is not None and value < objective.hard_minimum:
            return False
        if objective.hard_maximum is not None and value > objective.hard_maximum:
            return False
    return True


def learn_observational_beliefs(
    receipts: Iterable[RunReceipt],
    *,
    revision: str,
    interactions: tuple[tuple[str, str], ...] = (),
    alpha: float = 1.0,
    beta: float = 1.0,
) -> BeliefModel:
    """Fit smoothed success priors; these are correlations, not causal effects."""
    if alpha <= 0 or beta <= 0:
        raise ValueError("alpha and beta must be positive")
    receipts = tuple(receipt for receipt in receipts if receipt.accepted is not None)
    counts: dict[tuple[str, str], list[int]] = {}
    pair_counts: dict[tuple[str, str, str, str], list[int]] = {}
    for receipt in receipts:
        assignment = dict(receipt.assignments)
        success = int(receipt.accepted is True)
        for item in assignment.items():
            bucket = counts.setdefault(item, [0, 0])
            bucket[0] += success
            bucket[1] += 1
        for left_slot, right_slot in interactions:
            if left_slot not in assignment or right_slot not in assignment:
                continue
            key = (left_slot, assignment[left_slot], right_slot, assignment[right_slot])
            bucket = pair_counts.setdefault(key, [0, 0])
            bucket[0] += success
            bucket[1] += 1

    candidate_weights: list[CandidateWeight] = []
    for (slot_id, candidate_id), (successes, total) in sorted(counts.items()):
        posterior_total = total + alpha + beta
        probability = (successes + alpha) / posterior_total
        uncertainty = sqrt(probability * (1 - probability) / (posterior_total + 1))
        candidate_weights.append(CandidateWeight(
            slot_id=slot_id,
            candidate_id=candidate_id,
            log_weight=log(probability),
            evidence_count=total,
            uncertainty=uncertainty,
        ))
    interaction_weights: list[InteractionWeight] = []
    for key, (successes, total) in sorted(pair_counts.items()):
        probability = (successes + alpha) / (total + alpha + beta)
        interaction_weights.append(InteractionWeight(
            left_slot=key[0],
            left_candidate=key[1],
            right_slot=key[2],
            right_candidate=key[3],
            log_weight=log(probability),
            evidence_count=total,
        ))
    return BeliefModel(
        revision=revision,
        candidate_weights=tuple(candidate_weights),
        interaction_weights=tuple(interaction_weights),
    )
