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
        if len(self.stage_families) < 2 or any(not value.strip() for value in self.stage_families):
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
            problems.extend(f"tasks[{index}]: {problem}" for problem in task.validate())
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
            (
                "entity precision",
                "entity recall",
                "verified-field coverage",
                "provenance completeness",
            ),
            "template.data-quality",
            examples=("data-cleanup", "golden-customer-table", "stdlib-data-quality"),
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
            external=(
                "Live execution must honor site authorization, robots policy, rate limits, and terms."
            ),
            tags=("web", "scraping", "verification"),
        ),
        _task(
            "invoice-accounting-schema",
            "Unstructured invoices to a typed accounting schema",
            "Decode documents, recover layout, extract fields, reconcile totals, and validate accounting rules.",
            "PDF/image/text invoices and a versioned accounting schema.",
            "Grounded invoice records with evidence locations and validation findings.",
            (
                "decode",
                "OCR or text extraction",
                "layout",
                "field extraction",
                "reconcile totals",
                "validate",
            ),
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
            (
                "profile",
                "split",
                "clean",
                "impute",
                "encode",
                "select",
                "fit",
                "calibrate",
                "ensemble",
                "submit",
            ),
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
            (
                "regularize",
                "detect regime",
                "features",
                "fit",
                "forecast",
                "calibrate intervals",
                "backtest",
            ),
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
            (
                "capture",
                "decode",
                "map schema",
                "normalize",
                "join",
                "reconcile",
                "validate",
                "publish",
            ),
            (
                "schema conformance",
                "referential integrity",
                "reconciliation",
                "freshness",
                "lineage",
            ),
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
            external=(
                "Live email and phone reachability require approved providers and consent-aware policies."
            ),
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
            (
                "ingest",
                "normalize",
                "order events",
                "infer state",
                "deduplicate",
                "compose",
                "deliver",
                "verify",
            ),
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
            (
                "resolve",
                "identify",
                "build SBOM",
                "scan",
                "license classify",
                "policy",
                "remediate",
            ),
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
            (
                "eligibility",
                "candidate generation",
                "features",
                "score",
                "policy",
                "diversify",
                "evaluate",
            ),
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
            external=(
                "Production geocoding and Census/other authority lookups require current datasets or approved APIs."
            ),
            tags=("geospatial", "enrichment"),
        ),
        _task(
            "scientific-experiment",
            "A scientific hypothesis to a reproducible experiment receipt",
            "Design treatments, allocate trials, execute, analyze, and test robustness.",
            "Hypothesis, variables, controls, resource budget, and measurement contract.",
            "Raw observations, analysis, uncertainty, provenance, and conclusion limits.",
            (
                "formalize",
                "design",
                "allocate",
                "execute",
                "measure",
                "analyze",
                "robustness",
                "report",
            ),
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
            (
                "validate",
                "classify structure",
                "condition",
                "regularize",
                "factor or iterate",
                "solve",
                "residual",
                "fallback",
            ),
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
            (
                "build",
                "attest",
                "test",
                "stage",
                "canary",
                "observe",
                "decide",
                "promote or rollback",
            ),
            ("test pass", "error budget", "performance delta", "rollback readiness"),
            "template.deployment-release",
            readiness="credentialed_connector",
            external=(
                "Production execution requires deployment-provider credentials and explicit change authority."
            ),
            tags=("deployment", "operations"),
        ),
        _task(
            "api-business-workflow",
            "A business request to a verified multi-system transaction",
            "Validate intent, authorize, coordinate APIs, reconcile results, and compensate failures.",
            "Typed request, actor authority, service contracts, and idempotency keys.",
            "Committed business result or compensated failure with complete audit evidence.",
            (
                "validate",
                "authorize",
                "plan",
                "reserve",
                "execute",
                "reconcile",
                "compensate",
                "notify",
            ),
            (
                "contract success",
                "consistency",
                "idempotency",
                "compensation completeness",
                "latency",
            ),
            "template.api-service",
            readiness="credentialed_connector",
            external=(
                "Writes to external systems require scoped credentials and explicit authority."
            ),
            tags=("api", "business-workflow"),
        ),
        _task(
            "grounded-knowledge-system",
            "Source corpus to grounded answers with citations",
            "Ingest governed sources, build replaceable indexes, retrieve evidence, answer, and verify grounding.",
            "Versioned source corpus, access policy, query classes, and answer schema.",
            "Typed answers or abstentions with source spans, verification, and retrieval receipts.",
            (
                "contract",
                "ingest",
                "segment",
                "index",
                "retrieve",
                "rerank",
                "answer",
                "ground",
                "verify",
            ),
            (
                "answer correctness",
                "citation validity",
                "retrieval recall",
                "unsupported claim rate",
                "freshness",
            ),
            "template.knowledge-retrieval",
            tags=("knowledge", "retrieval", "grounding"),
        ),
        _task(
            "claims-adjudication",
            "Claim package to evidence-grounded adjudication",
            "Extract claim facts, retrieve policy, corroborate evidence, adjudicate, review exceptions, and settle.",
            "Authenticated claim package, policy version, coverage context, and decision authority.",
            "Approved settlement or explained denial with evidence, review state, and audit receipt.",
            (
                "intake",
                "extract",
                "retrieve policy",
                "corroborate",
                "adjudicate",
                "review",
                "settle",
                "audit",
            ),
            (
                "decision accuracy",
                "benefit reconciliation",
                "evidence coverage",
                "review calibration",
                "cycle time",
            ),
            "template.claims-processing",
            tags=("claims", "adjudication", "documents"),
        ),
        _task(
            "fraud-risk-decision",
            "Events to calibrated fraud-risk decisions",
            "Resolve identities, derive point-in-time features, combine detectors, choose actions, and learn from outcomes.",
            "Source-identified events, historical observations, risk policy, and intervention budget.",
            "Calibrated risk, reasons, proportionate action, and eventual outcome evidence.",
            (
                "observe",
                "resolve identity",
                "features",
                "rules",
                "anomaly",
                "model",
                "combine",
                "decide",
                "learn",
            ),
            ("precision", "recall", "calibration", "loss avoided", "customer friction", "latency"),
            "template.fraud-risk",
            tags=("fraud", "risk", "classification"),
        ),
        _task(
            "defensive-cyber-investigation",
            "Security telemetry to verified defensive findings",
            "Collect authorized telemetry, build an activity graph, test hypotheses, contain, and verify recovery.",
            "Authorized systems, investigation window, hypotheses, telemetry sources, and evidence policy.",
            "Confidence-bounded findings, timeline, defensive actions, recovery evidence, and case receipt.",
            (
                "scope",
                "collect",
                "normalize",
                "enrich",
                "activity graph",
                "hypotheses",
                "contain",
                "recover",
            ),
            (
                "detection quality",
                "evidence integrity",
                "time to contain",
                "false-positive rate",
                "recovery verification",
            ),
            "template.cybersecurity-investigation",
            examples=("defensive-cyber-investigation",),
            external=(
                "The bundled example is synthetic, read-only, and executes no containment. Production use requires explicit defensive authority and access-controlled telemetry and response connectors."
            ),
            tags=("security", "defensive", "investigation"),
        ),
        _task(
            "compliance-evidence-pack",
            "Requirements to a replayable control evidence pack",
            "Map requirements, collect authentic evidence, test controls, resolve exceptions, and attest within claim limits.",
            "Authoritative requirements, applicability, control inventory, systems, owners, and test policy.",
            "Control findings, samples, exceptions, remediation evidence, and bounded attestation.",
            (
                "map",
                "collect",
                "authenticate",
                "sample",
                "test",
                "cross-check",
                "remediate",
                "attest",
            ),
            (
                "control coverage",
                "evidence authenticity",
                "test reproducibility",
                "exception closure",
                "freshness",
            ),
            "template.compliance-evidence",
            tags=("compliance", "audit", "evidence"),
        ),
        _task(
            "geospatial-data-product",
            "Spatial sources to a verified analytical map product",
            "Normalize coordinate systems, repair topology, integrate sources, analyze, quantify uncertainty, and publish.",
            "Versioned geometries, rasters, tables, CRS declarations, predicates, and analytical objective.",
            "Verified spatial dataset, analysis, uncertainty, visualization, rejects, and lineage.",
            (
                "ingest",
                "validate geometry",
                "transform CRS",
                "index",
                "spatial join",
                "analyze",
                "uncertainty",
                "publish",
            ),
            (
                "geometry validity",
                "coverage",
                "join loss",
                "positional error",
                "numerical accuracy",
            ),
            "template.geospatial-analytics",
            tags=("geospatial", "gis", "analytics"),
        ),
        _task(
            "audio-speech-assurance",
            "Audio to aligned transcript and assurance report",
            "Decode, enhance, segment, diarize, transcribe, classify, verify, and redact audio evidence.",
            "Exact audio bytes, language hints, requested outputs, terminology, and redaction policy.",
            "Timestamped transcript, speakers, acoustic findings, confidence, redactions, and receipt.",
            (
                "decode",
                "validate",
                "enhance",
                "activity",
                "diarize",
                "transcribe",
                "align",
                "verify",
                "redact",
            ),
            (
                "word error rate",
                "alignment error",
                "speaker error",
                "policy recall",
                "signal quality",
            ),
            "template.audio-speech",
            tags=("audio", "speech", "transcription"),
        ),
        _task(
            "supply-chain-plan",
            "Demand and supply state to a resilient execution plan",
            "Forecast uncertain demand and lead time, optimize candidate plans, stress them, approve, dispatch, and replan.",
            "Reconciled demand, inventory, capacity, network, policy, scenarios, and planning horizon.",
            "Feasible approved plan, tradeoff evidence, dispatched actions, observations, and replan triggers.",
            (
                "state",
                "forecast",
                "scenarios",
                "constraints",
                "optimize",
                "stress",
                "approve",
                "execute",
                "replan",
            ),
            ("service level", "cost", "feasibility", "resilience", "inventory", "emissions"),
            "template.supply-chain-planning",
            tags=("supply-chain", "planning", "optimization"),
        ),
        _task(
            "constraint-scheduling",
            "Constraints and objectives to a verified schedule",
            "Formalize, transform, solve, refine, independently verify, and operationalize scheduling decisions.",
            "Decision variables, hard constraints, objectives, instance data, budget, and acceptable optimality gap.",
            "Feasible schedule, recomputed objectives, bound status, explanations, and execution monitor.",
            (
                "formalize",
                "validate",
                "presolve",
                "decompose",
                "solve",
                "refine",
                "verify",
                "publish",
                "monitor",
            ),
            ("feasibility", "objective value", "optimality gap", "runtime", "stability"),
            "template.optimization-scheduling",
            tags=("scheduling", "constraints", "optimization"),
        ),
        _task(
            "database-migration",
            "Source database to a reconciled cutover",
            "Map schemas, backfill, capture changes, shadow workloads, reconcile, cut over, and preserve rollback.",
            "Source and target contracts, data mappings, workload profile, SLOs, and change authority.",
            "Reconciled target, offsets, shadow evidence, cutover state, and rollback or retirement receipt.",
            (
                "assess",
                "map",
                "prepare",
                "snapshot",
                "backfill",
                "capture changes",
                "reconcile",
                "shadow",
                "cutover",
            ),
            (
                "row and value reconciliation",
                "replication lag",
                "workload compatibility",
                "downtime",
                "rollback readiness",
            ),
            "template.database-migration",
            external=(
                "Live migration requires scoped source/target credentials and explicit cutover authority."
            ),
            tags=("database", "migration", "cdc"),
        ),
        _task(
            "sre-observability-response",
            "Telemetry to a verified reliability response",
            "Collect trustworthy telemetry, detect SLO degradation, correlate symptoms, diagnose, mitigate, and learn.",
            "Service topology, telemetry, SLOs, ownership, mitigation authority, and error-budget policy.",
            "Impact, causal evidence, mitigation, recovery verification, and follow-up actions.",
            (
                "instrument",
                "collect",
                "verify telemetry",
                "detect",
                "correlate",
                "diagnose",
                "mitigate",
                "recover",
                "learn",
            ),
            ("detection delay", "precision", "time to recovery", "SLO recovery", "recurrence"),
            "template.observability-sre",
            tags=("sre", "observability", "reliability"),
        ),
        _task(
            "conflict-aware-data-contract",
            "Messy records to a conflict-aware contracted dataset",
            "Profile, normalize, impute permitted fields, resolve conflicting sources, validate a versioned contract, and quarantine invalid records.",
            "Source-tagged records, source priority, imputation policy, and an immutable data contract.",
            "Validated records, field-level provenance, conflict and imputation ledgers, quarantine rows, and output digest.",
            (
                "profile",
                "normalize missing",
                "impute",
                "resolve conflicts",
                "validate contract",
                "quarantine",
            ),
            (
                "contract pass",
                "row preservation",
                "conflict traceability",
                "imputation scope",
                "quarantine completeness",
            ),
            "template.data-quality",
            examples=("conflict-aware-data-contract",),
            tags=("data-cleaning", "imputation", "conflict-resolution", "data-contract"),
        ),
        _task(
            "event-time-windowing",
            "Out-of-order events to correction-aware windows",
            "Normalize event time, deduplicate, expose watermark decisions, aggregate windows, classify lateness, and link corrections to prior emissions.",
            "Events with event and processing timestamps plus window and allowed-lateness policies.",
            "Window emissions, dropped-event evidence, watermark trace, and explicit retraction links.",
            (
                "normalize event time",
                "deduplicate",
                "watermark",
                "window",
                "late-data policy",
                "retract",
            ),
            (
                "window accuracy",
                "duplicate removal",
                "late acceptance",
                "drop accountability",
                "correction lineage",
            ),
            "template.event-driven-system",
            examples=("event-time-windowing",),
            tags=("streaming", "event-time", "watermark", "late-data"),
        ),
        _task(
            "exact-gis-boundary-resolution",
            "Coordinates to versioned administrative membership",
            "Require CRS identity, prefilter candidate boundaries, apply an explicit spatial predicate, resolve overlaps, and retain boundary-vintage evidence.",
            "Coordinates, CRS and axis order, versioned polygons, level policy, and authority identity.",
            "Resolved memberships, ambiguity ledger, predicate identity, CRS, boundary vintage, and input/output digests.",
            (
                "normalize coordinate",
                "declare CRS",
                "prefilter",
                "exact predicate",
                "resolve overlap",
                "provenance",
            ),
            (
                "known-point accuracy",
                "boundary coverage",
                "ambiguity handling",
                "CRS correctness",
                "vintage traceability",
            ),
            "template.geospatial-analytics",
            examples=("exact-gis-boundary-resolution",),
            external=(
                "Production authority requires current approved boundary datasets and exact CRS transformation libraries."
            ),
            tags=("gis", "boundaries", "crs", "geospatial"),
        ),
        _task(
            "idempotent-api-contract",
            "Retries to one authorized backend mutation",
            "Validate a request contract, authorize the exact scope, enforce idempotency, execute, validate the response, and emit a secret-free audit record.",
            "Versioned request and response contracts, scoped principal, idempotency key, and operation payload.",
            "Stable responses, one logical mutation, authorization verdict, idempotency evidence, and audit digest.",
            (
                "validate request",
                "authorize",
                "idempotency",
                "execute",
                "validate response",
                "audit",
            ),
            (
                "contract conformance",
                "authorization",
                "duplicate suppression",
                "response stability",
                "audit completeness",
            ),
            "template.api-service",
            examples=("idempotent-api-contract",),
            tags=("api", "backend", "idempotency", "authorization"),
        ),
        _task(
            "frontend-release-journey",
            "UI build and trace to an evidence-backed release gate",
            "Check accessible controls, API contracts, a deterministic user journey, and performance budgets before release.",
            "UI element inventory, browser trace, API contracts, expected journey, and versioned budgets.",
            "Per-gate findings, replay state, performance evidence, release verdict, and evidence digest.",
            (
                "normalize trace",
                "accessibility",
                "API contracts",
                "journey replay",
                "performance",
                "release gate",
            ),
            (
                "accessibility pass",
                "journey completion",
                "contract pass",
                "budget pass",
                "deterministic evidence",
            ),
            "template.qa-engineering",
            examples=("frontend-release-journey",),
            tags=("frontend", "accessibility", "journey", "release"),
        ),
        _task(
            "document-render-and-verify",
            "Structured document to visually checked output",
            "Parse content, resolve exact assets, lay out pages, render through a declared adapter, verify visual invariants, and bind source to output.",
            "Structured blocks, content-addressed assets, page contract, output format, and visual checks.",
            "Rendered artifact identity, page/layout evidence, asset closure, visual findings, and render receipt.",
            ("parse", "resolve assets", "layout", "render", "visual verify", "seal receipt"),
            (
                "asset closure",
                "page count",
                "no overflow",
                "visual invariants",
                "source-output identity",
            ),
            "template.document-intelligence",
            examples=("document-render-and-verify",),
            tags=("documents", "rendering", "visual-verification", "provenance"),
        ),
        _task(
            "dataset-profiling-and-drift",
            "Dataset snapshots to a drift-aware quality report",
            "Infer schema, profile distributions and missingness, find duplicate content, compare snapshots, and bind the findings to source evidence.",
            "Reference and current records with stable column semantics.",
            "Schema, profiles, missingness patterns, duplicates, drift scores, and a content-addressed quality report.",
            ("infer schema", "profile", "missingness", "duplicates", "drift", "report"),
            (
                "schema coverage",
                "missingness accounting",
                "duplicate accuracy",
                "drift evidence",
                "lineage",
            ),
            "template.data-quality",
            examples=("dataset-profiling-and-drift",),
            tags=("data-science", "profiling", "data-quality", "drift"),
        ),
        _task(
            "wide-table-feature-reduction",
            "Wide tables to a traceable reduced feature matrix",
            "Repair permitted missing values, scale, remove constants, group collinearity, select relevant representatives, and preserve a feature manifest.",
            "Typed feature rows, target identity, and transformation policy.",
            "Reduced matrix, selected and removed features, fitted transformations, and source lineage.",
            ("impute", "scale", "variance", "collinearity", "select", "project"),
            ("no missing output", "variance removal", "relevance", "feature count", "lineage"),
            "template.kaggle-tabular",
            examples=("wide-table-feature-reduction",),
            tags=("data-science", "feature-engineering", "feature-selection", "tabular"),
        ),
        _task(
            "imbalanced-classification-and-calibration",
            "Imbalanced labels to calibrated, slice-checked decisions",
            "Preserve a stratified holdout, rebalance training, fit and calibrate a classifier, tune a decision threshold, and evaluate minority and group behavior.",
            "Labeled rows, immutable split membership, features, groups, and decision objective.",
            "Calibrated probabilities, threshold, predictions, minority recall, slice metrics, and split lineage.",
            ("split", "rebalance", "fit", "calibrate", "threshold", "slice evaluation"),
            ("holdout isolation", "accuracy", "minority recall", "calibration", "slice coverage"),
            "template.kaggle-tabular",
            examples=("imbalanced-classification-and-calibration",),
            tags=("data-science", "classification", "imbalance", "calibration"),
        ),
        _task(
            "robust-regression-and-conformal",
            "Grouped observations to robust predictions and intervals",
            "Hold out an entire group, screen training outliers, fit a robust regressor, predict, construct residual intervals, and stress the result.",
            "Regression rows with group identity, target, feature, and holdout policy.",
            "Model, outlier ledger, held-group predictions, intervals, coverage, error, and perturbation evidence.",
            ("group split", "outliers", "robust fit", "predict", "intervals", "stress"),
            ("group isolation", "outlier traceability", "RMSE", "interval coverage", "stability"),
            "template.kaggle-tabular",
            examples=("robust-regression-and-conformal",),
            tags=("data-science", "regression", "robustness", "uncertainty"),
        ),
        _task(
            "time-series-feature-backtest",
            "Gapped observations to walk-forward forecasts",
            "Audit chronology, repair a bounded gap, derive temporal features, build lag windows, backtest without shuffling, and issue uncertainty intervals.",
            "Ordered timestamp/value observations, gap policy, horizon, and evaluation budget.",
            "Repaired series, temporal features, lag windows, walk-forward evidence, forecasts, and intervals.",
            ("chronology", "interpolate", "calendar", "lags", "backtest", "forecast"),
            (
                "gap accounting",
                "temporal isolation",
                "MAE",
                "interval ordering",
                "horizon completeness",
            ),
            "template.time-series-forecasting",
            examples=("time-series-feature-backtest",),
            tags=("data-science", "time-series", "feature-engineering", "backtesting"),
        ),
        _task(
            "text-classification-pipeline",
            "Documents to evaluated text classifications",
            "Normalize text, tokenize, form n-grams, vectorize, fit a transparent model, and evaluate untouched documents.",
            "Text documents with labels and immutable train/holdout membership.",
            "Text transforms, vocabulary evidence, model weights, held-document predictions, and metrics.",
            ("normalize", "tokenize", "n-grams", "vectorize", "fit", "evaluate"),
            ("split isolation", "vocabulary traceability", "accuracy", "prediction evidence"),
            "template.document-intelligence",
            examples=("text-classification-pipeline",),
            tags=("data-science", "nlp", "text", "classification"),
        ),
        _task(
            "unsupervised-segmentation-and-anomaly",
            "Unlabeled points to segments and anomaly evidence",
            "Robustly scale features, choose a cluster count, fit and assign clusters, score unusual points, and characterize each segment.",
            "Unlabeled numeric points, feature identity, and anomaly policy.",
            "Cluster-count evidence, centers, assignments, anomaly scores, and human-readable segment profiles.",
            ("scale", "select k", "cluster", "assign", "anomaly", "profile"),
            (
                "cluster evidence",
                "assignment coverage",
                "anomaly detection",
                "segment characterization",
            ),
            "template.scientific-experiment",
            examples=("unsupervised-segmentation-and-anomaly",),
            tags=("data-science", "unsupervised", "clustering", "anomaly-detection"),
        ),
        _task(
            "model-explainability-and-stability",
            "Registered models to stability-aware explanation evidence",
            "Bind the model and data, compute explanations, test ranking stability, inspect slices, form a bounded counterfactual, and publish limitations.",
            "Immutable model, evaluation rows, group labels, feature order, and counterfactual request.",
            "Model digest, importance evidence, stability runs, slice metrics, counterfactual, and model card.",
            ("register", "importance", "stability", "slices", "counterfactual", "model card"),
            (
                "identity binding",
                "ranking stability",
                "slice coverage",
                "counterfactual scope",
                "limitations",
            ),
            "template.compliance-evidence",
            examples=("model-explainability-and-stability",),
            tags=("data-science", "explainability", "stability", "model-card"),
        ),
        _task(
            "ensemble-selection-and-stacking",
            "Base predictions to a leakage-checked ensemble",
            "Collect out-of-fold predictions, validate lineage, prune weak candidates, fit and calibrate a blend, and evaluate one untouched holdout.",
            "Named base predictions with fold identities, actuals, and separate holdout predictions.",
            "Fold audit, retained models, ensemble weights, calibration, holdout predictions, and error.",
            ("collect", "lineage", "prune", "blend", "calibrate", "holdout"),
            ("OOF disjointness", "weak-model removal", "holdout isolation", "ensemble error"),
            "template.kaggle-tabular",
            examples=("ensemble-selection-and-stacking",),
            tags=("data-science", "ensemble", "stacking", "leakage-control"),
        ),
        _task(
            "model-release-monitoring-and-rollback",
            "Candidate models to a gated release and rollback receipt",
            "Package exact model identity, replay inference, compare in shadow, detect drift, apply a fail-closed policy, and prepare a non-automatic rollback.",
            "Candidate and previous models, replay batch, labels, feature snapshots, schema, and release policy.",
            "Package digests, replay and shadow evidence, drift verdict, human-gated decision, and rollback target.",
            ("package", "replay", "shadow", "drift", "gate", "rollback"),
            (
                "replay identity",
                "quality delta",
                "drift threshold",
                "human authority",
                "rollback readiness",
            ),
            "template.deployment-release",
            examples=("model-release-monitoring-and-rollback",),
            tags=("data-science", "mlops", "monitoring", "rollback"),
        ),
        _task(
            "llm-evaluation-harness",
            "LLM or agent system to a sealed evaluation decision",
            "Freeze scenarios and evaluators, run controlled systems, adjudicate judgments, cluster development failures, and gate promotion on sealed evidence.",
            "Exact system identity, authority, scenario families, criteria, evaluator boundary, seeds, and budget.",
            "Criterion judgments, calibrated panels, failure clusters, sealed outer summary, promotion decision, and rollback identity.",
            (
                "contract",
                "scenarios",
                "allocate",
                "invoke",
                "deterministic oracles",
                "independent judges",
                "adjudicate",
                "failure learning",
                "sealed promotion",
            ),
            (
                "task acceptance",
                "judge calibration",
                "attack success rate",
                "over-refusal",
                "sealed holdout",
                "cost and latency",
            ),
            "template.llm-evaluation-harness",
            examples=("duecare-llm-evaluation-harness",),
            tags=("llm", "agent", "evaluation", "red-team", "sealed-holdout"),
        ),
        _task(
            "video-media-assurance",
            "Video and audio assets to an assurance report",
            "Probe streams, normalize timelines, align modalities, verify captions, and publish bounded media evidence.",
            "Captured media metadata or bytes, caption tracks, rights context, and quality policy.",
            "Timeline, synchronization, caption, integrity, policy, and provenance report.",
            ("ingest", "probe", "timeline", "align", "captions", "assure", "publish"),
            ("integrity", "dropped frames", "A/V sync", "caption timing", "quality", "rights"),
            "template.video-media-pipeline",
            examples=("video-media-assurance",),
            external=(
                "The bundled fixture validates timeline metadata only. Real codecs, perceptual quality, and delivery variants require a media runtime adapter.",
            ),
            tags=("video", "audio", "captions", "media-assurance"),
        ),
        _task(
            "three-d-asset-assurance",
            "3D assets to a validated optimized bundle",
            "Validate geometry, materials, collisions, budgets, renders, and export contracts.",
            "Versioned meshes, scenes, materials, textures, coordinate systems, collision intent, and budgets.",
            "Validated assets, defect and repair ledger, performance profile, renders, exports, and provenance.",
            ("ingest", "coordinates", "topology", "materials", "collision", "optimize", "render", "export"),
            ("manifoldness", "degenerates", "reference closure", "collision bounds", "triangle and memory budgets"),
            "template.three-d-asset-pipeline",
            examples=("three-d-asset-assurance",),
            external=(
                "The bundled tetrahedron fixture proves mesh-contract mechanics; engine rendering and physics require production adapters.",
            ),
            tags=("three-d", "mesh", "asset-pipeline", "simulation"),
        ),
        _task(
            "game-build-playtest",
            "Game rules and content to a release decision",
            "Build reproducibly, replay state transitions, run automated and human playtests, audit balance and accessibility, and gate release.",
            "Versioned game state, rules, code, content, target platforms, replays, player slices, and release policy.",
            "Builds, replay hashes, regressions, balance and performance evidence, human playtest evidence, and rollback plan.",
            ("contract", "build", "replay", "agent playtest", "balance", "performance", "accessibility", "human review", "release"),
            ("determinism", "crash-free rate", "frame time", "input latency", "balance", "exploit rate", "accessibility"),
            "template.game-build-playtest",
            examples=("gameplay-replay-and-balance",),
            external=(
                "The bundled fixture exercises deterministic rules and balance accounting only; engine builds and subjective fun require adapters and human evidence.",
            ),
            tags=("game", "playtest", "replay", "balance", "release"),
        ),
        _task(
            "robotics-control-assurance",
            "Robot task to a safety-gated execution plan",
            "Estimate state, plan, simulate, verify safety, require authority, monitor execution, and recover to a safe state.",
            "Robot and environment models, observations, task goal, safety envelope, and physical-effect authority.",
            "Feasible plan, simulation and safety evidence, approvals, execution telemetry, and recovery receipt.",
            ("model", "perceive", "plan", "feasibility", "simulate", "safety", "approve", "execute", "recover"),
            ("collision margin", "constraint violations", "state divergence", "stop response", "task success"),
            "template.robotics-control",
            examples=("robotics-safety-simulation",),
            external=(
                "The bundled fixture has no physical effects. Real robots require enforcing controllers, device authority, emergency stops, and domain safety validation.",
            ),
            tags=("robotics", "control", "safety", "simulation"),
        ),
        _task(
            "iot-fleet-assurance",
            "Device telemetry to fleet state and anomaly evidence",
            "Authenticate and normalize event-time telemetry, derive device state, detect anomalies, and gate commands and firmware rollout.",
            "Device identities, firmware versions, telemetry events, schemas, fleet policy, and command authority.",
            "Fleet state, anomalies, event-time evidence, command or rollout plan, and lifecycle receipt.",
            ("identity", "schema", "event-time", "deduplicate", "state", "anomaly", "command", "rollout", "monitor"),
            ("event integrity", "late and duplicate handling", "fleet coverage", "anomaly evidence", "rollback readiness"),
            "template.embedded-iot-system",
            examples=("iot-telemetry-assurance",),
            external=(
                "The bundled fixture uses unauthenticated finite telemetry; real devices require key management, signed firmware, enforcing command channels, and hardware testing.",
            ),
            tags=("iot", "embedded", "telemetry", "firmware"),
        ),
        _task(
            "digital-twin-validation",
            "Observed system to a validated simulation and decision dossier",
            "Calibrate a model, simulate scenarios, validate on untouched observations, quantify sensitivity, and bound applicability.",
            "System identity, model family, calibration observations, validation observations, scenarios, and decision contract.",
            "Calibrated model identity, simulations, residual and sensitivity evidence, applicability bounds, and reviewed recommendation.",
            ("scope", "assimilate", "calibrate", "simulate", "uncertainty", "sensitivity", "validate", "decide"),
            ("untouched residual", "coverage", "sensitivity", "regime validity", "decision uncertainty"),
            "template.digital-twin-simulation",
            examples=("digital-twin-validation",),
            external=(
                "The bundled linear fixture does not validate fidelity for any physical system; production twins require domain models and representative observations.",
            ),
            tags=("digital-twin", "simulation", "calibration", "decision-support"),
        ),
        _task(
            "healthcare-decision-support",
            "Longitudinal health data to reviewed decision-support evidence",
            "Govern access, normalize clinical data, reconcile a timeline, apply bounded decision support, and require qualified review.",
            "Authorized health records, terminology versions, intended-use contract, consent, and clinical review policy.",
            "Source-grounded evidence, uncertainty and applicability, qualified review state, and governed audit receipt.",
            ("govern", "normalize", "terminology", "identity", "timeline", "analyze", "uncertainty", "clinical review", "monitor"),
            ("clinical validity", "subgroup safety", "abstention", "workflow fit", "privacy", "adverse events"),
            "template.healthcare-evidence",
            external=(
                "Clinical use requires representative data, regulatory and institutional review, qualified human oversight, privacy controls, and production validation.",
            ),
            tags=("healthcare", "clinical-data", "privacy", "human-review"),
        ),
        _task(
            "product-experimentation",
            "Product hypothesis to a causal rollout decision",
            "Preregister metrics and allocation, verify instrumentation, run a controlled experiment, estimate effects, and monitor rollout.",
            "Hypothesis, eligible population, randomization unit, intervention, metrics, guardrails, power, and decision policy.",
            "Assignment and exposure evidence, effect estimates, uncertainty, deviations, decision, and rollout monitoring plan.",
            ("design", "instrument", "allocate", "monitor", "validate", "estimate", "sensitivity", "decide", "rollout"),
            ("sample ratio", "primary effect", "guardrails", "uncertainty", "heterogeneity", "long-term effect"),
            "template.product-experimentation",
            examples=("scientific-experiment", "user-journey-modeling"),
            tags=("product", "experiment", "causal", "analytics"),
        ),
        _task(
            "education-assessment",
            "Learning objectives to an assured assessment",
            "Author aligned content and items, verify accuracy and accessibility, score accountably, and analyze validity and fairness.",
            "Learning objectives, standards, learner population, content sources, accommodation policy, and assessment claims.",
            "Versioned content, items, rubrics, scoring evidence, review state, item analysis, and limitations.",
            ("contract", "source", "author", "accuracy", "alignment", "accessibility", "bias", "deliver", "score", "review", "analyze"),
            ("content accuracy", "alignment", "reliability", "validity", "fairness", "accessibility"),
            "template.education-assessment",
            tags=("education", "assessment", "rubric", "accessibility"),
        ),
        _task(
            "creative-content-production",
            "Creative brief to governed campaign variants",
            "Research, generate, assemble, edit, verify rights and quality, experiment, publish, and monitor creative assets.",
            "Audience, goal, channel, brand policy, source assets, rights, formats, and experiment contract.",
            "Traceable creative variants, rights and review evidence, channel packages, experiment outcomes, and provenance.",
            ("brief", "rights", "research", "concept", "generate", "assemble", "edit", "assure", "package", "experiment", "monitor"),
            ("brand compliance", "technical quality", "accessibility", "rights coverage", "policy", "campaign outcome"),
            "template.creative-content-production",
            tags=("creative", "campaign", "media", "experimentation"),
        ),
        _task(
            "content-policy-moderation",
            "Multimodal content to a reviewable policy action",
            "Bind policy context, extract multimodal evidence, combine detectors, act proportionately, review, and appeal.",
            "Content, conversation and product context, policy version, jurisdiction, audience, and action authority.",
            "Policy categories, calibrated severity, action, reasons, review state, and appeal evidence.",
            (
                "policy",
                "decode",
                "language",
                "signals",
                "rules",
                "models",
                "cross-check",
                "decide",
                "review",
                "appeal",
            ),
            (
                "category precision and recall",
                "severity calibration",
                "appeal overturn rate",
                "consistency",
                "latency",
            ),
            "template.content-moderation",
            tags=("moderation", "policy", "safety"),
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
        executor = ReferenceExecutor(runtimes=RuntimeRegistry({"python": PythonRuntime()}))
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
