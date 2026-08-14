"""Small authoring helpers used by the bundled specialized pack modules."""

from __future__ import annotations

from solutiongraph.specialized.model import (
    EvaluationMetric,
    PackRecipe,
    ProfilerFeature,
    QualityGate,
    SpecializedPackDefinition,
)

SOURCE = (
    "https://github.com/Amarel-Taylor-Scott/"
    "universal-node-graph-flexible-solutioning/tree/main/solutiongraph/specialized"
)


def feature(
    namespace: str,
    key: str,
    title: str,
    description: str,
    value_kind: str,
    *,
    mode: str = "deterministic",
    evidence_kind: str = "evidence.task-profile",
    cost_tier: int = 1,
    effects: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
    requirements: tuple[str, ...] = (),
) -> ProfilerFeature:
    return ProfilerFeature(
        id=f"feature.{namespace}.{key}",
        title=title,
        description=description,
        value_kind=value_kind,
        mode=mode,
        evidence_kind=evidence_kind,
        cost_tier=cost_tier,
        effects=effects,
        permissions=permissions,
        requirements=requirements,
    )


def embedding_feature(
    namespace: str,
    key: str,
    title: str,
    description: str,
    *,
    cost_tier: int = 7,
) -> ProfilerFeature:
    return feature(
        namespace,
        key,
        title,
        description,
        "vector",
        mode="model",
        evidence_kind="evidence.embedding-sidecar",
        cost_tier=cost_tier,
        effects=("model.invoke",),
        permissions=("model.invoke",),
        requirements=("requirement.exact-embedding-space-identity",),
    )


def metric(
    namespace: str,
    key: str,
    title: str,
    description: str,
    direction: str,
    unit: str,
    *,
    scope: str = "scope.task",
    evidence: tuple[str, ...] = ("evidence.independent-evaluation",),
) -> EvaluationMetric:
    return EvaluationMetric(
        id=f"metric.{namespace}.{key}",
        title=title,
        description=description,
        direction=direction,
        unit=unit,
        scope=scope,
        required_evidence=evidence,
    )


def gate(
    namespace: str,
    key: str,
    title: str,
    description: str,
    metric_ids: tuple[str, ...],
    *,
    oracle_kind: str = "property",
    decision: str = "reject",
    independent: bool = True,
) -> QualityGate:
    return QualityGate(
        id=f"gate.{namespace}.{key}",
        title=title,
        description=description,
        metric_ids=metric_ids,
        oracle_kind=oracle_kind,
        decision=decision,
        independent=independent,
    )


def recipe(
    namespace: str,
    key: str,
    title: str,
    description: str,
    inputs: tuple[str, ...],
    outputs: tuple[str, ...],
    capabilities: tuple[str, ...],
    categories: tuple[str, ...],
    templates: tuple[str, ...],
    *,
    node_packs: tuple[str, ...] = (),
    question_packs: tuple[str, ...] = (),
    design_packs: tuple[str, ...] = (),
    examples: tuple[str, ...] = (),
    benchmarks: tuple[str, ...] = (),
    agent_benchmarks: tuple[str, ...] = (),
    arena_tasks: tuple[str, ...] = (),
    adapters: tuple[str, ...] = (),
    effects: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
) -> PackRecipe:
    return PackRecipe(
        id=f"recipe.{namespace}.{key}",
        title=title,
        description=description,
        input_kind_ids=inputs,
        output_kind_ids=outputs,
        capability_ids=capabilities,
        category_ids=categories,
        template_ids=templates,
        node_pack_ids=node_packs,
        question_pack_ids=question_packs,
        design_pack_ids=design_packs,
        example_ids=examples,
        benchmark_ids=benchmarks,
        agent_benchmark_ids=agent_benchmarks,
        arena_task_ids=arena_tasks,
        adapter_ids=adapters,
        effects=effects,
        permissions=permissions,
        limitations=limitations,
    )


def specialized_pack(
    namespace: str,
    title: str,
    description: str,
    *,
    domain_packs: tuple[str, ...],
    categories: tuple[str, ...],
    signals: tuple[str, ...],
    recipes: tuple[PackRecipe, ...],
    features: tuple[ProfilerFeature, ...],
    metrics: tuple[EvaluationMetric, ...],
    gates: tuple[QualityGate, ...],
    readiness: str = "executable-fixture",
    limitations: tuple[str, ...] = (
        "This capability pack recommends authoring assets; compiler admission and a "
        "task-specific SolutionPackManifest are still required before execution.",
    ),
) -> SpecializedPackDefinition:
    entry_name = namespace.replace("_", "-")
    return SpecializedPackDefinition(
        id=f"specialized-pack.{entry_name}",
        version="0.1.0",
        title=title,
        description=description,
        readiness=readiness,
        current_distribution="browsergraph",
        python_module=f"solutiongraph.specialized.{namespace}",
        entry_point_name=entry_name,
        extraction_target=f"solutiongraph-pack-{entry_name}",
        domain_pack_ids=domain_packs,
        task_category_ids=categories,
        signal_terms=signals,
        recipes=recipes,
        profiler_features=features,
        metrics=metrics,
        gates=gates,
        source=SOURCE,
        license="MIT",
        limitations=limitations,
        extensions=(("solutiongraph.delivery", "bundled-extraction-ready"),),
    )


__all__ = [
    "SOURCE",
    "embedding_feature",
    "feature",
    "gate",
    "metric",
    "recipe",
    "specialized_pack",
]
