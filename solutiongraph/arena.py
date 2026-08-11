"""Universal DAG Arena catalogue and executable benchmark harness.

Arena entries distinguish runnable local fixtures from reusable templates and
credentialed production integrations.  A local address-reference fixture, for
example, proves the typed verification seam; it never claims to be an official
USPS response.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from solutiongraph.artifacts import FileArtifactStore, MemoryArtifactStore
from solutiongraph.executor import PythonRuntime, ReferenceExecutor, RuntimeRegistry
from solutiongraph.ledger import JsonlReceiptJournal
from solutiongraph.search import BeliefModel, CandidateWeight
from solutiongraph.solver import UniversalSolver, get_solver_profile
from solutiongraph.subprocess_runtime import SubprocessPythonRuntime

ARENA_MODEL_VERSION = "0.1"
ARENA_READINESS = (
    "executable_fixture",
    "template",
    "credentialed_connector",
)


@dataclass(frozen=True)
class ArenaTask:
    """One problem family with a semantic decomposition and honest readiness."""

    id: str
    title: str
    problem: str
    input_contract: str
    output_contract: str
    stage_families: tuple[str, ...]
    acceptance_signals: tuple[str, ...]
    template_id: str
    readiness: str = "template"
    executable_example_ids: tuple[str, ...] = ()
    external_requirements: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.id or not self.id.startswith("arena."):
            problems.append("arena task id must begin with arena.")
        for label, value in (
            ("title", self.title),
            ("problem", self.problem),
            ("input_contract", self.input_contract),
            ("output_contract", self.output_contract),
            ("template_id", self.template_id),
        ):
            if not value.strip():
                problems.append(f"{label} must not be empty")
        if self.readiness not in ARENA_READINESS:
            problems.append("readiness is not recognized")
        if len(self.stage_families) < 2 or any(
            not value.strip() for value in self.stage_families
        ):
            problems.append("stage_families must contain at least two named stages")
        if not self.acceptance_signals:
            problems.append("acceptance_signals must not be empty")
        if len(self.executable_example_ids) != len(set(self.executable_example_ids)):
            problems.append("executable_example_ids must be unique")
        if self.readiness == "executable_fixture" and not self.executable_example_ids:
            problems.append("executable fixtures must name an executable example")
        if self.readiness != "executable_fixture" and self.executable_example_ids:
            problems.append("non-executable entries cannot claim executable examples")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "arena_model_version": ARENA_MODEL_VERSION,
            "id": self.id,
            "title": self.title,
            "problem": self.problem,
            "input_contract": self.input_contract,
            "output_contract": self.output_contract,
            "stage_families": list(self.stage_families),
            "acceptance_signals": list(self.acceptance_signals),
            "template_id": self.template_id,
            "readiness": self.readiness,
            "executable_example_ids": list(self.executable_example_ids),
            "external_requirements": list(self.external_requirements),
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class ArenaCatalog:
    tasks: tuple[ArenaTask, ...]

    def validate(self) -> list[str]:
        problems: list[str] = []
        ids = [task.id for task in self.tasks]
        if len(ids) != len(set(ids)):
            problems.append("arena task ids must be unique")
        for index, task in enumerate(self.tasks):
            problems.extend(
                f"tasks[{index}]: {problem}" for problem in task.validate()
            )
        return problems

    def get(self, task_id: str) -> ArenaTask:
        try:
            return next(task for task in self.tasks if task.id == task_id)
        except StopIteration as exc:
            known = ", ".join(task.id for task in self.tasks)
            raise ValueError(f"unknown arena task {task_id!r}; known tasks: {known}") from exc

    def matching(
        self,
        *,
        readiness: str | None = None,
        tags: Iterable[str] = (),
    ) -> tuple[ArenaTask, ...]:
        required_tags = set(tags)
        return tuple(
            task
            for task in self.tasks
            if (readiness is None or task.readiness == readiness)
            and required_tags.issubset(task.tags)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "arena_model_version": ARENA_MODEL_VERSION,
            "task_count": len(self.tasks),
            "tasks": [task.to_dict() for task in self.tasks],
        }


def _task(
    id_suffix: str,
    title: str,
    problem: str,
    input_contract: str,
    output_contract: str,
    stages: tuple[str, ...],
    signals: tuple[str, ...],
    template_id: str,
    *,
    examples: tuple[str, ...] = (),
    external: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    readiness: str | None = None,
) -> ArenaTask:
    return ArenaTask(
        id=f"arena.{id_suffix}",
        title=title,
        problem=problem,
        input_contract=input_contract,
        output_contract=output_contract,
        stage_families=stages,
        acceptance_signals=signals,
        template_id=template_id,
        readiness=readiness or ("executable_fixture" if examples else "template"),
        executable_example_ids=examples,
        external_requirements=external,
        tags=tags,
    )


UNIVERSAL_DAG_ARENA = ArenaCatalog(
    (
        _task(
            "golden-customer-table",
            "Messy customer records to a golden customer table",
            "Normalize, validate, resolve, and merge fragmented customer identities.",
            "Source-tagged customer records plus optional reference directories.",
            "Deterministic golden records with provenance and verification state.",
            ("normalize", "validate contacts", "resolve identity", "merge golden record"),
            ("entity precision", "entity recall", "verified-field coverage", "provenance completeness"),
            "template.data-quality",
            examples=("data-cleanup", "golden-customer-table"),
            tags=("data-cleaning", "identity"),
        ),
        _task(
            "usps-address-verification",
            "Multi-source addresses to standardized, verified records",
            "Parse, standardize, and verify United States postal addresses.",
            "Raw addresses plus an explicitly identified authoritative reference connector.",
            "Standardized address records with match codes, provenance, and unresolved reasons.",
            ("parse", "normalize to postal form", "authoritative lookup", "classify match", "emit"),
            ("deliverability match", "false-positive rate", "unit preservation", "coverage"),
            "template.data-quality",
            examples=("address-reference-verification",),
            external=(
                "The bundled example uses an offline reference fixture, not USPS.",
                "Production USPS validation requires approved credentials, current USPS APIs, rate limits, and response retention rules.",
            ),
            tags=("address", "verification", "external-authority"),
        ),
        _task(
            "verified-product-scrape",
            "Websites to an independently verified product dataset",
            "Acquire authorized pages, extract products, normalize fields, and corroborate records.",
            "Authorized URLs or captured HTML plus a requested product schema.",
            "Typed product rows with source evidence and verification status.",
            ("acquire", "parse", "extract", "normalize", "cross-source verify", "publish"),
            ("field accuracy", "source coverage", "freshness", "schema validity"),
            "template.web-automation",
            examples=("browse-and-scrape", "verified-product-dataset"),
            external=("Live execution must honor site authorization, robots policy, rate limits, and terms."),
            tags=("web", "scraping", "verification"),
        ),
        _task(
            "invoice-accounting-schema",
            "Unstructured invoices to a typed accounting schema",
            "Decode documents, recover layout, extract fields, reconcile totals, and validate accounting rules.",
            "PDF/image/text invoices and a versioned accounting schema.",
            "Grounded invoice records with evidence locations and validation findings.",
            ("decode", "OCR or text extraction", "layout", "field extraction", "reconcile totals", "validate"),
            ("field accuracy", "total reconciliation", "evidence grounding", "schema validity"),
            "template.document-intelligence",
            examples=("document-to-schema",),
            tags=("documents", "accounting"),
        ),
        _task(
            "image-assurance",
            "Images to OCR, quality, safety, and classification reports",
            "Decode and transform images, then run independent quality and content checks.",
            "Image bytes plus requested checks and policy versions.",
            "A typed report with measurements, labels, OCR evidence, and policy verdicts.",
            ("decode", "orient", "enhance", "OCR", "quality", "safety", "classify", "aggregate"),
            ("decode success", "OCR accuracy", "calibration", "policy recall", "latency"),
            "template.image-processing",
            examples=("image-check-and-process",),
            tags=("image", "quality", "safety"),
        ),
        _task(
            "tabular-prediction",
            "Tabular data to regression or classification submissions",
            "Build leakage-safe preprocessing, modeling, ensembling, and submission graphs.",
            "Versioned train/test tables, target definition, metric, and resource budget.",
            "Reproducible predictions, validation evidence, and a model receipt.",
            ("profile", "split", "clean", "impute", "encode", "select", "fit", "calibrate", "ensemble", "submit"),
            ("holdout metric", "leakage checks", "calibration", "stability", "cost"),
            "template.kaggle-tabular",
            examples=("tabular-regression", "tabular-classification"),
            tags=("machine-learning", "kaggle"),
        ),
        _task(
            "calibrated-forecast",
            "Historical transactions to calibrated forecasts",
            "Regularize time series, fit candidates, forecast, and calibrate prediction intervals.",
            "Timestamped observations, forecast horizon, and backtest boundary.",
            "Point forecasts and intervals with backtest coverage evidence.",
            ("regularize", "detect regime", "features", "fit", "forecast", "calibrate intervals", "backtest"),
            ("MAE or pinball loss", "interval coverage", "interval width", "stability"),
            "template.time-series-forecasting",
            examples=("calibrated-time-series-forecast",),
            tags=("forecasting", "time-series"),
        ),
        _task(
            "organization-entity-graph",
            "Duplicate organizations to a resolved entity graph",
            "Normalize organizations, generate candidate pairs, score links, and form components.",
            "Source-tagged organization records and optional authoritative identifiers.",
            "Entity components, canonical organizations, pair evidence, and uncertainty.",
            ("normalize", "block", "compare", "link", "cluster", "canonicalize", "audit"),
            ("pair precision", "pair recall", "cluster quality", "review rate"),
            "template.data-quality",
            examples=("organization-entity-linking",),
            tags=("entity-linking", "knowledge-graph"),
        ),
        _task(
            "repository-repair",
            "Broken repositories to tested repairs",
            "Reproduce failures, localize causes, propose bounded patches, and verify regressions.",
            "Immutable repository snapshot, failing checks, and authority policy.",
            "Patch, test receipts, changed-file scope, and rollback instructions.",
            ("reproduce", "localize", "hypothesize", "patch", "test", "security scan", "package"),
            ("target test pass", "regression pass", "scope", "security", "reproducibility"),
            "template.qa-engineering",
            examples=("tested-code-repair",),
            tags=("code", "repair", "qa"),
        ),
        _task(
            "validated-analytical-dataset",
            "Raw files and API feeds to a validated analytical dataset",
            "Decode heterogeneous feeds, map schemas, reconcile records, validate, and publish.",
            "Versioned files/API captures, contracts, and source priorities.",
            "Typed analytical tables, quarantine rows, lineage, and quality report.",
            ("capture", "decode", "map schema", "normalize", "join", "reconcile", "validate", "publish"),
            ("schema conformance", "referential integrity", "reconciliation", "freshness", "lineage"),
            "template.batch-data-pipeline",
            examples=("multi-feed-analytical-dataset",),
            tags=("data-engineering", "etl"),
        ),
        _task(
            "contact-verification",
            "Contact records to verified communication endpoints",
            "Parse and verify email, phone, consent, and reachability without conflating those claims.",
            "Contact records, consent ledger, and approved verification connectors.",
            "Endpoint-specific validity, consent, provenance, and next-action state.",
            ("parse", "normalize", "syntax check", "authority check", "consent check", "classify"),
            ("precision", "coverage", "consent safety", "freshness"),
            "template.data-quality",
            examples=("contact-verification",),
            external=("Live email and phone reachability require approved providers and consent-aware policies."),
            tags=("contact", "verification"),
        ),
        _task(
            "web-change-monitoring",
            "Web snapshots to verified change events",
            "Capture pages, remove expected noise, compare semantic content, and corroborate changes.",
            "Authorized page targets, prior captures, and significance policy.",
            "Evidence-backed change events with confidence and alert disposition.",
            ("capture", "canonicalize", "segment", "diff", "corroborate", "alert"),
            ("change precision", "change recall", "alert latency", "noise rate"),
            "template.web-automation",
            examples=("web-change-monitoring",),
            tags=("web", "monitoring"),
        ),
        _task(
            "transaction-reconciliation",
            "Independent transaction streams to a reconciled ledger",
            "Normalize, match, balance, explain, and route unmatched financial events.",
            "Two or more source ledgers with stable source identities.",
            "Matched groups, residuals, exceptions, and balancing proof.",
            ("normalize", "candidate match", "score", "balance", "explain", "route exception"),
            ("matched value", "false match rate", "unexplained residual", "timeliness"),
            "template.batch-data-pipeline",
            examples=("transaction-reconciliation",),
            tags=("finance", "reconciliation"),
        ),
        _task(
            "pii-redaction",
            "Documents to verified PII-redacted artifacts",
            "Detect sensitive spans, apply policy-aware redactions, and independently check leakage.",
            "Documents, jurisdiction, entity policy, and output-format contract.",
            "Redacted document, span ledger, and leakage-test receipt.",
            ("decode", "detect", "resolve overlaps", "redact", "render", "leakage verify"),
            ("sensitive recall", "over-redaction", "render integrity", "leakage"),
            "template.document-intelligence",
            examples=("pii-redaction",),
            tags=("privacy", "documents"),
        ),
        _task(
            "schema-migration",
            "Versioned datasets to a verified schema migration",
            "Diff contracts, plan transformations, migrate, backfill, and prove invariants.",
            "Old/new schemas, immutable source snapshot, and compatibility requirements.",
            "Migrated dataset, compatibility report, lineage, and rollback plan.",
            ("diff", "plan", "transform", "backfill", "validate", "shadow compare", "cut over"),
            ("row preservation", "invariant pass", "compatibility", "rollback readiness"),
            "template.batch-data-pipeline",
            examples=("schema-migration",),
            tags=("schema", "migration"),
        ),
        _task(
            "shipping-notification",
            "Carrier events to trustworthy customer notifications",
            "Normalize carrier events, infer shipment state, suppress duplicates, and deliver notifications.",
            "Carrier feeds, order state, customer preferences, and delivery providers.",
            "State transition, notification decision, delivery receipt, and audit trail.",
            ("ingest", "normalize", "order events", "infer state", "deduplicate", "compose", "deliver", "verify"),
            ("state accuracy", "duplicate rate", "delivery rate", "notification timeliness"),
            "template.shipping-notifications",
            readiness="credentialed_connector",
            external=("Production use requires carrier and messaging provider credentials."),
            tags=("logistics", "events"),
        ),
        _task(
            "incident-triage",
            "Logs and alerts to a verified incident triage packet",
            "Parse signals, correlate events, retrieve context, propose causes, and test hypotheses.",
            "Versioned logs, metrics, traces, deploy events, and runbooks.",
            "Incident timeline, ranked hypotheses, evidence, and bounded response actions.",
            ("parse", "correlate", "retrieve", "hypothesize", "test", "rank", "respond"),
            ("time to useful hypothesis", "evidence coverage", "false action rate", "recovery"),
            "template.incident-response",
            examples=("incident-triage",),
            tags=("operations", "observability"),
        ),
        _task(
            "dependency-assurance",
            "Software dependencies to a license and security decision",
            "Resolve dependency graphs, identify provenance, scan advisories, and apply policy.",
            "Lockfiles, build manifests, artifact digests, and organization policy.",
            "SBOM, findings, policy verdicts, remediations, and evidence timestamps.",
            ("resolve", "identify", "build SBOM", "scan", "license classify", "policy", "remediate"),
            ("dependency coverage", "advisory freshness", "policy accuracy", "build pass"),
            "template.qa-engineering",
            examples=("dependency-assurance",),
            tags=("security", "supply-chain"),
        ),
        _task(
            "recommendation-ranking",
            "Events and catalog data to a verified ranking",
            "Build candidate sets, features, scores, constraints, diversification, and evaluation.",
            "User/event context, eligible items, policies, and evaluation split.",
            "Ranked items with scores, explanations, policy results, and offline evidence.",
            ("eligibility", "candidate generation", "features", "score", "policy", "diversify", "evaluate"),
            ("ranking metric", "coverage", "diversity", "policy violations", "latency"),
            "template.recommendation-ranking",
            examples=("recommendation-ranking",),
            tags=("ranking", "machine-learning"),
        ),
        _task(
            "geospatial-enrichment",
            "Addresses and coordinates to a verified geographic dataset",
            "Geocode, normalize coordinate systems, spatially join, and reconcile geographic authorities.",
            "Locations plus approved geocoders and reference boundaries.",
            "Coordinates, administrative areas, match confidence, and source provenance.",
            ("parse", "geocode", "normalize CRS", "spatial join", "authority reconcile", "verify"),
            ("geocode accuracy", "boundary consistency", "coverage", "source freshness"),
            "template.data-quality",
            readiness="credentialed_connector",
            external=("Production geocoding and Census/other authority lookups require current datasets or approved APIs."),
            tags=("geospatial", "enrichment"),
        ),
        _task(
            "scientific-experiment",
            "A scientific hypothesis to a reproducible experiment receipt",
            "Design treatments, allocate trials, execute, analyze, and test robustness.",
            "Hypothesis, variables, controls, resource budget, and measurement contract.",
            "Raw observations, analysis, uncertainty, provenance, and conclusion limits.",
            ("formalize", "design", "allocate", "execute", "measure", "analyze", "robustness", "report"),
            ("power", "effect uncertainty", "reproducibility", "assumption checks"),
            "template.scientific-experiment",
            examples=("scientific-experiment",),
            tags=("science", "experimentation"),
        ),
        _task(
            "numerical-linear-system",
            "Structured matrices to a verified numerical solution",
            "Inspect structure and conditioning, select a solver, solve, and verify residuals.",
            "Matrix/operator, right-hand side, tolerance, precision, and resource budget.",
            "Solution, residual, conditioning evidence, selected fallback, and performance receipt.",
            ("validate", "classify structure", "condition", "regularize", "factor or iterate", "solve", "residual", "fallback"),
            ("residual", "backward error", "stability", "time", "memory"),
            "template.numerical-linear-system",
            examples=("numerical-linear-system",),
            tags=("numerical", "linear-algebra"),
        ),
        _task(
            "deployment-release",
            "A release candidate to a verified production rollout",
            "Build, attest, test, stage, canary, observe, promote, or roll back.",
            "Source/artifact digest, environment contract, policy, and rollout budget.",
            "Deployment state, attestations, observations, decision, and rollback receipt.",
            ("build", "attest", "test", "stage", "canary", "observe", "decide", "promote or rollback"),
            ("test pass", "error budget", "performance delta", "rollback readiness"),
            "template.deployment-release",
            readiness="credentialed_connector",
            external=("Production execution requires deployment-provider credentials and explicit change authority."),
            tags=("deployment", "operations"),
        ),
        _task(
            "api-business-workflow",
            "A business request to a verified multi-system transaction",
            "Validate intent, authorize, coordinate APIs, reconcile results, and compensate failures.",
            "Typed request, actor authority, service contracts, and idempotency keys.",
            "Committed business result or compensated failure with complete audit evidence.",
            ("validate", "authorize", "plan", "reserve", "execute", "reconcile", "compensate", "notify"),
            ("contract success", "consistency", "idempotency", "compensation completeness", "latency"),
            "template.api-service",
            readiness="credentialed_connector",
            external=("Writes to external systems require scoped credentials and explicit authority."),
            tags=("api", "business-workflow"),
        ),
    )
)


def solve_example(
    example_id: str,
    *,
    profile: str = "balanced",
    runtime: str = "in-process",
    artifact_root: str | Path | None = None,
    receipt_journal: JsonlReceiptJournal | None = None,
    allow_exhaustive: bool = False,
) -> dict[str, Any]:
    """Run the universal solver against one bundled executable fixture."""
    from solutiongraph.examples import get_example

    example = get_example(example_id)
    if runtime == "in-process":
        executor = ReferenceExecutor(
            runtimes=RuntimeRegistry({"python": PythonRuntime()})
        )
        policy = example.policy
    elif runtime == "subprocess":
        executor = ReferenceExecutor(
            runtimes=RuntimeRegistry({"python": SubprocessPythonRuntime()})
        )
        policy = replace(example.policy, allow_in_process_python=False)
    else:
        raise ValueError("runtime must be 'in-process' or 'subprocess'")
    store_factory = (
        (lambda: FileArtifactStore(Path(artifact_root)))
        if artifact_root is not None
        else MemoryArtifactStore
    )
    suggested = next(
        (route for route in example.routes if route.expected_accepted),
        example.routes[0],
    )
    seeded_beliefs = BeliefModel(
        revision=f"example.suggested-route-{suggested.id}",
        candidate_weights=tuple(
            CandidateWeight(slot_id, candidate_id, 1.0)
            for slot_id, candidate_id in suggested.selection.items()
        ),
    )
    result = UniversalSolver(executor=executor).solve(
        example.program,
        example.registry,
        cases=(example.case,),
        objectives=example.objectives,
        policy=policy,
        profile=get_solver_profile(profile),
        beliefs=seeded_beliefs,
        baseline_selection=example.routes[0].selection,
        artifact_store_factory=store_factory,
        receipt_sink=receipt_journal,
        allow_exhaustive=allow_exhaustive,
    )
    return {
        "example_id": example.id,
        "title": example.title,
        "runtime": runtime,
        "result": result.to_dict(),
    }


def run_arena(
    task_ids: Iterable[str] | None = None,
    *,
    profile: str = "quick",
    runtime: str = "in-process",
    artifact_root: str | Path | None = None,
    receipt_journal: JsonlReceiptJournal | None = None,
    allow_exhaustive: bool = False,
) -> dict[str, Any]:
    """Run each selected executable fixture and disclose every skipped template."""
    selected = (
        tuple(UNIVERSAL_DAG_ARENA.get(task_id) for task_id in task_ids)
        if task_ids is not None
        else UNIVERSAL_DAG_ARENA.matching(readiness="executable_fixture")
    )
    example_ids: list[str] = []
    skipped: list[dict[str, str]] = []
    for task in selected:
        if task.readiness != "executable_fixture":
            skipped.append(
                {
                    "task_id": task.id,
                    "readiness": task.readiness,
                    "reason": "No bundled local executable fixture is claimed.",
                }
            )
            continue
        for example_id in task.executable_example_ids:
            if example_id not in example_ids:
                example_ids.append(example_id)
    root = Path(artifact_root) if artifact_root is not None else None
    reports = [
        solve_example(
            example_id,
            profile=profile,
            runtime=runtime,
            artifact_root=(root / example_id if root is not None else None),
            receipt_journal=receipt_journal,
            allow_exhaustive=allow_exhaustive,
        )
        for example_id in example_ids
    ]
    return {
        "arena_model_version": ARENA_MODEL_VERSION,
        "profile": profile,
        "runtime": runtime,
        "selected_task_ids": [task.id for task in selected],
        "executed_example_count": len(reports),
        "skipped_task_count": len(skipped),
        "skipped": skipped,
        "examples": reports,
    }


__all__ = [
    "ARENA_MODEL_VERSION",
    "ARENA_READINESS",
    "ArenaCatalog",
    "ArenaTask",
    "UNIVERSAL_DAG_ARENA",
    "run_arena",
    "solve_example",
]
