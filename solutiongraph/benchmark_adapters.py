"""Claim-safe normalization seams for external benchmark ecosystems.

Adapters in this module do not download data, submit results, or impersonate an
external authority.  They turn an explicitly versioned source manifest into a
strict ``TaskContract`` plus immutable case identities.  Credentialed fetch,
execution, evaluator isolation, and submission remain separate runtime nodes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from solutiongraph.evidence import Objective
from solutiongraph.model import DIGEST_RE, ID_RE, Port, sha256_digest
from solutiongraph.tasking import TaskCaseSpec, TaskContract, TaskOracle

EXTERNAL_BENCHMARK_MODEL_VERSION = "0.1"
EXTERNAL_CLAIM_SCOPES = (
    "mechanism-fixture",
    "internal-dataset",
    "public-benchmark",
    "production-shadow",
)


@dataclass(frozen=True)
class BenchmarkAdapterProfile:
    id: str
    source_kind: str
    default_task_family: str
    required_metadata: tuple[str, ...]
    tags: tuple[str, ...]
    default_limitations: tuple[str, ...]

    def validate(self) -> list[str]:
        problems: list[str] = []
        for label, value in (
            ("id", self.id),
            ("source_kind", self.source_kind),
            ("default_task_family", self.default_task_family),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"adapter profile {label} must be namespaced")
        for label, values in (
            ("required_metadata", self.required_metadata),
            ("tags", self.tags),
        ):
            if len(values) != len(set(values)) or any(
                not ID_RE.fullmatch(value) for value in values
            ):
                problems.append(f"adapter profile {label} must contain unique identifiers")
        if any(not item.strip() for item in self.default_limitations):
            problems.append("adapter profile limitations must not be empty")
        return problems


@dataclass(frozen=True)
class ExternalBenchmarkRequest:
    """Source manifest fields that must be fixed before adapting a benchmark."""

    task_id: str
    task_version: str
    title: str
    intent: str
    success_contract: str
    inputs: tuple[Port, ...]
    outputs: tuple[Port, ...]
    oracle: TaskOracle
    objectives: tuple[Objective, ...]
    cases: tuple[TaskCaseSpec, ...]
    source_id: str
    source_version: str
    source_uri: str
    claim_scope: str = "public-benchmark"
    task_family: str = ""
    metadata: tuple[tuple[str, Any], ...] = ()
    external_requirements: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def validate(self) -> list[str]:
        problems: list[str] = []
        for label, value in (("task_id", self.task_id), ("source_id", self.source_id)):
            if not ID_RE.fullmatch(value):
                problems.append(f"external benchmark {label} must be namespaced")
        for label, value in (
            ("task_version", self.task_version),
            ("source_version", self.source_version),
            ("title", self.title),
            ("intent", self.intent),
            ("success_contract", self.success_contract),
            ("source_uri", self.source_uri),
        ):
            if not value.strip():
                problems.append(f"external benchmark {label} must not be empty")
        if self.claim_scope not in EXTERNAL_CLAIM_SCOPES:
            problems.append("external benchmark claim_scope is unsupported")
        if self.task_family and not ID_RE.fullmatch(self.task_family):
            problems.append("external benchmark task_family must be empty or namespaced")
        if not self.inputs or not self.outputs:
            problems.append("external benchmark inputs and outputs must not be empty")
        for direction, ports in (("inputs", self.inputs), ("outputs", self.outputs)):
            names = [port.name for port in ports]
            if len(names) != len(set(names)):
                problems.append(f"external benchmark {direction} names must be unique")
            for index, port in enumerate(ports):
                problems.extend(port.validate(f"external_benchmark.{direction}[{index}]"))
        problems.extend(self.oracle.validate("external_benchmark.oracle"))
        if not self.objectives:
            problems.append("external benchmark objectives must not be empty")
        for objective in self.objectives:
            problems.extend(objective.validate())
        if not self.cases:
            problems.append("external benchmark cases must not be empty")
        case_ids = [case.id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            problems.append("external benchmark case ids must be unique")
        for index, case in enumerate(self.cases):
            problems.extend(case.validate(f"external_benchmark.cases[{index}]"))
        metadata_keys = [key for key, _ in self.metadata]
        if len(metadata_keys) != len(set(metadata_keys)) or any(
            not ID_RE.fullmatch(key) or "." not in key for key in metadata_keys
        ):
            problems.append("external benchmark metadata keys must be unique and namespaced")
        try:
            sha256_digest(dict(self.metadata))
        except (TypeError, ValueError):
            problems.append("external benchmark metadata must be JSON serialisable")
        if len(self.tags) != len(set(self.tags)) or any(
            not ID_RE.fullmatch(tag) for tag in self.tags
        ):
            problems.append("external benchmark tags must contain unique identifiers")
        if any(not item.strip() for item in (*self.external_requirements, *self.limitations)):
            problems.append("external requirements and limitations must not contain empty text")
        return problems


@dataclass(frozen=True)
class ExternalBenchmarkBundle:
    """Strict portable projection produced by one adapter profile."""

    adapter_id: str
    source_kind: str
    source_id: str
    source_version: str
    source_uri: str
    claim_scope: str
    task: TaskContract
    cases: tuple[TaskCaseSpec, ...]
    source_manifest_digest: str
    limitations: tuple[str, ...]

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    def validate(self) -> list[str]:
        problems = list(self.task.validate())
        for label, value in (
            ("adapter_id", self.adapter_id),
            ("source_kind", self.source_kind),
            ("source_id", self.source_id),
        ):
            if not ID_RE.fullmatch(value):
                problems.append(f"external bundle {label} must be namespaced")
        if not self.source_version.strip() or not self.source_uri.strip():
            problems.append("external bundle source version and URI are required")
        if self.claim_scope not in EXTERNAL_CLAIM_SCOPES:
            problems.append("external bundle claim_scope is unsupported")
        if len(self.cases) != len({case.id for case in self.cases}):
            problems.append("external bundle case ids must be unique")
        for index, case in enumerate(self.cases):
            problems.extend(case.validate(f"external_bundle.cases[{index}]"))
        if set(self.task.case_ids) != {case.id for case in self.cases}:
            problems.append("external bundle cases do not exactly close the task contract")
        if not DIGEST_RE.fullmatch(self.source_manifest_digest):
            problems.append("external bundle source_manifest_digest must be content-addressed")
        if not self.limitations or any(not item.strip() for item in self.limitations):
            problems.append("external bundle must preserve nonempty limitations")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "external_benchmark_model_version": EXTERNAL_BENCHMARK_MODEL_VERSION,
            "adapter_id": self.adapter_id,
            "source_kind": self.source_kind,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "source_uri": self.source_uri,
            "claim_scope": self.claim_scope,
            "task": self.task.to_dict(),
            "cases": [case.to_dict() for case in self.cases],
            "source_manifest_digest": self.source_manifest_digest,
            "limitations": list(self.limitations),
        }


class ExternalBenchmarkAdapter:
    """Normalize one explicit source manifest; perform no external side effects."""

    def __init__(self, profile: BenchmarkAdapterProfile) -> None:
        problems = profile.validate()
        if problems:
            raise ValueError("invalid benchmark adapter profile: " + "; ".join(problems))
        self.profile = profile

    def adapt(self, request: ExternalBenchmarkRequest) -> ExternalBenchmarkBundle:
        problems = request.validate()
        metadata = dict(request.metadata)
        missing = sorted(set(self.profile.required_metadata) - set(metadata))
        if missing:
            problems.append("external benchmark metadata is missing: " + ", ".join(missing))
        if problems:
            raise ValueError("invalid external benchmark request: " + "; ".join(problems))
        task_family = request.task_family or self.profile.default_task_family
        extensions = (
            ("task.family", task_family),
            ("benchmark.adapter-id", self.profile.id),
            ("benchmark.source-kind", self.profile.source_kind),
            ("benchmark.source-id", request.source_id),
            ("benchmark.source-version", request.source_version),
            ("benchmark.source-uri", request.source_uri),
            ("benchmark.claim-scope", request.claim_scope),
            *request.metadata,
        )
        task = TaskContract(
            id=request.task_id,
            version=request.task_version,
            title=request.title,
            intent=request.intent,
            inputs=request.inputs,
            outputs=request.outputs,
            success_contract=request.success_contract,
            oracle=request.oracle,
            objectives=request.objectives,
            case_ids=tuple(case.id for case in request.cases),
            tags=tuple(dict.fromkeys((*self.profile.tags, *request.tags))),
            external_requirements=request.external_requirements,
            extensions=extensions,
        )
        manifest_payload = {
            "adapter_id": self.profile.id,
            "source_kind": self.profile.source_kind,
            "source_id": request.source_id,
            "source_version": request.source_version,
            "source_uri": request.source_uri,
            "claim_scope": request.claim_scope,
            "metadata": metadata,
            "task_digest": task.digest,
            "case_digests": [case.digest for case in request.cases],
        }
        limitations = tuple(
            dict.fromkeys((*self.profile.default_limitations, *request.limitations))
        )
        bundle = ExternalBenchmarkBundle(
            self.profile.id,
            self.profile.source_kind,
            request.source_id,
            request.source_version,
            request.source_uri,
            request.claim_scope,
            task,
            request.cases,
            sha256_digest(manifest_payload),
            limitations,
        )
        bundle_problems = bundle.validate()
        if bundle_problems:
            raise ValueError("invalid external benchmark bundle: " + "; ".join(bundle_problems))
        return bundle


KAGGLE_ADAPTER_PROFILE = BenchmarkAdapterProfile(
    "adapter.kaggle",
    "benchmark.kaggle",
    "dag.learn.tabular",
    (
        "benchmark.dataset-license",
        "benchmark.data-version",
        "benchmark.metric-implementation",
        "benchmark.leakage-rules",
        "benchmark.submission-format",
    ),
    ("benchmark.kaggle", "benchmark.external"),
    (
        "A local split is required; repeated public-leaderboard tuning is not holdout evidence.",
        "The adapter does not download competition data or submit predictions.",
    ),
)

MLE_BENCH_ADAPTER_PROFILE = BenchmarkAdapterProfile(
    "adapter.mle-bench",
    "benchmark.mle-bench",
    "dag.learn.tabular",
    (
        "benchmark.dataset-license",
        "benchmark.data-version",
        "benchmark.metric-implementation",
        "benchmark.harness-version",
        "benchmark.submission-format",
    ),
    ("benchmark.mle-bench", "benchmark.external"),
    (
        "The adapter records MLE-bench identity but does not claim compatibility with every competition image.",
        "Container or remote execution policy must be supplied by the harness.",
    ),
)

SKILLSBENCH_ADAPTER_PROFILE = BenchmarkAdapterProfile(
    "adapter.skillsbench",
    "benchmark.skillsbench",
    "dag.evaluate.agent-skill",
    (
        "benchmark.dataset-license",
        "benchmark.task-set-version",
        "benchmark.evaluator-version",
        "benchmark.agent-policy",
    ),
    ("benchmark.skillsbench", "benchmark.agent"),
    (
        "Skill lift must compare matched with-skill and without-skill controls.",
        "External agent and container execution remain outside this manifest adapter.",
    ),
)

SWE_BENCH_ADAPTER_PROFILE = BenchmarkAdapterProfile(
    "adapter.swe-bench",
    "benchmark.swe-bench",
    "dag.engineer.code-repair",
    (
        "benchmark.dataset-license",
        "benchmark.dataset-split",
        "benchmark.harness-version",
        "benchmark.repository-snapshot-policy",
    ),
    ("benchmark.swe-bench", "benchmark.code-repair"),
    (
        "Repository images and tests must be resolved by a separately authorized harness.",
        "A passing transparent fixture is not a SWE-bench score.",
    ),
)

BROWSERGYM_ADAPTER_PROFILE = BenchmarkAdapterProfile(
    "adapter.browsergym",
    "benchmark.browsergym",
    "dag.operate.browser",
    (
        "benchmark.dataset-license",
        "benchmark.environment-version",
        "benchmark.task-set-version",
        "benchmark.evaluator-version",
    ),
    ("benchmark.browsergym", "benchmark.browser"),
    (
        "Browser state, credentials, and websites require an explicit runtime authority boundary.",
        "The manifest adapter does not certify task availability or website stability.",
    ),
)

DUECARE_ADAPTER_PROFILE = BenchmarkAdapterProfile(
    "adapter.duecare",
    "benchmark.duecare",
    "dag.evaluate.llm-harness",
    (
        "benchmark.scenario-set-version",
        "benchmark.sut-identity",
        "benchmark.grader-panel-version",
        "benchmark.sealed-split-policy",
    ),
    ("benchmark.duecare", "benchmark.llm-evaluation"),
    (
        "System-under-test execution, graders, and sealed evaluators must remain independently identified.",
        "An aggregate panel verdict does not erase criterion-level disagreement or failed cases.",
    ),
)

REFERENCE_BENCHMARK_ADAPTER_PROFILES = (
    KAGGLE_ADAPTER_PROFILE,
    MLE_BENCH_ADAPTER_PROFILE,
    SKILLSBENCH_ADAPTER_PROFILE,
    SWE_BENCH_ADAPTER_PROFILE,
    BROWSERGYM_ADAPTER_PROFILE,
    DUECARE_ADAPTER_PROFILE,
)


def get_benchmark_adapter(adapter_id: str) -> ExternalBenchmarkAdapter:
    try:
        profile = next(
            item for item in REFERENCE_BENCHMARK_ADAPTER_PROFILES if item.id == adapter_id
        )
    except StopIteration as exc:
        known = ", ".join(item.id for item in REFERENCE_BENCHMARK_ADAPTER_PROFILES)
        raise ValueError(f"unknown benchmark adapter {adapter_id!r}; known: {known}") from exc
    return ExternalBenchmarkAdapter(profile)


__all__ = [
    "BROWSERGYM_ADAPTER_PROFILE",
    "DUECARE_ADAPTER_PROFILE",
    "EXTERNAL_BENCHMARK_MODEL_VERSION",
    "EXTERNAL_CLAIM_SCOPES",
    "ExternalBenchmarkAdapter",
    "ExternalBenchmarkBundle",
    "ExternalBenchmarkRequest",
    "KAGGLE_ADAPTER_PROFILE",
    "MLE_BENCH_ADAPTER_PROFILE",
    "REFERENCE_BENCHMARK_ADAPTER_PROFILES",
    "SKILLSBENCH_ADAPTER_PROFILE",
    "SWE_BENCH_ADAPTER_PROFILE",
    "BenchmarkAdapterProfile",
    "get_benchmark_adapter",
]
