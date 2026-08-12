"""Extensible task-category seed registry for history-informed graph search.

The registry is intentionally not an ontology gate.  A task may match any
number of categories, callers may supply a different registry, and unknown
namespaced categories remain valid fingerprint attributes.  The bundled
catalog is only a useful cold-start vocabulary for common DAG work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from solutiongraph.model import ID_RE, canonical_json, sha256_digest
from solutiongraph.tasking import TaskContract

TASK_CATEGORY_MODEL_VERSION = "0.1"


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
class TaskCategory:
    """One composable task-family hint, never an admission rule."""

    id: str
    title: str
    description: str
    parent_ids: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    signal_terms: tuple[str, ...] = ()
    typical_inputs: tuple[str, ...] = ()
    typical_outputs: tuple[str, ...] = ()
    template_ids: tuple[str, ...] = ()
    extensions: tuple[tuple[str, Any], ...] = ()

    def validate(self, path: str = "category") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or "." not in self.id:
            problems.append(f"{path}.id must be a namespaced identifier")
        if not self.title.strip() or not self.description.strip():
            problems.append(f"{path}.title and description must not be empty")
        for label, values in (
            ("parent_ids", self.parent_ids),
            ("aliases", self.aliases),
            ("signal_terms", self.signal_terms),
            ("typical_inputs", self.typical_inputs),
            ("typical_outputs", self.typical_outputs),
            ("template_ids", self.template_ids),
        ):
            if len(values) != len(set(values)):
                problems.append(f"{path}.{label} must be unique")
            if any(not value.strip() for value in values):
                problems.append(f"{path}.{label} must not contain empty values")
        if any(not ID_RE.fullmatch(value) for value in self.parent_ids):
            problems.append(f"{path}.parent_ids must contain namespaced identifiers")
        if any(not ID_RE.fullmatch(value) for value in self.template_ids):
            problems.append(f"{path}.template_ids must contain namespaced identifiers")
        problems.extend(_extension_problems(self.extensions, f"{path}.extensions"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "parent_ids": list(self.parent_ids),
            "aliases": list(self.aliases),
            "signal_terms": list(self.signal_terms),
            "typical_inputs": list(self.typical_inputs),
            "typical_outputs": list(self.typical_outputs),
            "template_ids": list(self.template_ids),
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class TaskCategoryMatch:
    category_id: str
    score: float
    matched_terms: tuple[str, ...]
    evidence_kind: str = "evidence.inferred"

    def validate(self, path: str = "category_match") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.category_id):
            problems.append(f"{path}.category_id must be a namespaced identifier")
        if not 0.0 <= self.score <= 1.0:
            problems.append(f"{path}.score must be between zero and one")
        if len(self.matched_terms) != len(set(self.matched_terms)):
            problems.append(f"{path}.matched_terms must be unique")
        if not self.matched_terms or any(not term.strip() for term in self.matched_terms):
            problems.append(f"{path}.matched_terms must contain nonempty evidence")
        if not ID_RE.fullmatch(self.evidence_kind):
            problems.append(f"{path}.evidence_kind must be a namespaced identifier")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "category_id": self.category_id,
            "score": self.score,
            "matched_terms": list(self.matched_terms),
            "evidence_kind": self.evidence_kind,
        }


@dataclass(frozen=True)
class TaskCategoryRegistry:
    """A replaceable seed catalog with deterministic multi-label matching."""

    id: str
    version: str
    categories: tuple[TaskCategory, ...]
    description: str = ""
    extensions: tuple[tuple[str, Any], ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or "." not in self.id:
            problems.append("category registry id must be namespaced")
        if not self.version.strip():
            problems.append("category registry version must not be empty")
        if not self.categories:
            problems.append("category registry must contain categories")
        ids = [category.id for category in self.categories]
        if len(ids) != len(set(ids)):
            problems.append("category registry ids must be unique")
        known = set(ids)
        for index, category in enumerate(self.categories):
            problems.extend(category.validate(f"categories[{index}]"))
            unknown = sorted(set(category.parent_ids) - known)
            if unknown:
                problems.append(
                    f"categories[{index}] references unknown parents: {', '.join(unknown)}"
                )
        problems.extend(self._cycle_problems())
        problems.extend(_extension_problems(self.extensions, "registry.extensions"))
        return problems

    def _cycle_problems(self) -> list[str]:
        parents = {category.id: category.parent_ids for category in self.categories}
        visiting: set[str] = set()
        visited: set[str] = set()

        def walk(category_id: str) -> bool:
            if category_id in visiting:
                return True
            if category_id in visited:
                return False
            visiting.add(category_id)
            if any(walk(parent) for parent in parents.get(category_id, ())):
                return True
            visiting.remove(category_id)
            visited.add(category_id)
            return False

        return (
            ["category registry parent graph must be acyclic"]
            if any(walk(category_id) for category_id in parents)
            else []
        )

    def get(self, category_id: str) -> TaskCategory:
        for category in self.categories:
            if category.id == category_id:
                return category
        raise KeyError(category_id)

    def classify(
        self, contract: TaskContract, *, limit: int | None = 12
    ) -> tuple[TaskCategoryMatch, ...]:
        """Return transparent lexical/declared priors, not semantic truth."""
        if limit is not None and limit <= 0:
            raise ValueError("category match limit must be positive or null")
        declared = set(contract.tags)
        extension_values = dict(contract.extensions)
        for key in ("task.family", "task.subfamily"):
            value = extension_values.get(key)
            if isinstance(value, str):
                declared.add(value)
        text_parts = [
            contract.title,
            contract.intent,
            contract.success_contract,
            *contract.tags,
            *contract.external_requirements,
        ]
        for key in ("task.family", "task.subfamily", "semantic.domain_labels"):
            value = extension_values.get(key)
            if isinstance(value, str):
                text_parts.append(value)
            elif isinstance(value, (list, tuple)):
                text_parts.extend(str(item) for item in value)
        normalized = " ".join(text_parts).casefold().replace("_", "-")

        matches: list[TaskCategoryMatch] = []
        for category in self.categories:
            exact = category.id in declared
            terms = tuple(
                sorted(
                    {
                        term
                        for term in (*category.aliases, *category.signal_terms, category.title)
                        if term.strip() and term.casefold().replace("_", "-") in normalized
                    }
                )
            )
            if not exact and not terms:
                continue
            denominator = max(2, min(6, len(category.signal_terms) or 2))
            lexical = min(1.0, len(terms) / denominator)
            score = 1.0 if exact else max(0.2, lexical)
            matches.append(
                TaskCategoryMatch(
                    category.id,
                    score,
                    terms or (category.id,),
                    "evidence.declared" if exact else "evidence.inferred",
                )
            )
        by_id = {match.category_id: match for match in matches}
        frontier = list(matches)
        while frontier:
            child = frontier.pop()
            for parent_id in self.get(child.category_id).parent_ids:
                score = child.score * 0.85
                inherited = TaskCategoryMatch(
                    parent_id,
                    score,
                    (f"ancestor-of:{child.category_id}",),
                    "evidence.inferred",
                )
                current = by_id.get(parent_id)
                if current is None or inherited.score > current.score:
                    by_id[parent_id] = inherited
                    frontier.append(inherited)
        matches = sorted(by_id.values(), key=lambda item: (-item.score, item.category_id))
        return tuple(matches if limit is None else matches[:limit])

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_category_model_version": TASK_CATEGORY_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "description": self.description,
            "categories": [category.to_dict() for category in self.categories],
            "extensions": dict(self.extensions),
        }


def _category(
    category_id: str,
    title: str,
    parent: str | tuple[str, ...] = (),
    terms: tuple[str, ...] = (),
    *,
    templates: tuple[str, ...] = (),
) -> TaskCategory:
    parents = (parent,) if isinstance(parent, str) else parent
    return TaskCategory(
        id=category_id,
        title=title,
        description=f"Composable DAG work for {title.casefold()}.",
        parent_ids=parents,
        signal_terms=terms,
        template_ids=templates,
    )


# A broad cold-start catalog.  It is data, not a closed enum: downstream
# packages can replace it, merge it, or add any namespaced category.
COMMON_DAG_TASK_CATEGORIES = (
    _category("dag.acquire", "Data acquisition", terms=("ingest", "collect", "acquire")),
    _category("dag.prepare", "Data preparation", terms=("prepare", "preprocess")),
    _category("dag.integrate", "Data integration", terms=("integrate", "combine")),
    _category("dag.generate", "Data and artifact generation", terms=("generate", "synthesize")),
    _category("dag.learn", "Model learning and inference", terms=("train", "predict", "model")),
    _category("dag.evaluate", "Testing and evaluation", terms=("evaluate", "benchmark", "test")),
    _category("dag.serve", "Serving and delivery", terms=("serve", "api", "deliver")),
    _category(
        "dag.operate", "Operations and reliability", terms=("operate", "monitor", "incident")
    ),
    _category("dag.govern", "Governance and assurance", terms=("govern", "audit", "policy")),
    _category("dag.human", "Human review and collaboration", terms=("human review", "annotation")),
    _category(
        "dag.acquire.batch",
        "Batch ingestion",
        "dag.acquire",
        ("batch ingestion", "files"),
        templates=("template.batch-data-pipeline",),
    ),
    _category(
        "dag.acquire.stream",
        "Streaming ingestion",
        "dag.acquire",
        ("stream", "event time", "cdc"),
        templates=("template.event-driven-system",),
    ),
    _category(
        "dag.acquire.web",
        "Web and API acquisition",
        "dag.acquire",
        ("scrape", "crawl", "api feed"),
        templates=("template.web-automation",),
    ),
    _category(
        "dag.acquire.document",
        "Document and media ingestion",
        "dag.acquire",
        ("document", "pdf", "image", "audio"),
        templates=("template.document-intelligence",),
    ),
    _category(
        "dag.prepare.parse", "Parsing and decoding", "dag.prepare", ("parse", "decode", "extract")
    ),
    _category(
        "dag.prepare.schema",
        "Schema discovery and typing",
        "dag.prepare",
        ("schema inference", "type inference", "schema"),
    ),
    _category(
        "dag.prepare.profile",
        "Data profiling",
        "dag.prepare",
        ("profile", "statistics", "data shape"),
    ),
    _category(
        "dag.prepare.clean",
        "Data cleaning and repair",
        "dag.prepare",
        ("clean", "repair", "missing values"),
        templates=("template.data-quality",),
    ),
    _category(
        "dag.prepare.impute",
        "Missing-data imputation",
        "dag.prepare",
        ("imputation", "fill missing", "missing data"),
    ),
    _category(
        "dag.prepare.outlier",
        "Outlier diagnosis and treatment",
        "dag.prepare",
        ("outlier treatment", "winsorize", "robust statistics"),
    ),
    _category(
        "dag.prepare.conflict",
        "Conflicting-data adjudication",
        "dag.prepare",
        ("conflicting data", "source disagreement", "adjudicate records"),
    ),
    _category(
        "dag.prepare.verify",
        "Data verification and validation",
        "dag.prepare",
        ("verify", "validate", "quality checks"),
        templates=("template.data-quality",),
    ),
    _category(
        "dag.prepare.normalize",
        "Normalization and standardization",
        "dag.prepare",
        ("normalize", "standardize", "canonicalize"),
    ),
    _category(
        "dag.prepare.deduplicate",
        "Deduplication",
        "dag.prepare",
        ("deduplicate", "duplicate records", "near duplicate"),
    ),
    _category(
        "dag.prepare.entity-resolution",
        "Entity resolution",
        "dag.prepare",
        ("entity resolution", "record linkage", "golden record"),
    ),
    _category(
        "dag.prepare.split",
        "Sampling and split construction",
        "dag.prepare",
        ("train test split", "cross validation", "sampling"),
    ),
    _category(
        "dag.integrate.join",
        "Join and data fusion",
        "dag.integrate",
        ("join", "merge", "data fusion"),
        templates=("template.batch-data-pipeline",),
    ),
    _category(
        "dag.integrate.reconcile",
        "Reconciliation",
        "dag.integrate",
        ("reconcile", "ledger", "cross-source"),
    ),
    _category(
        "dag.integrate.aggregate",
        "Aggregation and summarization",
        "dag.integrate",
        ("aggregate", "summarize", "rollup"),
    ),
    _category(
        "dag.integrate.enrich",
        "Data enrichment",
        "dag.integrate",
        ("enrich", "append attributes", "reference data"),
    ),
    _category(
        "dag.integrate.enrich.temporal",
        "Temporal enrichment",
        "dag.integrate.enrich",
        ("event on date", "calendar enrichment", "as-of"),
    ),
    _category(
        "dag.integrate.enrich.geospatial",
        "Geospatial enrichment",
        "dag.integrate.enrich",
        ("geocode", "gis", "spatial enrichment"),
        templates=("template.geospatial-analytics",),
    ),
    _category(
        "dag.integrate.enrich.geotemporal",
        "Geospatial and temporal enrichment",
        ("dag.integrate.enrich.geospatial", "dag.integrate.enrich.temporal"),
        ("geotemporal", "city on date", "location and time"),
    ),
    _category(
        "dag.integrate.enrich.identity",
        "Identity and reference enrichment",
        "dag.integrate.enrich",
        ("name enrichment", "address enrichment", "postal enrichment", "company enrichment"),
    ),
    _category(
        "dag.integrate.enrich.knowledge",
        "Knowledge enrichment",
        "dag.integrate.enrich",
        ("knowledge graph", "external knowledge", "rag"),
        templates=("template.knowledge-retrieval",),
    ),
    _category(
        "dag.generate.synthetic",
        "Synthetic data generation",
        "dag.generate",
        ("synthetic data", "simulation", "generative data"),
    ),
    _category(
        "dag.generate.synthetic.tabular",
        "Synthetic tabular data",
        "dag.generate.synthetic",
        ("synthetic table", "tabular synthesizer", "privacy utility"),
    ),
    _category(
        "dag.generate.synthetic.text",
        "Synthetic text and instruction data",
        "dag.generate.synthetic",
        ("synthetic text", "self instruct", "instruction data"),
    ),
    _category(
        "dag.generate.synthetic.media",
        "Synthetic image, audio, and multimodal data",
        "dag.generate.synthetic",
        ("synthetic image", "synthetic audio", "multimodal generation"),
    ),
    _category(
        "dag.generate.synthetic.adversarial",
        "Synthetic adversarial and red-team data",
        "dag.generate.synthetic",
        ("adversarial prompts", "hard negatives", "hostile documents"),
    ),
    _category(
        "dag.generate.augmentation",
        "Data augmentation",
        "dag.generate",
        ("augmentation", "perturbation", "counterfactual examples"),
    ),
    _category(
        "dag.generate.label",
        "Label and annotation generation",
        "dag.generate",
        ("label generation", "weak supervision", "annotation"),
    ),
    _category(
        "dag.generate.scenario",
        "Scenario and test-case generation",
        "dag.generate",
        ("scenario generation", "test cases", "adversarial cases"),
    ),
    _category(
        "dag.generate.report",
        "Report and artifact generation",
        "dag.generate",
        ("report", "artifact", "submission"),
    ),
    _category(
        "dag.learn.feature",
        "Feature engineering",
        "dag.learn",
        ("feature engineering", "transform features"),
    ),
    _category(
        "dag.learn.linear",
        "Linear and generalized linear models",
        "dag.learn",
        ("linear model", "logistic regression", "generalized linear"),
    ),
    _category(
        "dag.learn.tree",
        "Tree and random-forest models",
        "dag.learn",
        ("decision tree", "random forest", "extra trees"),
    ),
    _category(
        "dag.learn.boosted-tree",
        "Boosted-tree models",
        "dag.learn",
        ("gradient boosting", "boosted tree", "xgboost", "lightgbm"),
    ),
    _category(
        "dag.learn.neural",
        "Neural and multilayer perceptron models",
        "dag.learn",
        ("neural network", "mlp", "deep learning"),
    ),
    _category(
        "dag.learn.transformer",
        "Transformer and attention models",
        "dag.learn",
        ("transformer", "attention model", "foundation model"),
    ),
    _category(
        "dag.learn.tabular-attention",
        "Tabular attention models",
        "dag.learn",
        ("tabular transformer", "tabular attention", "ft transformer"),
    ),
    _category(
        "dag.learn.reinforcement",
        "Reinforcement and preference learning",
        "dag.learn",
        ("reinforcement learning", "reward model", "policy optimization", "rlhf"),
    ),
    _category(
        "dag.learn.embedding",
        "Representation and embedding",
        "dag.learn",
        ("embedding", "representation learning"),
    ),
    _category(
        "dag.learn.selection",
        "Feature and representation selection",
        "dag.learn",
        ("feature selection", "dimensionality reduction"),
    ),
    _category(
        "dag.learn.regression",
        "Regression",
        "dag.learn",
        ("regression", "continuous target", "rmse"),
        templates=("template.kaggle-tabular",),
    ),
    _category(
        "dag.learn.classification",
        "Classification",
        "dag.learn",
        ("classification", "class label", "auc", "f1"),
        templates=("template.kaggle-tabular",),
    ),
    _category(
        "dag.learn.ranking",
        "Ranking and recommendation",
        "dag.learn",
        ("ranking", "recommendation", "ndcg"),
        templates=("template.recommendation-ranking",),
    ),
    _category(
        "dag.learn.forecast",
        "Forecasting",
        "dag.learn",
        ("forecast", "time series", "horizon"),
        templates=("template.time-series-forecasting",),
    ),
    _category(
        "dag.learn.cluster",
        "Clustering and segmentation",
        "dag.learn",
        ("clustering", "segmentation", "unsupervised"),
    ),
    _category(
        "dag.learn.anomaly",
        "Anomaly and novelty detection",
        "dag.learn",
        ("anomaly", "outlier detection", "novelty"),
    ),
    _category(
        "dag.learn.graph",
        "Graph and relational learning",
        "dag.learn",
        ("graph neural", "link prediction", "graph prediction"),
    ),
    _category(
        "dag.learn.causal",
        "Causal inference and experimentation",
        "dag.learn",
        ("causal", "treatment effect", "experiment"),
        templates=("template.scientific-experiment",),
    ),
    _category(
        "dag.learn.optimize",
        "Optimization, planning, and control",
        "dag.learn",
        ("optimization", "schedule", "control policy"),
        templates=("template.optimization-scheduling",),
    ),
    _category(
        "dag.learn.ensemble",
        "Ensembling and stacking",
        "dag.learn",
        ("ensemble", "stacking", "blend"),
    ),
    _category(
        "dag.learn.uncertainty",
        "Calibration and uncertainty",
        "dag.learn",
        ("calibration", "prediction interval", "conformal", "uncertainty"),
    ),
    _category(
        "dag.learn.llm",
        "LLM inference and generation",
        "dag.learn",
        ("llm", "language model", "prompt"),
    ),
    _category(
        "dag.learn.rag",
        "Retrieval-augmented generation",
        "dag.learn",
        ("rag", "retrieval augmented", "grounded answer"),
        templates=("template.knowledge-retrieval",),
    ),
    _category(
        "dag.learn.finetune",
        "Model fine-tuning and adaptation",
        "dag.learn",
        ("fine-tune", "lora", "preference optimization"),
    ),
    _category(
        "dag.evaluate.data",
        "Data-quality evaluation",
        "dag.evaluate",
        ("data quality evaluation", "schema tests", "data contract"),
    ),
    _category(
        "dag.evaluate.model",
        "Model evaluation",
        "dag.evaluate",
        ("model evaluation", "offline evaluation", "holdout"),
    ),
    _category(
        "dag.evaluate.regression",
        "Software and behavior regression testing",
        "dag.evaluate",
        ("regression test", "golden test", "snapshot test"),
    ),
    _category(
        "dag.evaluate.metamorphic",
        "Metamorphic and counterfactual testing",
        "dag.evaluate",
        ("metamorphic test", "counterfactual test", "invariance test"),
    ),
    _category(
        "dag.evaluate.judge",
        "Judge and grader evaluation",
        "dag.evaluate",
        ("llm as judge", "judge calibration", "grader evaluation"),
    ),
    _category(
        "dag.evaluate.llm-harness",
        "LLM test and evaluation harness",
        "dag.evaluate",
        ("llm evaluation", "eval harness", "grader", "judge model"),
    ),
    _category(
        "dag.evaluate.rag",
        "Retrieval and RAG evaluation",
        "dag.evaluate",
        ("rag evaluation", "retrieval evaluation", "faithfulness"),
    ),
    _category(
        "dag.evaluate.agent",
        "Agent and tool-use evaluation",
        "dag.evaluate",
        ("agent evaluation", "tool use", "trajectory evaluation"),
    ),
    _category(
        "dag.evaluate.safety",
        "Safety, red-team, and adversarial evaluation",
        "dag.evaluate",
        ("red team", "jailbreak", "safety evaluation", "adversarial"),
    ),
    _category(
        "dag.evaluate.human",
        "Human and panel evaluation",
        "dag.evaluate",
        ("human evaluation", "blind review", "panel"),
    ),
    _category(
        "dag.evaluate.online",
        "Online experimentation",
        "dag.evaluate",
        ("a/b test", "online experiment", "interleaving"),
    ),
    _category(
        "dag.evaluate.outer",
        "Sealed outer evaluation",
        "dag.evaluate",
        ("outer evaluation", "hidden holdout", "independent evaluator"),
    ),
    _category(
        "dag.serve.api",
        "API and service execution",
        "dag.serve",
        ("api service", "endpoint", "inference service"),
        templates=("template.api-service",),
    ),
    _category(
        "dag.serve.frontend",
        "Frontend application pipeline",
        "dag.serve",
        ("frontend", "web ui", "client application"),
    ),
    _category(
        "dag.serve.backend",
        "Backend and service pipeline",
        "dag.serve",
        ("backend", "service orchestration", "business logic"),
    ),
    _category(
        "dag.serve.plugin",
        "Skill, plugin, and tool integration",
        "dag.serve",
        ("plugin", "skill", "tool integration", "mcp server"),
    ),
    _category(
        "dag.serve.automation",
        "Workflow and browser automation",
        "dag.serve",
        ("automation", "browser", "workflow"),
        templates=("template.web-automation",),
    ),
    _category(
        "dag.serve.deploy",
        "Deployment and release",
        "dag.serve",
        ("deploy", "release", "rollout"),
        templates=("template.deployment-release",),
    ),
    _category(
        "dag.operate.observe",
        "Observability and monitoring",
        "dag.operate",
        ("observability", "monitoring", "telemetry"),
        templates=("template.observability-sre",),
    ),
    _category(
        "dag.operate.incident",
        "Incident detection and response",
        "dag.operate",
        ("incident", "triage", "response"),
        templates=("template.incident-response",),
    ),
    _category(
        "dag.operate.migrate",
        "Migration and backfill",
        "dag.operate",
        ("migration", "backfill", "cutover"),
        templates=("template.database-migration",),
    ),
    _category(
        "dag.govern.privacy",
        "Privacy and de-identification",
        "dag.govern",
        ("privacy", "pii", "redaction"),
    ),
    _category(
        "dag.govern.security",
        "Security assurance",
        "dag.govern",
        ("security", "vulnerability", "threat"),
        templates=("template.cybersecurity-investigation",),
    ),
    _category(
        "dag.govern.compliance",
        "Compliance and evidence",
        "dag.govern",
        ("compliance", "control evidence", "audit"),
        templates=("template.compliance-evidence",),
    ),
    _category(
        "dag.govern.provenance",
        "Provenance and lineage",
        "dag.govern",
        ("provenance", "lineage", "receipt"),
    ),
    _category(
        "dag.human.annotate",
        "Human annotation",
        "dag.human",
        ("human annotation", "labeling queue"),
    ),
    _category(
        "dag.human.review",
        "Human review and approval",
        "dag.human",
        ("human review", "approval", "escalation"),
    ),
)

DEFAULT_TASK_CATEGORY_REGISTRY = TaskCategoryRegistry(
    id="registry.common-dag-task-categories",
    version="0.1",
    categories=COMMON_DAG_TASK_CATEGORIES,
    description=(
        "Extensible multi-label cold-start vocabulary for common data, ML, LLM, "
        "software, evaluation, and operational DAG tasks."
    ),
)


__all__ = [
    "COMMON_DAG_TASK_CATEGORIES",
    "DEFAULT_TASK_CATEGORY_REGISTRY",
    "TASK_CATEGORY_MODEL_VERSION",
    "TaskCategory",
    "TaskCategoryMatch",
    "TaskCategoryRegistry",
]
