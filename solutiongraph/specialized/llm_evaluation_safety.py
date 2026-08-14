"""Specialized package for independent LLM, agent, and safety evaluation."""

from solutiongraph.specialized._builders import (
    embedding_feature,
    feature,
    gate,
    metric,
    recipe,
    specialized_pack,
)

NAMESPACE = "llm-evaluation-safety"

FEATURES = (
    feature(
        NAMESPACE,
        "system-surface",
        "System surface",
        "Profile model, prompt, retrieval, tools, memory, authority, sampling, and environment identity.",
        "mapping",
    ),
    feature(
        NAMESPACE,
        "scenario-coverage",
        "Scenario coverage",
        "Count normal, boundary, multilingual, long-context, tool, adversarial, and failure-recovery slices.",
        "mapping",
    ),
    feature(
        NAMESPACE,
        "evaluator-independence",
        "Evaluator independence",
        "Profile producer/judge family overlap, candidate readability, human sampling, and outer-evaluator isolation.",
        "mapping",
    ),
    embedding_feature(
        NAMESPACE,
        "failure-embedding",
        "Failure-family embedding",
        "Optional redacted failure-family embedding for diverse retrieval under an exact embedding-space identity.",
    ),
)

METRICS = (
    metric(
        NAMESPACE,
        "slice-acceptance",
        "Slice acceptance",
        "Independent task acceptance reported by predeclared scenario slice.",
        "maximize",
        "ratio",
        scope="scope.scenario",
    ),
    metric(
        NAMESPACE,
        "judge-calibration",
        "Judge calibration",
        "Agreement, calibration, and correlated-error evidence across deterministic, model, panel, and human judges.",
        "maximize",
        "ratio",
        scope="scope.evaluation",
    ),
    metric(
        NAMESPACE,
        "attack-success",
        "Attack success rate",
        "Share of adversarial scenarios that cause a declared safety, integrity, privacy, or authority failure.",
        "minimize",
        "ratio",
        scope="scope.stress",
    ),
    metric(
        NAMESPACE,
        "sealed-acceptance",
        "Sealed acceptance",
        "Acceptance on candidate-unreadable cases and evaluator infrastructure.",
        "maximize",
        "ratio",
        scope="scope.holdout",
    ),
)

GATES = (
    gate(
        NAMESPACE,
        "development",
        "Development evidence gate",
        "Reject improvement claims without slice acceptance, judge calibration, and retained negative evidence.",
        (METRICS[0].id, METRICS[1].id),
        oracle_kind="cross-implementation",
    ),
    gate(
        NAMESPACE,
        "promotion",
        "Sealed promotion gate",
        "Reject promotion when adversarial or sealed evidence fails the predeclared threshold or accountable approval is absent.",
        (METRICS[2].id, METRICS[3].id),
        oracle_kind="human",
    ),
)

RECIPES = (
    recipe(
        NAMESPACE,
        "system-evaluation",
        "LLM system evaluation",
        "Freeze criteria and scenarios, execute the exact system, apply diverse judges, adjudicate disagreement, and publish a sealed promotion report.",
        ("artifact.llm-system",),
        ("artifact.llm-evaluation-report",),
        (
            "llm-eval.contract",
            "llm-eval.scenario",
            "llm-eval.execute",
            "llm-eval.judge",
            "llm-eval.promote",
        ),
        ("dag.evaluate.llm-harness", "dag.evaluate.judge", "dag.evaluate.outer"),
        ("template.llm-evaluation-harness",),
        node_packs=("example.engineering-showcase-node-pack",),
        design_packs=(
            "design-pack.llm-harness",
            "design-pack.evaluation-error",
            "design-pack.reproducibility-governance",
        ),
        examples=("duecare-llm-evaluation-harness",),
        arena_tasks=("arena.llm-evaluation-harness",),
        limitations=(
            "The bundled DueCare-style evidence is a transparent mechanism fixture; confidential evaluation requires a separate candidate-unreadable trust domain.",
        ),
    ),
    recipe(
        NAMESPACE,
        "agent-trajectory",
        "Agent and tool-use evaluation",
        "Evaluate planning, tool choice, authority, intermediate state, recovery, and final outcomes over exact agent trajectories.",
        ("artifact.agent-system",),
        ("artifact.llm-evaluation-report",),
        (
            "agent-eval.trace",
            "agent-eval.tool-authority",
            "agent-eval.outcome",
            "agent-eval.compare",
        ),
        ("dag.evaluate.agent", "dag.evaluate.safety", "dag.evaluate.outer"),
        ("template.llm-evaluation-harness", "template.qa-engineering"),
        node_packs=("reference.core-node-pack",),
        agent_benchmarks=(
            "agent-benchmark.reference-smoke",
            "agent-benchmark.command-matrix-example",
        ),
        arena_tasks=("arena.repository-repair",),
        limitations=(
            "The bundled coding-agent smoke harness is model-free and does not prove frontier-model quality.",
        ),
    ),
    recipe(
        NAMESPACE,
        "red-team-regression",
        "Red-team to regression curriculum",
        "Generate lineage-bound adversarial families, deduplicate and partition them, cluster failures, sanitize feedback, and build a non-leaking regression suite.",
        ("artifact.llm-system",),
        ("artifact.red-team-regression-suite",),
        (
            "llm-eval.red-team",
            "llm-eval.deduplicate",
            "llm-eval.cluster",
            "llm-eval.regression-suite",
        ),
        ("dag.generate.synthetic.adversarial", "dag.evaluate.safety", "dag.evaluate.metamorphic"),
        ("template.llm-evaluation-harness", "template.content-moderation"),
        node_packs=("example.engineering-showcase-node-pack",),
        design_packs=(
            "design-pack.llm-harness",
            "design-pack.robustness-stability",
            "design-pack.fairness-risk",
        ),
        examples=("synthetic-llm-curriculum", "duecare-llm-evaluation-harness"),
        arena_tasks=("arena.content-policy-moderation",),
    ),
)

PACK = specialized_pack(
    "llm_evaluation_safety",
    "LLM evaluation and safety",
    "Independent LLM and agent evaluation, judge calibration, red teaming, regression curricula, feedback firewalls, and sealed promotion.",
    domain_packs=(
        "domain-pack.llm-agent",
        "domain-pack.security-compliance",
        "domain-pack.business-human-workflow",
    ),
    categories=tuple(dict.fromkeys(category for item in RECIPES for category in item.category_ids)),
    signals=(
        "llm evaluation",
        "agent evaluation",
        "red team",
        "safety evaluation",
        "judge calibration",
        "sealed holdout",
        "due care",
        "adversarial testing",
    ),
    recipes=RECIPES,
    features=FEATURES,
    metrics=METRICS,
    gates=GATES,
)

__all__ = ["FEATURES", "GATES", "METRICS", "PACK", "RECIPES"]
