"""Executable release verification for the bundled SolutionGraph skeleton.

``doctor`` proves that definitions are structurally valid.  This module goes
further: it compiles every bundled route, executes every route through the
reference runtime, checks its declared oracle outcome, and can compare the
generated catalogue byte-for-meaning with the checked-in JSON projection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from solutiongraph.benchmark_library import REFERENCE_BENCHMARKS
from solutiongraph.catalog import catalog_documents
from solutiongraph.conformance import ConformanceResult, run_conformance_suite
from solutiongraph.examples import all_examples, run_example
from solutiongraph.reference_nodes import (
    REFERENCE_DESCRIPTORS,
    REFERENCE_NODE_SPECS,
)
from solutiongraph.schemas import load_all_schemas
from solutiongraph.specialized import (
    REFERENCE_SPECIALIZED_PACK_REGISTRY,
    REFERENCE_SPECIALIZED_PACKS,
    validate_specialized_pack_catalog,
)
from solutiongraph.stdlib_pack import (
    STANDARD_LIBRARY_DESCRIPTORS,
    STANDARD_LIBRARY_NODE_SPECS,
)
from solutiongraph.template_library import REFERENCE_TEMPLATES


@dataclass(frozen=True)
class RouteVerification:
    """Observed outcome for one declared example route."""

    example_id: str
    route_id: str
    plan_digest: str
    expected_accepted: bool
    accepted: bool | None
    outcome: str
    node_attempts: int
    artifact_count: int

    @property
    def ok(self) -> bool:
        return (
            self.accepted is self.expected_accepted
            and self.outcome
            == ("accepted" if self.expected_accepted else "rejected")
            and self.node_attempts > 0
            and self.artifact_count > 0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "example_id": self.example_id,
            "route_id": self.route_id,
            "plan_digest": self.plan_digest,
            "expected_accepted": self.expected_accepted,
            "accepted": self.accepted,
            "outcome": self.outcome,
            "node_attempts": self.node_attempts,
            "artifact_count": self.artifact_count,
            "ok": self.ok,
        }


@dataclass(frozen=True)
class ReleaseVerification:
    """Complete, machine-readable release-gate result."""

    route_results: tuple[RouteVerification, ...]
    problems: tuple[str, ...]
    template_count: int
    atomic_slot_count: int
    executable_node_count: int
    schema_count: int
    catalog_document_count: int
    catalog_checked: bool
    conformance: ConformanceResult
    benchmark_count: int
    solution_pack_count: int
    specialized_pack_count: int

    @property
    def ok(self) -> bool:
        return (
            not self.problems
            and self.conformance.ok
            and all(item.ok for item in self.route_results)
        )

    @property
    def accepted_routes(self) -> int:
        return sum(item.accepted is True for item in self.route_results)

    @property
    def rejected_controls(self) -> int:
        return sum(item.accepted is False for item in self.route_results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "problems": list(self.problems),
            "template_count": self.template_count,
            "atomic_slot_count": self.atomic_slot_count,
            "executable_node_count": self.executable_node_count,
            "schema_count": self.schema_count,
            "catalog_document_count": self.catalog_document_count,
            "catalog_checked": self.catalog_checked,
            "benchmark_count": self.benchmark_count,
            "solution_pack_count": self.solution_pack_count,
            "specialized_pack_count": self.specialized_pack_count,
            "conformance": self.conformance.to_dict(),
            "example_count": len(all_examples()),
            "route_count": len(self.route_results),
            "accepted_routes": self.accepted_routes,
            "rejected_controls": self.rejected_controls,
            "routes": [item.to_dict() for item in self.route_results],
        }


def _catalog_problems(root: Path, expected: dict[str, dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    if not root.is_dir():
        return [f"catalog root does not exist: {root}"]

    actual_paths = {
        path.relative_to(root).as_posix() for path in root.rglob("*.json")
    }
    expected_paths = set(expected)
    for path in sorted(expected_paths - actual_paths):
        problems.append(f"catalog document is missing: {path}")
    for path in sorted(actual_paths - expected_paths):
        problems.append(f"catalog contains an unexpected JSON document: {path}")
    for relative in sorted(expected_paths & actual_paths):
        try:
            actual = json.loads((root / relative).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            problems.append(f"catalog document cannot be read: {relative}: {exc}")
            continue
        if actual != expected[relative]:
            problems.append(f"catalog document is stale: {relative}")
    return problems


def verify_reference_release(
    *,
    catalog_root: str | Path | None = None,
    runtime: str = "in-process",
) -> ReleaseVerification:
    """Compile and execute every bundled route and return all gate failures."""
    problems = list(REFERENCE_TEMPLATES.validate())
    problems.extend(validate_specialized_pack_catalog(REFERENCE_SPECIALIZED_PACK_REGISTRY))
    conformance = run_conformance_suite()
    problems.extend(
        f"advanced conformance failed: {check.id}: {check.details}"
        for check in conformance.checks
        if not check.passed
    )
    node_by_id = {node.id: node for node in REFERENCE_NODE_SPECS}
    for node in REFERENCE_NODE_SPECS:
        problems.extend(node.validate(f"nodes.{node.id}"))
    for descriptor in REFERENCE_DESCRIPTORS:
        problems.extend(
            descriptor.validate(
                node_by_id.get(descriptor.node_id),
                f"descriptors.{descriptor.node_id}",
            )
        )
    stdlib_by_id = {node.id: node for node in STANDARD_LIBRARY_NODE_SPECS}
    for descriptor in STANDARD_LIBRARY_DESCRIPTORS:
        problems.extend(
            descriptor.validate(
                stdlib_by_id.get(descriptor.node_id),
                f"stdlib_descriptors.{descriptor.node_id}",
            )
        )
    for bundle in REFERENCE_BENCHMARKS:
        problems.extend(
            f"{bundle.id}: {problem}" for problem in bundle.validate()
        )

    executable_nodes = {
        node.id: node
        for example in all_examples()
        for node in example.registry.nodes
    }
    for node in executable_nodes.values():
        problems.extend(node.validate(f"example_nodes.{node.id}"))

    schemas = load_all_schemas()
    documents = catalog_documents()
    if catalog_root is not None:
        problems.extend(_catalog_problems(Path(catalog_root), documents))

    route_results: list[RouteVerification] = []
    for example in all_examples():
        try:
            space, plans = example.compile()
            if len(plans) != len(example.routes):
                problems.append(f"{example.id}: not every declared route compiled")
                continue
            if any(not space.choices_for(slot.id) for slot in example.program.slots):
                problems.append(f"{example.id}: at least one slot has no admitted candidate")
                continue
            report = run_example(example.id, route="all", runtime=runtime)
        except Exception as exc:  # the release gate must report, not hide, crashes
            problems.append(
                f"{example.id}: compile or execution crashed: "
                f"{type(exc).__name__}: {exc}"
            )
            continue

        experiment = report["experiment"]
        if experiment["scheduled_runs"] != len(example.routes):
            problems.append(f"{example.id}: scheduled run count does not match routes")
        if experiment["completed_runs"] != len(example.routes):
            problems.append(f"{example.id}: completed run count does not match routes")
        if not experiment["pareto_plan_digests"]:
            problems.append(f"{example.id}: experiment produced an empty Pareto frontier")

        receipts = {
            receipt["plan_digest"]: receipt for receipt in experiment["receipts"]
        }
        for route in example.routes:
            plan = plans[route.id]
            receipt = receipts.get(plan.digest)
            if receipt is None:
                problems.append(f"{example.id}/{route.id}: execution receipt is missing")
                continue
            result = RouteVerification(
                example_id=example.id,
                route_id=route.id,
                plan_digest=plan.digest,
                expected_accepted=route.expected_accepted,
                accepted=receipt["accepted"],
                outcome=receipt["outcome"],
                node_attempts=len(receipt["node_receipts"]),
                artifact_count=len(receipt["output_artifacts"]),
            )
            route_results.append(result)
            if not result.ok:
                problems.append(
                    f"{example.id}/{route.id}: expected "
                    f"{'accepted' if route.expected_accepted else 'rejected'}, "
                    f"observed {result.outcome}"
                )

    return ReleaseVerification(
        route_results=tuple(route_results),
        problems=tuple(problems),
        template_count=len(REFERENCE_TEMPLATES.templates),
        atomic_slot_count=sum(
            len(template.program.slots) for template in REFERENCE_TEMPLATES.templates
        ),
        executable_node_count=len(executable_nodes),
        schema_count=len(schemas),
        catalog_document_count=len(documents),
        catalog_checked=catalog_root is not None,
        conformance=conformance,
        benchmark_count=len(REFERENCE_BENCHMARKS),
        solution_pack_count=len(REFERENCE_BENCHMARKS),
        specialized_pack_count=len(REFERENCE_SPECIALIZED_PACKS),
    )


__all__ = [
    "ReleaseVerification",
    "RouteVerification",
    "verify_reference_release",
]
