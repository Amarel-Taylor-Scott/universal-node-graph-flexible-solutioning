"""Search over alternative compiler-valid graph topologies and their node routes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from math import isfinite
from typing import Any

from solutiongraph.compiler import Compiler
from solutiongraph.model import (
    ID_RE,
    AdmittedSpace,
    FrozenPlan,
    ProgramGraph,
    Registry,
    sha256_digest,
)
from solutiongraph.search import (
    BeliefModel,
    SearchBudget,
    SearchEngine,
    SearchMode,
    SearchReport,
)

TOPOLOGY_MODEL_VERSION = "0.1"


def _external_interface(program: ProgramGraph) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    """Return endpoint-independent external port contracts for family comparison."""

    inputs = tuple(sorted(
        (item.name, item.value_type.to_dict()) for item in program.inputs
    ))
    outputs = tuple(sorted(
        (item.name, item.value_type.to_dict()) for item in program.outputs
    ))
    return inputs, outputs


@dataclass(frozen=True)
class TopologyVariant:
    """One explicit semantic DAG alternative in a topology family."""

    id: str
    title: str
    program: ProgramGraph
    rationale: str
    prior_log_weight: float = 0.0
    parent_variant_id: str = ""
    operators: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append("topology variant id must be namespaced")
        if not self.title.strip() or not self.rationale.strip():
            problems.append("topology variant title and rationale are required")
        if not isfinite(self.prior_log_weight):
            problems.append("topology prior_log_weight must be finite")
        if self.parent_variant_id and not ID_RE.fullmatch(self.parent_variant_id):
            problems.append("topology parent_variant_id must be empty or namespaced")
        for label, values in (("operators", self.operators), ("tags", self.tags)):
            if len(values) != len(set(values)):
                problems.append(f"topology {label} must be unique")
            if any(not ID_RE.fullmatch(value) for value in values):
                problems.append(f"topology {label} must contain namespaced identifiers")
        for diagnostic in Compiler().validate_program(self.program):
            problems.append(
                f"program: {diagnostic.code}: {diagnostic.message} ({diagnostic.path})"
            )
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "topology_model_version": TOPOLOGY_MODEL_VERSION,
            "id": self.id,
            "title": self.title,
            "program_id": self.program.id,
            "program_version": self.program.version,
            "program_digest": self.program.digest,
            "rationale": self.rationale,
            "prior_log_weight": self.prior_log_weight,
            "parent_variant_id": self.parent_variant_id,
            "operators": list(self.operators),
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class TopologyFamily:
    """A closed, inspectable set of alternative DAGs for the same task contract."""

    id: str
    version: str
    task: str
    success_contract: str
    variants: tuple[TopologyVariant, ...]

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not self.version.strip():
            problems.append("topology family id and version are invalid")
        if not self.task.strip() or not self.success_contract.strip():
            problems.append("topology family task and success_contract are required")
        if not self.variants:
            problems.append("topology family must contain at least one variant")
        ids = [variant.id for variant in self.variants]
        digests = [variant.program.digest for variant in self.variants]
        if len(ids) != len(set(ids)):
            problems.append("topology variant ids must be unique")
        if len(digests) != len(set(digests)):
            problems.append("topology programs must be content-distinct")
        known = set(ids)
        parents = {
            variant.id: variant.parent_variant_id
            for variant in self.variants
            if variant.parent_variant_id
        }
        reference_interface = (
            _external_interface(self.variants[0].program)
            if self.variants
            else None
        )
        for index, variant in enumerate(self.variants):
            problems.extend(
                f"variants[{index}]: {problem}" for problem in variant.validate()
            )
            if variant.parent_variant_id and variant.parent_variant_id not in known:
                problems.append(
                    f"variants[{index}]: parent_variant_id is not in this family"
                )
            if variant.parent_variant_id == variant.id:
                problems.append(f"variants[{index}]: topology variant cannot parent itself")
            if variant.program.task != self.task:
                problems.append(f"variants[{index}]: program task differs from family task")
            if variant.program.success_contract != self.success_contract:
                problems.append(
                    f"variants[{index}]: program success contract differs from family"
                )
            if (
                reference_interface is not None
                and _external_interface(variant.program) != reference_interface
            ):
                problems.append(
                    f"variants[{index}]: program external inputs and outputs differ "
                    "from the topology family interface"
                )
        for variant_id in parents:
            visited: set[str] = set()
            current = variant_id
            while current in parents:
                if current in visited:
                    problems.append(
                        f"topology parent lineage contains a cycle at {current}"
                    )
                    break
                visited.add(current)
                current = parents[current]
        return problems

    def get(self, variant_id: str) -> TopologyVariant:
        try:
            return next(variant for variant in self.variants if variant.id == variant_id)
        except StopIteration as exc:
            raise ValueError(f"unknown topology variant {variant_id!r}") from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "topology_model_version": TOPOLOGY_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "task": self.task,
            "success_contract": self.success_contract,
            "variants": [variant.to_dict() for variant in self.variants],
        }


@dataclass(frozen=True)
class TopologySearchBudget:
    """Explicit global limits layered over ordinary per-DAG route search."""

    route_budget: SearchBudget = field(default_factory=SearchBudget)
    topology_limit: int | None = None
    global_evaluation_limit: int | None = None
    result_limit: int = 10

    def validate(self) -> list[str]:
        problems = self.route_budget.validate()
        if self.topology_limit is not None and self.topology_limit <= 0:
            problems.append("topology_limit must be positive or null")
        if self.global_evaluation_limit is not None and self.global_evaluation_limit <= 0:
            problems.append("global_evaluation_limit must be positive or null")
        if self.result_limit <= 0:
            problems.append("topology result_limit must be positive")
        return problems


@dataclass(frozen=True)
class TopologyProposal:
    variant_id: str
    program_digest: str
    assignments: tuple[tuple[str, str], ...]
    route_log_score: float
    topology_log_weight: float
    contributions: tuple[tuple[str, float], ...] = ()

    @property
    def log_score(self) -> float:
        return self.route_log_score + self.topology_log_weight

    @property
    def selection(self) -> dict[str, str]:
        return dict(self.assignments)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "program_digest": self.program_digest,
            "selection": dict(self.assignments),
            "route_log_score": self.route_log_score,
            "topology_log_weight": self.topology_log_weight,
            "log_score": self.log_score,
            "contributions": [
                {"factor": factor, "value": value}
                for factor, value in self.contributions
            ],
        }


@dataclass(frozen=True)
class TopologySearchReport:
    family_digest: str
    registry_digest: str
    total_topologies: int
    searched_topologies: int
    total_cartesian_routes: int
    evaluated_routes: int
    constraint_eliminated_routes: int
    heuristic_skipped_routes: int
    topology_skipped_routes: int
    unvisited_routes: int
    complete: bool
    optimality_proven: bool
    per_variant: tuple[tuple[str, SearchReport], ...]
    proposals: tuple[TopologyProposal, ...]

    @property
    def evaluation_coverage(self) -> float:
        return (
            self.evaluated_routes / self.total_cartesian_routes
            if self.total_cartesian_routes
            else 0.0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "topology_model_version": TOPOLOGY_MODEL_VERSION,
            "family_digest": self.family_digest,
            "registry_digest": self.registry_digest,
            "total_topologies": self.total_topologies,
            "searched_topologies": self.searched_topologies,
            "total_cartesian_routes": self.total_cartesian_routes,
            "evaluated_routes": self.evaluated_routes,
            "constraint_eliminated_routes": self.constraint_eliminated_routes,
            "heuristic_skipped_routes": self.heuristic_skipped_routes,
            "topology_skipped_routes": self.topology_skipped_routes,
            "unvisited_routes": self.unvisited_routes,
            "complete": self.complete,
            "optimality_proven": self.optimality_proven,
            "evaluation_coverage": self.evaluation_coverage,
            "per_variant": [
                {"variant_id": variant_id, "search": report.to_dict()}
                for variant_id, report in self.per_variant
            ],
            "proposals": [proposal.to_dict() for proposal in self.proposals],
        }


class TopologySearchEngine:
    """Admit every topology, then search explicitly selected topology spaces."""

    def __init__(
        self,
        *,
        compiler: Compiler | None = None,
        search_engine: SearchEngine | None = None,
    ) -> None:
        self.compiler = compiler or Compiler()
        self.search_engine = search_engine or SearchEngine()

    def admit_all(
        self, family: TopologyFamily, registry: Registry
    ) -> tuple[tuple[str, AdmittedSpace], ...]:
        problems = family.validate()
        if problems:
            raise ValueError("invalid topology family: " + "; ".join(problems))
        return tuple(
            (variant.id, self.compiler.admit(variant.program, registry))
            for variant in family.variants
        )

    def search(
        self,
        family: TopologyFamily,
        registry: Registry,
        *,
        budget: TopologySearchBudget | None = None,
        beliefs: Mapping[str, BeliefModel] | None = None,
    ) -> TopologySearchReport:
        budget = budget or TopologySearchBudget()
        problems = budget.validate()
        if problems:
            raise ValueError("invalid topology search budget: " + "; ".join(problems))
        beliefs = beliefs or {}
        spaces = dict(self.admit_all(family, registry))
        ordered = tuple(sorted(
            family.variants,
            key=lambda variant: (-variant.prior_log_weight, variant.id),
        ))
        searched = ordered[: budget.topology_limit] if budget.topology_limit else ordered
        skipped = ordered[len(searched):]
        reports: list[tuple[str, SearchReport]] = []
        proposals: list[TopologyProposal] = []
        remaining = budget.global_evaluation_limit

        for variant in searched:
            if remaining is not None and remaining <= 0:
                skipped = (*skipped, variant)
                continue
            route_budget = budget.route_budget
            local_limit = route_budget.evaluation_limit
            if remaining is not None:
                local_limit = remaining if local_limit is None else min(local_limit, remaining)
            if route_budget.mode == SearchMode.EXHAUSTIVE and local_limit is None:
                local_result_limit = min(
                    spaces[variant.id].route_count_upper_bound,
                    max(route_budget.result_limit, budget.result_limit),
                )
            else:
                local_result_limit = max(route_budget.result_limit, budget.result_limit)
            local_budget = replace(
                route_budget,
                evaluation_limit=local_limit,
                result_limit=local_result_limit,
            )
            report = self.search_engine.search(
                spaces[variant.id],
                beliefs.get(variant.id, BeliefModel()),
                local_budget,
            )
            reports.append((variant.id, report))
            if remaining is not None:
                remaining -= report.evaluated_routes
            for route in report.proposals:
                proposals.append(TopologyProposal(
                    variant_id=variant.id,
                    program_digest=variant.program.digest,
                    assignments=route.assignments,
                    route_log_score=route.log_score,
                    topology_log_weight=variant.prior_log_weight,
                    contributions=(
                        (f"topology:{variant.id}", variant.prior_log_weight),
                        *route.contributions,
                    ),
                ))

        proposals.sort(key=lambda item: (-item.log_score, item.variant_id, item.assignments))
        total = sum(space.route_count_upper_bound for space in spaces.values())
        evaluated = sum(report.evaluated_routes for _, report in reports)
        constrained = sum(report.constraint_eliminated_routes for _, report in reports)
        heuristic = sum(report.heuristic_skipped_routes for _, report in reports)
        searched_ids = {variant_id for variant_id, _ in reports}
        skipped_routes = sum(
            spaces[variant.id].route_count_upper_bound
            for variant in family.variants
            if variant.id not in searched_ids
        )
        accounted = evaluated + constrained + heuristic + skipped_routes
        complete = (
            len(reports) == len(family.variants)
            and all(report.complete for _, report in reports)
        )
        return TopologySearchReport(
            family_digest=family.digest,
            registry_digest=registry.digest,
            total_topologies=len(family.variants),
            searched_topologies=len(reports),
            total_cartesian_routes=total,
            evaluated_routes=evaluated,
            constraint_eliminated_routes=constrained,
            heuristic_skipped_routes=heuristic,
            topology_skipped_routes=skipped_routes,
            unvisited_routes=max(0, total - accounted),
            complete=complete,
            optimality_proven=complete,
            per_variant=tuple(reports),
            proposals=tuple(proposals[: budget.result_limit]),
        )

    def compile(
        self,
        family: TopologyFamily,
        registry: Registry,
        proposal: TopologyProposal,
    ) -> FrozenPlan:
        variant = family.get(proposal.variant_id)
        if variant.program.digest != proposal.program_digest:
            raise ValueError("topology proposal program digest does not match its variant")
        space = self.compiler.admit(variant.program, registry)
        return self.compiler.compile(
            variant.program, registry, space, proposal.selection
        )


__all__ = [
    "TOPOLOGY_MODEL_VERSION",
    "TopologyFamily",
    "TopologyProposal",
    "TopologySearchBudget",
    "TopologySearchEngine",
    "TopologySearchReport",
    "TopologyVariant",
]
