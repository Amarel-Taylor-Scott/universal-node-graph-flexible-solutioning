"""Evidence-derived capability coverage over exact checked-in repository assets."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from solutiongraph.model import sha256_digest
from solutiongraph.universal.catalog import REFERENCE_DOMAIN_PACKS
from solutiongraph.universal.model import (
    COVERAGE_STATUSES,
    CapabilityAssessment,
    CapabilityRequirement,
    DomainCoverageAssessment,
    DomainPack,
    UniversalCoverageReport,
)


@dataclass(frozen=True)
class RepositoryAssetInventory:
    """Closed-world evidence boundary used to derive the reference dashboard."""

    template_ids: tuple[str, ...]
    example_route_counts: tuple[tuple[str, int], ...]
    benchmark_ids: tuple[str, ...]
    agent_benchmark_ids: tuple[str, ...]
    question_pack_ids: tuple[str, ...]
    adapter_ids: tuple[str, ...]
    operational_evidence_refs: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(
            {
                "templates": self.template_ids,
                "examples": dict(self.example_route_counts),
                "benchmarks": self.benchmark_ids,
                "agent_benchmarks": self.agent_benchmark_ids,
                "question_packs": self.question_pack_ids,
                "adapters": self.adapter_ids,
                "operational_evidence": self.operational_evidence_refs,
            }
        )


@lru_cache(maxsize=1)
def reference_asset_inventory() -> RepositoryAssetInventory:
    """Resolve exact assets and compiler-valid route counts once per process."""

    from solutiongraph.agent_bench.config import (
        command_matrix_example_suite,
        reference_agent_benchmark_suite,
    )
    from solutiongraph.benchmark_library import REFERENCE_BENCHMARKS
    from solutiongraph.examples import all_examples
    from solutiongraph.integrations import REFERENCE_INTEGRATION_ADAPTERS
    from solutiongraph.question_packs import REFERENCE_QUESTION_PACKS
    from solutiongraph.template_library import REFERENCE_TEMPLATES

    route_counts: list[tuple[str, int]] = []
    for example in all_examples():
        space, _ = example.compile()
        route_counts.append((example.id, space.route_count_upper_bound))
    suites = (reference_agent_benchmark_suite(), command_matrix_example_suite())
    return RepositoryAssetInventory(
        template_ids=tuple(sorted(item.id for item in REFERENCE_TEMPLATES.templates)),
        example_route_counts=tuple(sorted(route_counts)),
        benchmark_ids=tuple(sorted(item.id for item in REFERENCE_BENCHMARKS)),
        agent_benchmark_ids=tuple(sorted(item.id for item in suites)),
        question_pack_ids=tuple(sorted(item.id for item in REFERENCE_QUESTION_PACKS)),
        adapter_ids=tuple(sorted(item.id for item in REFERENCE_INTEGRATION_ADAPTERS)),
    )


def _assets(
    capability: CapabilityRequirement,
    inventory: RepositoryAssetInventory,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[int, ...]]:
    available = {
        "template": set(inventory.template_ids),
        "example": {key for key, _ in inventory.example_route_counts},
        "benchmark": set(inventory.benchmark_ids),
        "agent-benchmark": set(inventory.agent_benchmark_ids),
        "question-pack": set(inventory.question_pack_ids),
        "adapter": set(inventory.adapter_ids),
        "operational": set(inventory.operational_evidence_refs),
    }
    requested = (
        *(("template", item) for item in capability.template_ids),
        *(("example", item) for item in capability.example_ids),
        *(("benchmark", item) for item in capability.benchmark_ids),
        *(("agent-benchmark", item) for item in capability.agent_benchmark_ids),
        *(("question-pack", item) for item in capability.question_pack_ids),
        *(("adapter", item) for item in capability.adapter_ids),
        *(("operational", item) for item in capability.operational_evidence_refs),
    )
    resolved = tuple(
        f"{kind}:{identifier}"
        for kind, identifier in requested
        if identifier in available[kind]
    )
    missing = tuple(
        f"{kind}:{identifier}"
        for kind, identifier in requested
        if identifier not in available[kind]
    )
    count_by_example = dict(inventory.example_route_counts)
    route_counts = tuple(
        count_by_example[item]
        for item in capability.example_ids
        if item in count_by_example
    )
    return resolved, missing, route_counts


def assess_capability(
    capability: CapabilityRequirement,
    inventory: RepositoryAssetInventory,
) -> CapabilityAssessment:
    """Derive contiguous C0-C7 gates; later evidence cannot skip an earlier gate."""

    resolved, missing, route_counts = _assets(capability, inventory)
    declaration_refs = (
        capability.template_ids
        + capability.question_pack_ids
        + capability.adapter_ids
        + capability.example_ids
    )
    benchmark_refs = capability.benchmark_ids + capability.agent_benchmark_ids
    resolved_names = {item.split(":", 1)[1] for item in resolved}
    gates = (
        ("C1", True),
        ("C2", bool(declaration_refs) and all(item in resolved_names for item in declaration_refs)),
        ("C3", bool(capability.example_ids) and len(route_counts) == len(capability.example_ids)),
        ("C4", bool(route_counts) and all(count > 0 for count in route_counts)),
        ("C5", any(count > 1 for count in route_counts)),
        ("C6", bool(benchmark_refs) and all(item in resolved_names for item in benchmark_refs)),
        (
            "C7",
            bool(capability.operational_evidence_refs)
            and all(
                item in set(inventory.operational_evidence_refs)
                for item in capability.operational_evidence_refs
            ),
        ),
    )
    level = "C0"
    satisfied: list[str] = []
    for gate, passed in gates:
        if not passed:
            break
        level = gate
        satisfied.append(gate)
    numeric_level = int(level[1:])
    if capability.blockers and numeric_level <= 2:
        status = "blocked"
    elif level == "C1":
        status = "catalog-only"
    elif numeric_level >= 6:
        status = "strong"
    elif numeric_level >= 2:
        status = "thin"
    else:
        status = "empty"
    evidence = {
        "capability": capability.to_dict(),
        "inventory": inventory.digest,
        "resolved": resolved,
        "missing": missing,
        "routes": route_counts,
        "gates": gates,
    }
    return CapabilityAssessment(
        capability_id=capability.id,
        obligation_id=capability.obligation_id,
        status=status,
        maturity_level=level,
        satisfied_gates=tuple(satisfied),
        next_gate=f"C{numeric_level + 1}" if numeric_level < 7 else "complete",
        resolved_assets=resolved,
        missing_assets=missing,
        route_count_upper_bound=sum(route_counts),
        blockers=capability.blockers,
        evidence_digest=sha256_digest(evidence),
    )


def assess_domain_pack(
    pack: DomainPack,
    inventory: RepositoryAssetInventory,
) -> DomainCoverageAssessment:
    capabilities = [assess_capability(item, inventory) for item in pack.capabilities]
    covered = {item.obligation_id for item in capabilities}
    for obligation_id in pack.required_obligation_ids:
        if obligation_id in covered:
            continue
        evidence = {
            "domain_pack": pack.digest,
            "obligation": obligation_id,
            "inventory": inventory.digest,
            "reason": "required obligation has no declared capability",
        }
        capabilities.append(
            CapabilityAssessment(
                capability_id=f"capability.gap.{pack.id.removeprefix('domain-pack.')}.{obligation_id.removeprefix('obligation.')}",
                obligation_id=obligation_id,
                status="empty",
                maturity_level="C0",
                satisfied_gates=(),
                next_gate="C1",
                resolved_assets=(),
                missing_assets=("capability-declaration",),
                route_count_upper_bound=0,
                blockers=(),
                evidence_digest=sha256_digest(evidence),
            )
        )
    capabilities.sort(key=lambda item: (item.obligation_id, item.capability_id))
    counts = Counter(item.status for item in capabilities)
    lowest = min(capabilities, key=lambda item: int(item.maturity_level[1:])).maturity_level
    return DomainCoverageAssessment(
        domain_pack_id=pack.id,
        domain_pack_digest=pack.digest,
        capabilities=tuple(capabilities),
        status_counts=tuple((status, counts[status]) for status in COVERAGE_STATUSES),
        lowest_maturity_level=lowest,
    )


@lru_cache(maxsize=1)
def reference_coverage_report() -> UniversalCoverageReport:
    inventory = reference_asset_inventory()
    domains = tuple(assess_domain_pack(pack, inventory) for pack in REFERENCE_DOMAIN_PACKS)
    counts = Counter(
        capability.status for domain in domains for capability in domain.capabilities
    )
    report = UniversalCoverageReport(
        id="coverage.reference-universal-engineering",
        generated_from=inventory.digest,
        domains=domains,
        status_counts=tuple((status, counts[status]) for status in COVERAGE_STATUSES),
        claim_boundary=(
            "Coverage is derived from exact checked-in templates, compiler-valid example "
            "route spaces, mechanism benchmarks, question packs, and adapter manifests. "
            "It is not a production-readiness or domain-superiority claim."
        ),
    )
    problems = report.validate()
    if problems:
        raise ValueError("invalid reference coverage report: " + "; ".join(problems))
    return report


__all__ = [
    "RepositoryAssetInventory",
    "assess_capability",
    "assess_domain_pack",
    "reference_asset_inventory",
    "reference_coverage_report",
]
