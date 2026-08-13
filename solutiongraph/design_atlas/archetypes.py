"""Common task archetypes that route into the design-question system."""

from __future__ import annotations

from solutiongraph.design_atlas.model import TaskArchetype
from solutiongraph.design_atlas.packs import DESIGN_PACK_BY_ID

CORE = (
    "design-pack.task-contract",
    "design-pack.data-source",
    "design-pack.schema-semantics",
)
CLOSE = (
    "design-pack.reproducibility-governance",
    "design-pack.decision-handoff",
)
STANDARD_MODEL = (
    "design-pack.profiling-eda",
    "design-pack.quality-cleaning",
    "design-pack.validation-splits",
    "design-pack.feature-engineering",
    "design-pack.target-labels",
    "design-pack.baselines-models",
    "design-pack.tuning-search",
    "design-pack.evaluation-error",
)


def _a(
    key: str,
    title: str,
    description: str,
    outcome: str,
    required: tuple[str, ...],
    optional: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
) -> TaskArchetype:
    return TaskArchetype(
        id=f"task.{key}",
        title=title,
        description=description,
        outcome_artifact=outcome,
        required_pack_ids=tuple(dict.fromkeys((*CORE, *required, *CLOSE))),
        optional_pack_ids=tuple(dict.fromkeys(optional)),
        tags=(f"task.{key}", *tags),
    )


REFERENCE_TASK_ARCHETYPES = (
    _a(
        "data-cleaning", "Data cleaning",
        "Detect, repair, quarantine, and independently verify quality defects while preserving raw evidence.",
        "artifact.cleaned-dataset",
        ("design-pack.profiling-eda", "design-pack.quality-cleaning"),
        ("design-pack.geospatial", "design-pack.time-series"),
        ("domain.data-engineering",),
    ),
    _a(
        "data-validation", "Data validation",
        "Compile schema, semantic, cross-field, source, drift, and policy checks into an auditable gate.",
        "artifact.validation-report",
        ("design-pack.profiling-eda", "design-pack.quality-cleaning"),
        ("design-pack.monitoring-feedback",),
        ("domain.data-engineering",),
    ),
    _a(
        "data-enrichment", "Data enrichment",
        "Join internal or external facts with explicit identity, authority, vintage, confidence, and lineage.",
        "artifact.enriched-dataset",
        ("design-pack.quality-cleaning",),
        ("design-pack.geospatial", "design-pack.time-series", "design-pack.text-document"),
        ("domain.data-engineering",),
    ),
    _a(
        "geospatial-enrichment", "Geospatial enrichment",
        "Validate and enrich addresses, coordinates, boundaries, places, proximity, and geographic attributes.",
        "artifact.geospatial-dataset",
        ("design-pack.quality-cleaning", "design-pack.geospatial"),
        ("design-pack.monitoring-feedback",),
        ("domain.geospatial", "signal.geospatial"),
    ),
    _a(
        "temporal-enrichment", "Temporal enrichment",
        "Enrich records with calendars, events, rolling context, and point-in-time-safe external facts.",
        "artifact.temporal-dataset",
        ("design-pack.quality-cleaning", "design-pack.time-series"),
        ("design-pack.geospatial",),
        ("domain.temporal", "signal.time-aware"),
    ),
    _a(
        "geotemporal-enrichment", "Geotemporal enrichment",
        "Join versioned place and event context at the correct location, time, and availability boundary.",
        "artifact.geotemporal-dataset",
        ("design-pack.quality-cleaning", "design-pack.time-series", "design-pack.geospatial"),
        (), ("domain.geospatial", "signal.geospatial", "signal.time-aware"),
    ),
    _a(
        "entity-resolution", "Entity resolution",
        "Link or deduplicate people, organizations, products, places, and records with calibrated abstention.",
        "artifact.entity-map",
        ("design-pack.profiling-eda", "design-pack.quality-cleaning", "design-pack.evaluation-error"),
        ("design-pack.fairness-risk",),
        ("domain.identity", "signal.entity-aware"),
    ),
    _a(
        "dataset-profiling", "Dataset profiling and EDA",
        "Produce reproducible aggregate, slice, conflict, anomaly, and hypothesis summaries.",
        "artifact.data-profile",
        ("design-pack.profiling-eda",),
        ("design-pack.quality-cleaning", "design-pack.geospatial", "design-pack.time-series"),
        ("domain.data-science",),
    ),
    _a(
        "tabular-regression", "Tabular regression",
        "Predict a continuous outcome with leakage-safe preprocessing, uncertainty, and controlled model search.",
        "artifact.regression-model", STANDARD_MODEL,
        ("design-pack.selection-reduction", "design-pack.ensemble-calibration", "design-pack.interpretability"),
        ("domain.machine-learning", "signal.supervised"),
    ),
    _a(
        "binary-classification", "Binary classification",
        "Predict or rank binary outcomes with cost-aware evaluation, calibration, and threshold policy.",
        "artifact.classification-model", STANDARD_MODEL,
        ("design-pack.ensemble-calibration", "design-pack.fairness-risk", "design-pack.interpretability"),
        ("domain.machine-learning", "signal.supervised"),
    ),
    _a(
        "multiclass-classification", "Multiclass or multilabel classification",
        "Model exclusive, hierarchical, ordinal, or overlapping labels with class- and slice-aware metrics.",
        "artifact.classification-model", STANDARD_MODEL,
        ("design-pack.ensemble-calibration", "design-pack.fairness-risk"),
        ("domain.machine-learning", "signal.supervised"),
    ),
    _a(
        "imbalanced-classification", "Imbalanced or rare-event classification",
        "Optimize rare-event discovery under explicit costs, capacity, calibration, and prevalence shift.",
        "artifact.rare-event-model", (*STANDARD_MODEL, "design-pack.ensemble-calibration"),
        ("design-pack.synthetic-data", "design-pack.fairness-risk"),
        ("domain.machine-learning", "signal.supervised", "signal.imbalanced"),
    ),
    _a(
        "ranking-recommendation", "Ranking and recommendation",
        "Rank items or actions with exposure, feedback, cold-start, counterfactual, and policy constraints.",
        "artifact.ranking-policy", STANDARD_MODEL,
        ("design-pack.causality-experiments", "design-pack.reinforcement-learning", "design-pack.fairness-risk"),
        ("domain.machine-learning", "signal.supervised"),
    ),
    _a(
        "forecasting", "Forecasting",
        "Predict future quantities or events with point-in-time features, realistic backtests, and uncertainty.",
        "artifact.forecast-model", (*STANDARD_MODEL, "design-pack.time-series"),
        ("design-pack.geospatial", "design-pack.ensemble-calibration"),
        ("domain.machine-learning", "signal.time-aware", "signal.supervised"),
    ),
    _a(
        "survival-analysis", "Survival and time-to-event modeling",
        "Model event timing under censoring, competing risks, delayed entry, and calibration over horizons.",
        "artifact.survival-model", (*STANDARD_MODEL, "design-pack.time-series"),
        ("design-pack.ensemble-calibration",),
        ("domain.machine-learning", "signal.time-aware", "signal.censored"),
    ),
    _a(
        "anomaly-detection", "Anomaly and novelty detection",
        "Identify unusual points, sequences, entities, or clusters with scarce labels and review capacity.",
        "artifact.anomaly-detector",
        ("design-pack.profiling-eda", "design-pack.feature-engineering", "design-pack.baselines-models", "design-pack.evaluation-error", "design-pack.robustness-stability"),
        ("design-pack.time-series", "design-pack.interpretability"),
        ("domain.machine-learning", "signal.unsupervised"),
    ),
    _a(
        "clustering-segmentation", "Clustering and segmentation",
        "Discover stable, useful groups with distance, dimension, uncertainty, and external utility checks.",
        "artifact.segment-model",
        ("design-pack.profiling-eda", "design-pack.feature-engineering", "design-pack.selection-reduction", "design-pack.baselines-models", "design-pack.evaluation-error"),
        ("design-pack.interpretability", "design-pack.robustness-stability"),
        ("domain.machine-learning", "signal.unsupervised"),
    ),
    _a(
        "causal-inference", "Causal inference",
        "Estimate effects of interventions from experimental or observational evidence with explicit identification.",
        "artifact.causal-estimate",
        ("design-pack.profiling-eda", "design-pack.validation-splits", "design-pack.causality-experiments", "design-pack.evaluation-error"),
        ("design-pack.fairness-risk",),
        ("domain.causal",),
    ),
    _a(
        "experiment-design", "Experiment design and analysis",
        "Allocate treatments, measure exposure and outcomes, and analyze effects under interference and operational constraints.",
        "artifact.experiment-report",
        ("design-pack.causality-experiments", "design-pack.evaluation-error"),
        ("design-pack.fairness-risk", "design-pack.monitoring-feedback"),
        ("domain.causal",),
    ),
    _a(
        "synthetic-data", "Synthetic-data generation",
        "Generate or augment tabular, text, image, document, sequence, or multimodal data under utility and privacy gates.",
        "artifact.synthetic-dataset",
        ("design-pack.profiling-eda", "design-pack.validation-splits", "design-pack.synthetic-data", "design-pack.evaluation-error", "design-pack.robustness-stability"),
        ("design-pack.text-document", "design-pack.image-multimodal", "design-pack.fairness-risk"),
        ("domain.synthetic-data",),
    ),
    _a(
        "text-classification", "Text and NLP modeling",
        "Classify, score, retrieve, summarize, or extract from text with document and language-aware evaluation.",
        "artifact.text-model", (*STANDARD_MODEL, "design-pack.text-document"),
        ("design-pack.llm-harness", "design-pack.fairness-risk"),
        ("domain.nlp",),
    ),
    _a(
        "document-extraction", "Document extraction",
        "Convert PDFs, forms, tables, images, and mixed documents into grounded structured outputs.",
        "artifact.structured-document",
        ("design-pack.quality-cleaning", "design-pack.text-document", "design-pack.image-multimodal", "design-pack.evaluation-error"),
        ("design-pack.llm-harness",),
        ("domain.document-intelligence",),
    ),
    _a(
        "computer-vision", "Image and computer-vision modeling",
        "Classify, detect, segment, retrieve, or generate images under capture and robustness constraints.",
        "artifact.vision-model", (*STANDARD_MODEL, "design-pack.image-multimodal"),
        ("design-pack.synthetic-data", "design-pack.fairness-risk"),
        ("domain.computer-vision",),
    ),
    _a(
        "multimodal-modeling", "Multimodal modeling",
        "Combine text, image, audio, video, document, sensor, or tabular inputs with explicit alignment and ablations.",
        "artifact.multimodal-model", (*STANDARD_MODEL, "design-pack.text-document", "design-pack.image-multimodal"),
        ("design-pack.llm-harness", "design-pack.synthetic-data"),
        ("domain.multimodal",),
    ),
    _a(
        "retrieval", "Retrieval and RAG",
        "Index, retrieve, rerank, ground, answer, cite, abstain, and refresh knowledge under separate component evaluation.",
        "artifact.retrieval-system",
        ("design-pack.text-document", "design-pack.baselines-models", "design-pack.tuning-search", "design-pack.evaluation-error", "design-pack.llm-harness"),
        ("design-pack.robustness-stability", "design-pack.monitoring-feedback"),
        ("domain.retrieval",),
    ),
    _a(
        "reinforcement-learning", "Reinforcement learning",
        "Learn or compare sequential policies with explicit support, safety, and offline/online evaluation boundaries.",
        "artifact.policy", ("design-pack.reinforcement-learning", "design-pack.evaluation-error", "design-pack.robustness-stability"),
        ("design-pack.causality-experiments", "design-pack.fairness-risk"),
        ("domain.reinforcement-learning",),
    ),
    _a(
        "llm-evaluation", "LLM and agent evaluation harness",
        "Compare models, prompts, tools, agents, supervisors, and contexts across fixed scenarios and multiple evaluators.",
        "artifact.llm-evaluation-report",
        ("design-pack.llm-harness", "design-pack.evaluation-error", "design-pack.robustness-stability"),
        ("design-pack.fairness-risk", "design-pack.deployment-serving"),
        ("domain.llm",),
    ),
    _a(
        "llm-red-teaming", "LLM and agent red teaming",
        "Discover, reproduce, classify, mitigate, and regression-test model and tool-enabled failure modes.",
        "artifact.red-team-report",
        ("design-pack.llm-harness", "design-pack.robustness-stability", "design-pack.fairness-risk"),
        ("design-pack.monitoring-feedback",),
        ("domain.llm", "risk.high"),
    ),
    _a(
        "user-action-modeling", "User action, journey, and flow modeling",
        "Model events, sessions, funnels, transitions, interventions, and delayed outcomes without identity or feedback leakage.",
        "artifact.user-flow-model", (*STANDARD_MODEL, "design-pack.time-series"),
        ("design-pack.causality-experiments", "design-pack.reinforcement-learning", "design-pack.fairness-risk"),
        ("domain.product-analytics", "signal.time-aware", "signal.entity-aware"),
    ),
    _a(
        "streaming-ml", "Streaming and online ML",
        "Process event-time data with windows, late arrivals, checkpoints, online state, drift, and safe updates.",
        "artifact.streaming-model",
        ("design-pack.time-series", "design-pack.validation-splits", "design-pack.deployment-serving", "design-pack.monitoring-feedback"),
        ("design-pack.reinforcement-learning",),
        ("domain.streaming", "signal.time-aware"),
    ),
    _a(
        "model-operations", "Model release and operations",
        "Package, release, observe, compare, retrain, roll back, and retire an existing model or graph.",
        "artifact.operational-model",
        ("design-pack.evaluation-error", "design-pack.robustness-stability", "design-pack.deployment-serving", "design-pack.monitoring-feedback"),
        ("design-pack.fairness-risk", "design-pack.interpretability"),
        ("domain.mlops", "lifecycle.production"),
    ),
)

ARCHETYPE_BY_ID = {item.id: item for item in REFERENCE_TASK_ARCHETYPES}


def normalize_task_type(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-").replace(" ", "-")
    aliases = {
        "regression": "tabular-regression",
        "classification": "binary-classification",
        "multiclass": "multiclass-classification",
        "forecast": "forecasting",
        "rag": "retrieval",
        "llm-eval": "llm-evaluation",
        "red-teaming": "llm-red-teaming",
        "cleaning": "data-cleaning",
        "validation": "data-validation",
        "enrichment": "data-enrichment",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized.startswith("task.") else f"task.{normalized}"


def get_archetype(value: str) -> TaskArchetype:
    task_id = normalize_task_type(value)
    try:
        return ARCHETYPE_BY_ID[task_id]
    except KeyError as exc:
        choices = ", ".join(item.id.removeprefix("task.") for item in REFERENCE_TASK_ARCHETYPES)
        raise ValueError(f"unknown task archetype {value!r}; choose one of: {choices}") from exc


def validate_archetypes() -> list[str]:
    problems: list[str] = []
    if len(ARCHETYPE_BY_ID) != len(REFERENCE_TASK_ARCHETYPES):
        problems.append("task archetype ids must be unique")
    for index, archetype in enumerate(REFERENCE_TASK_ARCHETYPES):
        problems.extend(archetype.validate(f"archetypes[{index}]"))
        missing = set((*archetype.required_pack_ids, *archetype.optional_pack_ids)).difference(
            DESIGN_PACK_BY_ID
        )
        if missing:
            problems.append(f"{archetype.id} references unknown packs: {sorted(missing)}")
    return problems


__all__ = [
    "ARCHETYPE_BY_ID",
    "REFERENCE_TASK_ARCHETYPES",
    "get_archetype",
    "normalize_task_type",
    "validate_archetypes",
]
