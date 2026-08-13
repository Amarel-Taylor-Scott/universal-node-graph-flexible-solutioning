"""Portable frozen-plan exports for external orchestration adapters."""

from __future__ import annotations

from collections import defaultdict

from solutiongraph.integrations.model import (
    OrchestratorPlanProjection,
    OrchestratorTask,
)
from solutiongraph.integrations.profiles import INTEGRATION_ADAPTER_BY_ID
from solutiongraph.model import FrozenPlan, ProgramGraph, Registry

_TARGET_VERSION = {
    "adapter.orchestrator.airflow": "3",
    "adapter.orchestrator.dagster": "1",
    "adapter.orchestrator.temporal": "1",
    "adapter.orchestrator.kubernetes": "batch/v1",
}


def export_frozen_plan(
    plan: FrozenPlan,
    program: ProgramGraph,
    registry: Registry,
    *,
    adapter_id: str,
) -> OrchestratorPlanProjection:
    """Export exact task identity and dependencies without scheduling work.

    The returned record deliberately is not native Airflow, Dagster, Temporal,
    or Kubernetes code.  A deployment adapter must translate it while retaining
    the frozen identities and enforcing permissions, effects, resources, and
    runtime isolation.
    """

    if adapter_id not in _TARGET_VERSION:
        raise ValueError(f"unsupported orchestrator adapter {adapter_id!r}")
    profile = INTEGRATION_ADAPTER_BY_ID[adapter_id]
    if plan.program_digest != program.digest:
        raise ValueError("frozen plan does not match the supplied program")
    if plan.registry_digest != registry.digest:
        raise ValueError("frozen plan does not match the supplied registry")
    binding_by_slot = {item.slot_id: item for item in plan.bindings}
    if set(binding_by_slot) != set(plan.topological_order):
        raise ValueError("frozen plan bindings do not match its topological order")
    node_map = registry.node_map()
    dependencies: dict[str, list[str]] = defaultdict(list)
    for edge in plan.edges:
        dependencies[edge.target_slot].append(edge.source_slot)
    for slot in program.slots:
        if slot.activation_slot:
            dependencies[slot.id].append(slot.activation_slot)
    fallbacks: dict[str, list[str]] = defaultdict(list)
    for item in sorted(plan.fallbacks, key=lambda fallback: fallback.priority):
        fallbacks[item.slot_id].append(item.candidate_id)

    tasks: list[OrchestratorTask] = []
    for slot_id in plan.topological_order:
        binding = binding_by_slot[slot_id]
        node = node_map.get((binding.node_id, binding.node_version))
        if node is None:
            raise ValueError(f"plan binding {binding.candidate_id} references an unknown node")
        if node.implementation_digest != binding.implementation_digest:
            raise ValueError(
                f"plan binding {binding.candidate_id} implementation digest is stale"
            )
        tasks.append(
            OrchestratorTask(
                slot_id=slot_id,
                candidate_id=binding.candidate_id,
                node_id=node.id,
                node_version=node.version,
                implementation_digest=node.implementation_digest,
                runtime=node.runtime,
                entrypoint=node.entrypoint,
                parameters=binding.parameters,
                fallback_candidate_ids=tuple(fallbacks[slot_id]),
                dependencies=tuple(dict.fromkeys(dependencies[slot_id])),
                effects=node.effects,
                permissions=node.permissions,
                resources=tuple(item.to_dict() for item in node.resources),
            )
        )
    projection = OrchestratorPlanProjection(
        id=f"orchestrator-projection.{adapter_id.removeprefix('adapter.orchestrator.')}.{plan.digest.removeprefix('sha256:')[:20]}",
        adapter_id=profile.id,
        adapter_digest=profile.digest,
        target=profile.source_kind,
        target_version=_TARGET_VERSION[adapter_id],
        plan_digest=plan.digest,
        program_digest=plan.program_digest,
        registry_digest=plan.registry_digest,
        admitted_space_digest=plan.admitted_space_digest,
        tasks=tuple(tasks),
        limitations=profile.limitations,
    )
    problems = projection.validate()
    if problems:
        raise ValueError("invalid orchestrator projection: " + "; ".join(problems))
    return projection


__all__ = ["export_frozen_plan"]
