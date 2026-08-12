"""Portable contracts for matched LLM coding-harness experiments.

The agent benchmark layer compares systems that *author* candidate artifacts.
It does not make generated code compiler-valid, safe, or correct.  Exact task,
context, harness, model, budget, evaluator, and receipt identities remain
separate so a report can distinguish mechanism checks from real evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from solutiongraph.model import DIGEST_RE, ID_RE, canonical_json, sha256_digest

AGENT_BENCH_MODEL_VERSION = "0.1"
AGENT_BENCH_CONDITIONS = ("control", "solutiongraph")
AGENT_BENCH_CLAIM_SCOPES = (
    "mechanism-fixture",
    "internal-dataset",
    "public-benchmark",
    "production-shadow",
)
AGENT_BENCH_HARNESS_KINDS = ("fixture", "command")
AGENT_BENCH_SIZE_CLASSES = ("tiny", "small", "medium", "large", "frontier", "unknown")
TRIAL_LIFECYCLE = ("ATTEMPTED", "DELIVERED", "VALID", "SCORED", "ACCEPTED")
DECISION_LIFECYCLE = ("SELECTED", "WINNER", "PROMOTED")


def _unique_namespaced(values: tuple[str, ...], label: str) -> list[str]:
    problems: list[str] = []
    if len(values) != len(set(values)):
        problems.append(f"{label} must be unique")
    if any(not ID_RE.fullmatch(value) for value in values):
        problems.append(f"{label} must contain namespaced identifiers")
    return problems


@dataclass(frozen=True)
class AgentCaseSpec:
    """Content identity and candidate visibility for one benchmark case."""

    id: str
    split: str
    input_digest: str
    expected_digest: str
    candidate_readable: bool
    tags: tuple[str, ...] = ()

    def validate(self, path: str = "case") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if self.split not in ("development", "validation", "holdout", "stress"):
            problems.append(f"{path}.split is not supported")
        if not DIGEST_RE.fullmatch(self.input_digest):
            problems.append(f"{path}.input_digest must be a sha256 digest")
        if not DIGEST_RE.fullmatch(self.expected_digest):
            problems.append(f"{path}.expected_digest must be a sha256 digest")
        if len(self.tags) != len(set(self.tags)):
            problems.append(f"{path}.tags must be unique")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "split": self.split,
            "input_digest": self.input_digest,
            "expected_digest": self.expected_digest,
            "candidate_readable": self.candidate_readable,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class AgentTaskSpec:
    """One implementation-neutral coding task and fixed evaluation boundary."""

    id: str
    version: str
    title: str
    summary: str
    instructions: str
    input_contract: str
    output_contract: str
    success_contract: str
    categories: tuple[str, ...]
    template_id: str
    stages: tuple[str, ...]
    cases: tuple[AgentCaseSpec, ...]
    oracle_id: str
    oracle_digest: str
    score_metric: str = "oracle_score"
    score_direction: str = "maximize"
    acceptance_threshold: float = 1.0
    context_sources: tuple[str, ...] = ()
    allowed_imports: tuple[str, ...] = ()
    required_artifacts: tuple[str, ...] = (
        "solution.py",
        "SOLUTION.md",
        "solution.mmd",
    )
    claim_scope: str = "mechanism-fixture"
    limitations: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    @property
    def public_case_ids(self) -> tuple[str, ...]:
        return tuple(case.id for case in self.cases if case.candidate_readable)

    @property
    def sealed_case_ids(self) -> tuple[str, ...]:
        return tuple(case.id for case in self.cases if not case.candidate_readable)

    def validate(self, path: str = "task") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not self.version.strip():
            problems.append(f"{path}.version must not be empty")
        if any(
            not value.strip()
            for value in (
                self.title,
                self.summary,
                self.instructions,
                self.input_contract,
                self.output_contract,
                self.success_contract,
            )
        ):
            problems.append(
                f"{path}.title, summary, instructions, and contracts must not be empty"
            )
        problems.extend(_unique_namespaced(self.categories, f"{path}.categories"))
        if not ID_RE.fullmatch(self.template_id):
            problems.append(f"{path}.template_id must be a namespaced identifier")
        if not self.stages or len(self.stages) != len(set(self.stages)):
            problems.append(f"{path}.stages must contain unique stage labels")
        if not self.cases:
            problems.append(f"{path}.cases must not be empty")
        case_ids = tuple(case.id for case in self.cases)
        problems.extend(_unique_namespaced(case_ids, f"{path}.case ids"))
        for index, case in enumerate(self.cases):
            problems.extend(case.validate(f"{path}.cases[{index}]"))
        if not self.public_case_ids:
            problems.append(f"{path} must include at least one candidate-readable case")
        if not self.sealed_case_ids:
            problems.append(f"{path} must include at least one candidate-unreadable case")
        if not ID_RE.fullmatch(self.oracle_id):
            problems.append(f"{path}.oracle_id must be a namespaced identifier")
        if not DIGEST_RE.fullmatch(self.oracle_digest):
            problems.append(f"{path}.oracle_digest must be a sha256 digest")
        if not ID_RE.fullmatch(self.score_metric):
            problems.append(f"{path}.score_metric must be a namespaced identifier")
        if self.score_direction not in ("maximize", "minimize"):
            problems.append(f"{path}.score_direction must be maximize or minimize")
        if not isfinite(self.acceptance_threshold):
            problems.append(f"{path}.acceptance_threshold must be finite")
        if len(self.context_sources) != len(set(self.context_sources)):
            problems.append(f"{path}.context_sources must be unique")
        if any(source.startswith(("/", "../")) for source in self.context_sources):
            problems.append(f"{path}.context_sources must be repository-relative")
        if len(self.allowed_imports) != len(set(self.allowed_imports)):
            problems.append(f"{path}.allowed_imports must be unique")
        if (
            not self.required_artifacts
            or len(self.required_artifacts) != len(set(self.required_artifacts))
            or any(name.startswith(("/", "../")) for name in self.required_artifacts)
        ):
            problems.append(f"{path}.required_artifacts must be unique relative paths")
        if self.claim_scope not in AGENT_BENCH_CLAIM_SCOPES:
            problems.append(f"{path}.claim_scope is not supported")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_bench_model_version": AGENT_BENCH_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "summary": self.summary,
            "instructions": self.instructions,
            "input_contract": self.input_contract,
            "output_contract": self.output_contract,
            "success_contract": self.success_contract,
            "categories": list(self.categories),
            "template_id": self.template_id,
            "stages": list(self.stages),
            "cases": [case.to_dict() for case in self.cases],
            "oracle_id": self.oracle_id,
            "oracle_digest": self.oracle_digest,
            "score_metric": self.score_metric,
            "score_direction": self.score_direction,
            "acceptance_threshold": self.acceptance_threshold,
            "context_sources": list(self.context_sources),
            "allowed_imports": list(self.allowed_imports),
            "required_artifacts": list(self.required_artifacts),
            "claim_scope": self.claim_scope,
            "limitations": list(self.limitations),
        }

    def mermaid(self) -> str:
        lines = ["flowchart LR", "    input([Task input])"]
        previous = "input"
        for index, stage in enumerate(self.stages, start=1):
            node = f"stage{index}"
            label = stage.replace('"', "'")
            lines.append(f'    {node}["{label}"]')
            lines.append(f"    {previous} --> {node}")
            previous = node
        lines.append("    output([Verified output])")
        lines.append(f"    {previous} --> output")
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class ModelProfile:
    """Exact model label supplied by the operator; no capability is inferred."""

    id: str
    provider: str
    model: str
    revision: str
    size_class: str = "unknown"
    context_window: int | None = None
    settings: tuple[tuple[str, str | int | float | bool | None], ...] = ()
    enabled: bool = True
    notes: str = ""

    def validate(self, path: str = "model") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if not self.provider.strip() or not self.model.strip() or not self.revision.strip():
            problems.append(f"{path}.provider, model, and revision must not be empty")
        if self.size_class not in AGENT_BENCH_SIZE_CLASSES:
            problems.append(f"{path}.size_class is not supported")
        if self.context_window is not None and self.context_window <= 0:
            problems.append(f"{path}.context_window must be positive or null")
        setting_names = tuple(name for name, _ in self.settings)
        if len(setting_names) != len(set(setting_names)) or any(
            not name.strip() for name in setting_names
        ):
            problems.append(f"{path}.settings must use unique non-empty names")
        if any(
            not isinstance(value, (str, int, float, bool, type(None)))
            or (isinstance(value, float) and not isfinite(value))
            for _, value in self.settings
        ):
            problems.append(f"{path}.settings values must be finite JSON scalars")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider,
            "model": self.model,
            "revision": self.revision,
            "size_class": self.size_class,
            "context_window": self.context_window,
            "settings": dict(self.settings),
            "enabled": self.enabled,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class HarnessProfile:
    """One no-shell CLI adapter or the deterministic reference fixture."""

    id: str
    kind: str
    version: str
    command_argv: tuple[str, ...] = ()
    compatible_model_ids: tuple[str, ...] = ()
    environment_allowlist: tuple[str, ...] = ()
    enabled: bool = True
    isolation: str = "external-unspecified"
    notes: str = ""

    def validate(self, path: str = "harness") -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"{path}.id must be a namespaced identifier")
        if self.kind not in AGENT_BENCH_HARNESS_KINDS:
            problems.append(f"{path}.kind is not supported")
        if not self.version.strip():
            problems.append(f"{path}.version must not be empty")
        if self.kind == "command" and not self.command_argv:
            problems.append(f"{path}.command_argv is required for command harnesses")
        if self.kind == "fixture" and self.command_argv:
            problems.append(f"{path}.fixture harnesses cannot declare command_argv")
        problems.extend(
            _unique_namespaced(self.compatible_model_ids, f"{path}.compatible_model_ids")
        )
        allowed_placeholders = {
            "{condition}",
            "{model}",
            "{model_id}",
            "{prompt}",
            "{prompt_file}",
            "{seed}",
            "{task_id}",
            "{workspace}",
        }
        for argument in self.command_argv:
            fields = {"{" + item.split("}", 1)[0] + "}" for item in argument.split("{")[1:]}
            if fields - allowed_placeholders:
                problems.append(
                    f"{path}.command_argv contains unsupported placeholders: "
                    + ", ".join(sorted(fields - allowed_placeholders))
                )
        if len(self.environment_allowlist) != len(set(self.environment_allowlist)):
            problems.append(f"{path}.environment_allowlist must be unique")
        if any(not name or "=" in name or "\x00" in name for name in self.environment_allowlist):
            problems.append(f"{path}.environment_allowlist contains an invalid name")
        if not self.isolation.strip():
            problems.append(f"{path}.isolation must not be empty")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "version": self.version,
            "command_argv": list(self.command_argv),
            "compatible_model_ids": list(self.compatible_model_ids),
            "environment_allowlist": list(self.environment_allowlist),
            "enabled": self.enabled,
            "isolation": self.isolation,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class AgentTrialBudget:
    """Comparable resource declaration for every arm in a paired cell."""

    max_wall_seconds: float
    max_output_bytes: int = 1_000_000
    max_context_bytes: int | None = None
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_cost_units: float | None = None

    def validate(self, path: str = "budget") -> list[str]:
        problems: list[str] = []
        if not isfinite(self.max_wall_seconds) or self.max_wall_seconds <= 0:
            problems.append(f"{path}.max_wall_seconds must be finite and positive")
        if self.max_output_bytes <= 0:
            problems.append(f"{path}.max_output_bytes must be positive")
        for label, value in (
            ("max_context_bytes", self.max_context_bytes),
            ("max_input_tokens", self.max_input_tokens),
            ("max_output_tokens", self.max_output_tokens),
        ):
            if value is not None and value <= 0:
                problems.append(f"{path}.{label} must be positive or null")
        if self.max_cost_units is not None and (
            not isfinite(self.max_cost_units) or self.max_cost_units <= 0
        ):
            problems.append(f"{path}.max_cost_units must be finite and positive or null")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_wall_seconds": self.max_wall_seconds,
            "max_output_bytes": self.max_output_bytes,
            "max_context_bytes": self.max_context_bytes,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "max_cost_units": self.max_cost_units,
        }


@dataclass(frozen=True)
class AgentBenchmarkSuite:
    """Frozen task × condition × harness × model × seed allocation."""

    id: str
    version: str
    title: str
    task_ids: tuple[str, ...]
    conditions: tuple[str, ...]
    harnesses: tuple[HarnessProfile, ...]
    models: tuple[ModelProfile, ...]
    seeds: tuple[int, ...]
    repetitions: int
    budget: AgentTrialBudget
    claim_scope: str = "mechanism-fixture"
    bootstrap_resamples: int = 2_000
    confidence_level: float = 0.95
    practical_effect: float = 0.02
    acceptance_noninferiority_margin: float = 0.0
    allow_promotion: bool = False
    limitations: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    @property
    def enabled_harnesses(self) -> tuple[HarnessProfile, ...]:
        return tuple(item for item in self.harnesses if item.enabled)

    @property
    def enabled_models(self) -> tuple[ModelProfile, ...]:
        return tuple(item for item in self.models if item.enabled)

    def models_for_harness(self, harness: HarnessProfile) -> tuple[ModelProfile, ...]:
        """Return only explicitly compatible enabled models for one harness."""
        if not harness.compatible_model_ids:
            return self.enabled_models
        compatible = set(harness.compatible_model_ids)
        return tuple(item for item in self.enabled_models if item.id in compatible)

    @property
    def total_trials(self) -> int:
        compatible_pairs = sum(
            len(self.models_for_harness(harness)) for harness in self.enabled_harnesses
        )
        return (
            len(self.task_ids)
            * len(self.conditions)
            * compatible_pairs
            * len(self.seeds)
            * self.repetitions
        )

    def validate(self, task_ids: tuple[str, ...] | None = None) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append("suite.id must be a namespaced identifier")
        if not self.version.strip() or not self.title.strip():
            problems.append("suite.version and title must not be empty")
        problems.extend(_unique_namespaced(self.task_ids, "suite.task_ids"))
        if task_ids is not None:
            unknown = sorted(set(self.task_ids) - set(task_ids))
            if unknown:
                problems.append("suite.task_ids contains unknown tasks: " + ", ".join(unknown))
        if self.conditions != AGENT_BENCH_CONDITIONS:
            problems.append("suite.conditions must be exactly control, solutiongraph")
        if not self.harnesses or not self.models:
            problems.append("suite.harnesses and models must not be empty")
        harness_ids = tuple(item.id for item in self.harnesses)
        model_ids = tuple(item.id for item in self.models)
        problems.extend(_unique_namespaced(harness_ids, "suite.harness ids"))
        problems.extend(_unique_namespaced(model_ids, "suite.model ids"))
        for index, harness in enumerate(self.harnesses):
            problems.extend(harness.validate(f"suite.harnesses[{index}]"))
        for index, model in enumerate(self.models):
            problems.extend(model.validate(f"suite.models[{index}]"))
        if not self.enabled_harnesses or not self.enabled_models:
            problems.append("suite must enable at least one harness and model")
        known_model_ids = set(model_ids)
        for index, harness in enumerate(self.harnesses):
            unknown = sorted(set(harness.compatible_model_ids) - known_model_ids)
            if unknown:
                problems.append(
                    f"suite.harnesses[{index}].compatible_model_ids contains unknown models: "
                    + ", ".join(unknown)
                )
            if harness.enabled and not self.models_for_harness(harness):
                problems.append(
                    f"suite.harnesses[{index}] has no compatible enabled model"
                )
        if not self.seeds or len(self.seeds) != len(set(self.seeds)):
            problems.append("suite.seeds must contain unique integers")
        if any(isinstance(seed, bool) or not isinstance(seed, int) for seed in self.seeds):
            problems.append("suite.seeds must contain integers")
        if self.repetitions <= 0:
            problems.append("suite.repetitions must be positive")
        problems.extend(self.budget.validate("suite.budget"))
        if self.claim_scope not in AGENT_BENCH_CLAIM_SCOPES:
            problems.append("suite.claim_scope is not supported")
        if self.bootstrap_resamples <= 0:
            problems.append("suite.bootstrap_resamples must be positive")
        if not isfinite(self.confidence_level) or not 0 < self.confidence_level < 1:
            problems.append("suite.confidence_level must be between zero and one")
        if not isfinite(self.practical_effect) or self.practical_effect < 0:
            problems.append("suite.practical_effect must be finite and non-negative")
        if (
            not isfinite(self.acceptance_noninferiority_margin)
            or not 0 <= self.acceptance_noninferiority_margin <= 1
        ):
            problems.append("suite.acceptance_noninferiority_margin must be in [0,1]")
        if self.allow_promotion and self.claim_scope == "mechanism-fixture":
            problems.append("mechanism-fixture suites cannot authorize promotion")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_bench_model_version": AGENT_BENCH_MODEL_VERSION,
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "task_ids": list(self.task_ids),
            "conditions": list(self.conditions),
            "harnesses": [item.to_dict() for item in self.harnesses],
            "models": [item.to_dict() for item in self.models],
            "seeds": list(self.seeds),
            "repetitions": self.repetitions,
            "budget": self.budget.to_dict(),
            "claim_scope": self.claim_scope,
            "bootstrap_resamples": self.bootstrap_resamples,
            "confidence_level": self.confidence_level,
            "practical_effect": self.practical_effect,
            "acceptance_noninferiority_margin": self.acceptance_noninferiority_margin,
            "allow_promotion": self.allow_promotion,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class TrialPlan:
    """One exact matched-cell allocation before a harness executes."""

    id: str
    suite_digest: str
    task_id: str
    task_digest: str
    condition: str
    harness_id: str
    harness_version: str
    model_id: str
    model_revision: str
    seed: int
    repetition: int
    budget: AgentTrialBudget

    @property
    def pairing_key(self) -> tuple[str, str, str, int, int]:
        return (self.task_id, self.harness_id, self.model_id, self.seed, self.repetition)

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems: list[str] = []
        for label, value in (
            ("id", self.id),
            ("task_id", self.task_id),
            ("harness_id", self.harness_id),
            ("model_id", self.model_id),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"trial.{label} must be a namespaced identifier")
        for label, value in (("suite_digest", self.suite_digest), ("task_digest", self.task_digest)):
            if not DIGEST_RE.fullmatch(value):
                problems.append(f"trial.{label} must be a sha256 digest")
        if self.condition not in AGENT_BENCH_CONDITIONS:
            problems.append("trial.condition is not supported")
        if not self.harness_version.strip() or not self.model_revision.strip():
            problems.append("trial harness/model revisions must not be empty")
        if self.repetition < 0:
            problems.append("trial.repetition must be non-negative")
        problems.extend(self.budget.validate("trial.budget"))
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "suite_digest": self.suite_digest,
            "task_id": self.task_id,
            "task_digest": self.task_digest,
            "condition": self.condition,
            "harness_id": self.harness_id,
            "harness_version": self.harness_version,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "seed": self.seed,
            "repetition": self.repetition,
            "budget": self.budget.to_dict(),
        }


@dataclass(frozen=True)
class TrialArtifact:
    path: str
    digest: str
    size_bytes: int

    def validate(self, path: str = "artifact") -> list[str]:
        problems: list[str] = []
        if not self.path or self.path.startswith(("/", "../")):
            problems.append(f"{path}.path must be relative")
        if not DIGEST_RE.fullmatch(self.digest):
            problems.append(f"{path}.digest must be a sha256 digest")
        if self.size_bytes < 0:
            problems.append(f"{path}.size_bytes must be non-negative")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "digest": self.digest, "size_bytes": self.size_bytes}


@dataclass(frozen=True)
class AgentTrialReceipt:
    """Immutable observation from delivery through independent scoring."""

    id: str
    plan: TrialPlan
    plan_digest: str
    prompt_digest: str
    context_digest: str
    context_bytes: int
    workspace_manifest_digest: str
    lifecycle: tuple[str, ...]
    started_at: str
    ended_at: str
    wall_seconds: float
    exit_code: int | None
    timed_out: bool
    command_digest: str
    stdout_digest: str
    stderr_digest: str
    artifacts: tuple[TrialArtifact, ...]
    metrics: tuple[tuple[str, float], ...]
    accepted: bool
    problems: tuple[str, ...] = ()
    environment_variable_names: tuple[str, ...] = ()
    budget_enforcement: tuple[str, ...] = ()
    isolation: str = "external-unspecified"

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    @property
    def metric_map(self) -> dict[str, float]:
        return dict(self.metrics)

    def validate(self) -> list[str]:
        problems = self.plan.validate()
        if not ID_RE.fullmatch(self.id):
            problems.append("receipt.id must be a namespaced identifier")
        for label, value in (
            ("plan_digest", self.plan_digest),
            ("prompt_digest", self.prompt_digest),
            ("context_digest", self.context_digest),
            ("workspace_manifest_digest", self.workspace_manifest_digest),
            ("command_digest", self.command_digest),
            ("stdout_digest", self.stdout_digest),
            ("stderr_digest", self.stderr_digest),
        ):
            if not DIGEST_RE.fullmatch(value):
                problems.append(f"receipt.{label} must be a sha256 digest")
        if self.plan_digest != self.plan.digest:
            problems.append("receipt.plan_digest does not match the trial plan")
        if self.context_bytes < 0:
            problems.append("receipt.context_bytes must be non-negative")
        if not self.lifecycle or tuple(TRIAL_LIFECYCLE[: len(self.lifecycle)]) != self.lifecycle:
            problems.append("receipt.lifecycle must be an ordered prefix of the trial lifecycle")
        if self.accepted and self.lifecycle != TRIAL_LIFECYCLE:
            problems.append("accepted receipts must reach every trial lifecycle state")
        if not isfinite(self.wall_seconds) or self.wall_seconds < 0:
            problems.append("receipt.wall_seconds must be finite and non-negative")
        artifact_paths = tuple(item.path for item in self.artifacts)
        if len(artifact_paths) != len(set(artifact_paths)):
            problems.append("receipt.artifact paths must be unique")
        for index, artifact in enumerate(self.artifacts):
            problems.extend(artifact.validate(f"receipt.artifacts[{index}]"))
        metric_names = tuple(name for name, _ in self.metrics)
        if len(metric_names) != len(set(metric_names)):
            problems.append("receipt.metrics must be unique")
        if any(not ID_RE.fullmatch(name) or not isfinite(value) for name, value in self.metrics):
            problems.append("receipt.metrics must use namespaced ids and finite values")
        if len(self.environment_variable_names) != len(set(self.environment_variable_names)):
            problems.append("receipt.environment_variable_names must be unique")
        if not self.isolation.strip():
            problems.append("receipt.isolation must not be empty")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_bench_model_version": AGENT_BENCH_MODEL_VERSION,
            "id": self.id,
            "plan": self.plan.to_dict(),
            "plan_digest": self.plan_digest,
            "prompt_digest": self.prompt_digest,
            "context_digest": self.context_digest,
            "context_bytes": self.context_bytes,
            "workspace_manifest_digest": self.workspace_manifest_digest,
            "lifecycle": list(self.lifecycle),
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "wall_seconds": self.wall_seconds,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "command_digest": self.command_digest,
            "stdout_digest": self.stdout_digest,
            "stderr_digest": self.stderr_digest,
            "artifacts": [item.to_dict() for item in self.artifacts],
            "metrics": dict(self.metrics),
            "accepted": self.accepted,
            "problems": list(self.problems),
            "environment_variable_names": list(self.environment_variable_names),
            "budget_enforcement": list(self.budget_enforcement),
            "isolation": self.isolation,
        }


@dataclass(frozen=True)
class AgentDecisionRecord:
    """Selection is a separate evidence-derived event, never a receipt rewrite."""

    id: str
    state: str
    trial_receipt_ids: tuple[str, ...]
    reason: str
    authorized: bool = False

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append("decision.id must be a namespaced identifier")
        if self.state not in DECISION_LIFECYCLE:
            problems.append("decision.state is not supported")
        problems.extend(_unique_namespaced(self.trial_receipt_ids, "decision receipt ids"))
        if not self.reason.strip():
            problems.append("decision.reason must not be empty")
        if self.state == "PROMOTED" and not self.authorized:
            problems.append("PROMOTED decisions require explicit authorization")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state,
            "trial_receipt_ids": list(self.trial_receipt_ids),
            "reason": self.reason,
            "authorized": self.authorized,
        }


def task_case_spec(
    case_id: str,
    split: str,
    payload: Any,
    expected: Any,
    *,
    candidate_readable: bool,
    tags: tuple[str, ...] = (),
) -> AgentCaseSpec:
    """Build a case identity without publishing its evaluator payload."""
    return AgentCaseSpec(
        id=case_id,
        split=split,
        input_digest=sha256_digest(payload),
        expected_digest=sha256_digest(expected),
        candidate_readable=candidate_readable,
        tags=tags,
    )


def stable_trial_id(
    suite_id: str,
    task_id: str,
    condition: str,
    harness_id: str,
    model_id: str,
    seed: int,
    repetition: int,
) -> str:
    identity = canonical_json(
        [suite_id, task_id, condition, harness_id, model_id, seed, repetition]
    )
    suffix = sha256_digest(identity).removeprefix("sha256:")[:16]
    return f"agent-trial.{suffix}"


__all__ = [
    "AGENT_BENCH_CLAIM_SCOPES",
    "AGENT_BENCH_CONDITIONS",
    "AGENT_BENCH_HARNESS_KINDS",
    "AGENT_BENCH_MODEL_VERSION",
    "AGENT_BENCH_SIZE_CLASSES",
    "DECISION_LIFECYCLE",
    "TRIAL_LIFECYCLE",
    "AgentBenchmarkSuite",
    "AgentCaseSpec",
    "AgentDecisionRecord",
    "AgentTaskSpec",
    "AgentTrialBudget",
    "AgentTrialReceipt",
    "HarnessProfile",
    "ModelProfile",
    "TrialArtifact",
    "TrialPlan",
    "stable_trial_id",
    "task_case_spec",
]
