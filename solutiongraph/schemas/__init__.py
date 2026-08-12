"""Bundled JSON Schemas for non-Python registries and executors."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

SCHEMA_NAMES = (
    "common.schema.json",
    "artifact-record.schema.json",
    "node-spec.schema.json",
    "program-graph.schema.json",
    "registry.schema.json",
    "admitted-space.schema.json",
    "frozen-plan.schema.json",
    "execution-policy.schema.json",
    "verification-result.schema.json",
    "run-receipt.schema.json",
    "receipt-journal-record.schema.json",
    "solutiongraph-project.schema.json",
    "campaign-budget.schema.json",
    "evaluation-boundary.schema.json",
    "harness-bundle.schema.json",
    "harness-evidence-bundle.schema.json",
    "candidate-record.schema.json",
    "campaign-ledger.schema.json",
    "node-descriptor.schema.json",
    "embedding-record.schema.json",
    "registry-capabilities.schema.json",
    "harness-capabilities.schema.json",
    "registry-session.schema.json",
    "discovery-query.schema.json",
    "discovery-receipt.schema.json",
    "registry-snapshot.schema.json",
    "node-pack.schema.json",
    "solution-template.schema.json",
    "template-blueprint.schema.json",
    "search-report.schema.json",
    "arena-task.schema.json",
    "solver-result.schema.json",
    "topology-family.schema.json",
    "subgraph-catalog.schema.json",
    "structured-lowering-receipt.schema.json",
    "node-compatibility-profile.schema.json",
    "compatibility-catalog.schema.json",
    "execution-checkpoint.schema.json",
    "topology-search-report.schema.json",
    "stream-window-policy.schema.json",
    "stream-event.schema.json",
    "stream-emission.schema.json",
    "stream-run-receipt.schema.json",
    "stream-result.schema.json",
    "successive-halving-run.schema.json",
    "provenance-bundle.schema.json",
    "openlineage-execution-facet.schema.json",
    "openlineage-artifact-facet.schema.json",
    "saga-result.schema.json",
    "conformance-result.schema.json",
    "task-case.schema.json",
    "task-contract.schema.json",
    "task-category-registry.schema.json",
    "task-fingerprint.schema.json",
    "historical-memory.schema.json",
    "historical-memory-update.schema.json",
    "search-initialization.schema.json",
    "solution-pack.schema.json",
    "benchmark-suite.schema.json",
    "benchmark-report.schema.json",
)


def load_schema(name: str) -> dict[str, Any]:
    if name not in SCHEMA_NAMES:
        raise ValueError(f"unknown SolutionGraph schema {name!r}")
    resource = files("solutiongraph.schemas").joinpath(name)
    return json.loads(resource.read_text(encoding="utf-8"))


def load_all_schemas() -> dict[str, dict[str, Any]]:
    return {name: load_schema(name) for name in SCHEMA_NAMES}


__all__ = ["SCHEMA_NAMES", "load_all_schemas", "load_schema"]
