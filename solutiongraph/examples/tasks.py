"""Six executable examples that use one universal registry and executor."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from solutiongraph.artifacts import FileArtifactStore, MemoryArtifactStore
from solutiongraph.compiler import Compiler
from solutiongraph.evidence import ExperimentDesign, Objective
from solutiongraph.examples import nodes as implementations
from solutiongraph.executor import (
    CallableVerifier,
    ExecutionPolicy,
    PythonRuntime,
    ReferenceExecutor,
    RuntimeRegistry,
    VerificationContext,
    VerificationResult,
    callable_implementation_digest,
)
from solutiongraph.experiments import ExperimentCase, ExperimentRunner
from solutiongraph.ledger import JsonlReceiptJournal
from solutiongraph.model import (
    Candidate,
    Determinism,
    Edge,
    FailureMode,
    GraphInput,
    GraphOutput,
    Idempotency,
    NodeSpec,
    ParameterSpec,
    Port,
    ProgramGraph,
    Registry,
    SemanticSlot,
    ValueType,
)
from solutiongraph.subprocess_runtime import SubprocessPythonRuntime

WEB_SOURCE = ValueType("example.web-source")
HTML_DOCUMENT = ValueType("example.html-document", media_type="text/html")
PAGE_RECORD = ValueType("example.page-record")
SCRAPE_RESULT = ValueType("example.scrape-result")

DOCUMENT_TEXT = ValueType("example.document-text", media_type="text/plain")
NORMALIZED_TEXT = ValueType("example.normalized-text", media_type="text/plain")
FIELD_MAP = ValueType("example.field-map")
DOCUMENT_RECORD = ValueType("example.document-record")

PGM_DOCUMENT = ValueType("example.pgm-document", media_type="image/x-portable-graymap")
GRAY_IMAGE = ValueType("example.gray-image")
IMAGE_REPORT = ValueType("example.image-report")

RAW_RECORDS = ValueType("example.raw-records")
NORMALIZED_RECORDS = ValueType("example.normalized-records")
DEDUPLICATED_RECORDS = ValueType("example.deduplicated-records")
CLEAN_RECORDS = ValueType("example.clean-records")

REGRESSION_DATASET = ValueType("example.regression-dataset")
REGRESSION_SPLIT = ValueType("example.regression-split")
REGRESSION_MODEL = ValueType("example.regression-model")
REGRESSION_RESULT = ValueType("example.regression-result")

CLASSIFICATION_DATASET = ValueType("example.classification-dataset")
CLASSIFICATION_SPLIT = ValueType("example.classification-split")
CLASSIFICATION_MODEL = ValueType("example.classification-model")
CLASSIFICATION_RESULT = ValueType("example.classification-result")


def _node(
    node_id: str,
    function: Callable[..., Any],
    capability: str,
    inputs: tuple[Port, ...],
    outputs: tuple[Port, ...],
    description: str,
    *,
    parameters: tuple[ParameterSpec, ...] = (),
    effects: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
    determinism: Determinism = Determinism.DETERMINISTIC,
    failure_modes: tuple[FailureMode, ...] = (),
) -> NodeSpec:
    return NodeSpec(
        id=node_id,
        version="1.0.0",
        implementation_digest=callable_implementation_digest(function),
        inputs=inputs,
        outputs=outputs,
        runtime="python",
        entrypoint=f"solutiongraph.examples.nodes:{function.__name__}",
        description=description,
        parameters=parameters,
        capabilities=(capability,),
        effects=effects,
        permissions=permissions,
        determinism=determinism,
        idempotency=Idempotency.IDEMPOTENT,
        failure_modes=failure_modes,
        source="solutiongraph/examples/nodes.py",
    )


def _candidate(
    node: NodeSpec,
    *,
    suffix: str = "default",
    parameters: Mapping[str, Any] | None = None,
) -> Candidate:
    return Candidate(
        id=f"candidate.{node.id}.{suffix}",
        node_id=node.id,
        node_version=node.version,
        implementation_digest=node.implementation_digest,
        parameters=dict(parameters or {}),
    )


NODES = (
    _node(
        "example.web.load.offline",
        implementations.load_web_source_offline,
        "web.load",
        (Port("source", WEB_SOURCE),),
        (Port("html", HTML_DOCUMENT),),
        "Load inline HTML or a text data URL without external network access.",
        failure_modes=(
            FailureMode("web.offline-source-unavailable", False, "No offline payload exists."),
            FailureMode("web.invalid-data-url", False, "The data URL is malformed."),
        ),
    ),
    _node(
        "example.web.load.urllib",
        implementations.load_web_source_urllib,
        "web.load",
        (Port("source", WEB_SOURCE),),
        (Port("html", HTML_DOCUMENT),),
        "Fetch one explicit read-only URL with the Python standard library.",
        parameters=(ParameterSpec("timeout_seconds", "number", default=10.0),),
        effects=("network.read",),
        permissions=("network.read",),
        determinism=Determinism.RECORDED,
        failure_modes=(
            FailureMode("web.missing-url", False, "No URL was supplied."),
            FailureMode("web.invalid-url", False, "The supplied URL is malformed."),
            FailureMode("network.http-error", True, "The read-only fetch failed."),
        ),
    ),
    _node(
        "example.web.extract.parser",
        implementations.extract_page_html_parser,
        "web.extract",
        (Port("html", HTML_DOCUMENT),),
        (Port("page", PAGE_RECORD),),
        "Extract title, visible text, and links with HTMLParser.",
    ),
    _node(
        "example.web.extract.regex",
        implementations.extract_page_regex,
        "web.extract",
        (Port("html", HTML_DOCUMENT),),
        (Port("page", PAGE_RECORD),),
        "Extract the same fields with a simple regular-expression strategy.",
    ),
    _node(
        "example.web.project.schema",
        implementations.project_page_schema,
        "web.project-schema",
        (Port("page", PAGE_RECORD),),
        (Port("result", SCRAPE_RESULT),),
        "Project extracted page fields into a declared result schema.",
        parameters=(ParameterSpec("fields", "array[string]", required=True),),
        failure_modes=(FailureMode("schema.missing-field", False),),
    ),
    _node(
        "example.document.normalize.conservative",
        implementations.normalize_document_conservative,
        "document.normalize",
        (Port("document", DOCUMENT_TEXT),),
        (Port("text", NORMALIZED_TEXT),),
        "Normalize line endings while preserving record boundaries.",
    ),
    _node(
        "example.document.normalize.compact",
        implementations.normalize_document_compact,
        "document.normalize",
        (Port("document", DOCUMENT_TEXT),),
        (Port("text", NORMALIZED_TEXT),),
        "Compact repeated whitespace while preserving nonempty record lines.",
    ),
    _node(
        "example.document.extract.lines",
        implementations.extract_document_lines,
        "document.extract-fields",
        (Port("text", NORMALIZED_TEXT),),
        (Port("fields", FIELD_MAP),),
        "Parse colon-delimited fields one line at a time.",
    ),
    _node(
        "example.document.extract.regex",
        implementations.extract_document_regex,
        "document.extract-fields",
        (Port("text", NORMALIZED_TEXT),),
        (Port("fields", FIELD_MAP),),
        "Parse colon-delimited fields with a multiline expression.",
    ),
    _node(
        "example.document.project.schema",
        implementations.project_document_schema,
        "document.project-schema",
        (Port("fields", FIELD_MAP),),
        (Port("result", DOCUMENT_RECORD),),
        "Require and project an exact requested document schema.",
        parameters=(ParameterSpec("required_fields", "array[string]", required=True),),
        failure_modes=(FailureMode("schema.missing-field", False),),
    ),
    _node(
        "example.image.decode.tokens",
        implementations.decode_pgm_tokens,
        "image.decode",
        (Port("document", PGM_DOCUMENT),),
        (Port("image", GRAY_IMAGE),),
        "Decode an ASCII PGM image with a token scanner.",
        failure_modes=(
            FailureMode("image.unsupported-format", False),
            FailureMode("image.invalid-header", False),
            FailureMode("image.invalid-pixels", False),
        ),
    ),
    _node(
        "example.image.decode.lines",
        implementations.decode_pgm_lines,
        "image.decode",
        (Port("document", PGM_DOCUMENT),),
        (Port("image", GRAY_IMAGE),),
        "Decode the same ASCII PGM contract with a line parser.",
        failure_modes=(
            FailureMode("image.unsupported-format", False),
            FailureMode("image.invalid-header", False),
            FailureMode("image.invalid-pixels", False),
        ),
    ),
    _node(
        "example.image.enhance.identity",
        implementations.enhance_image_identity,
        "image.enhance",
        (Port("image", GRAY_IMAGE),),
        (Port("image", GRAY_IMAGE),),
        "Explicitly certify that no contrast transformation is required.",
    ),
    _node(
        "example.image.enhance.minmax",
        implementations.enhance_image_minmax,
        "image.enhance",
        (Port("image", GRAY_IMAGE),),
        (Port("image", GRAY_IMAGE),),
        "Stretch observed pixels across the declared grayscale range.",
    ),
    _node(
        "example.image.inspect.mean",
        implementations.inspect_image_mean,
        "image.inspect",
        (Port("image", GRAY_IMAGE),),
        (Port("report", IMAGE_REPORT),),
        "Measure dimensions and contrast directly from pixels.",
    ),
    _node(
        "example.image.inspect.histogram",
        implementations.inspect_image_histogram,
        "image.inspect",
        (Port("image", GRAY_IMAGE),),
        (Port("report", IMAGE_REPORT),),
        "Measure the same contract through a grayscale histogram.",
    ),
    _node(
        "example.data.normalize.conservative",
        implementations.normalize_records_conservative,
        "data.normalize-records",
        (Port("records", RAW_RECORDS),),
        (Port("records", NORMALIZED_RECORDS),),
        "Normalize field names, whitespace, and email casing.",
    ),
    _node(
        "example.data.normalize.aggressive",
        implementations.normalize_records_aggressive,
        "data.normalize-records",
        (Port("records", RAW_RECORDS),),
        (Port("records", NORMALIZED_RECORDS),),
        "Add person, company, and phone canonicalization.",
    ),
    _node(
        "example.data.deduplicate.exact",
        implementations.deduplicate_records_exact,
        "data.deduplicate",
        (Port("records", NORMALIZED_RECORDS),),
        (Port("records", DEDUPLICATED_RECORDS),),
        "Deduplicate configured fields by exact equality.",
        parameters=(ParameterSpec("key_fields", "array[string]", required=True),),
    ),
    _node(
        "example.data.deduplicate.normalized",
        implementations.deduplicate_records_normalized,
        "data.deduplicate",
        (Port("records", NORMALIZED_RECORDS),),
        (Port("records", DEDUPLICATED_RECORDS),),
        "Deduplicate configured fields by normalized alphanumeric equality.",
        parameters=(ParameterSpec("key_fields", "array[string]", required=True),),
    ),
    _node(
        "example.data.sort",
        implementations.sort_records,
        "data.emit-clean",
        (Port("records", DEDUPLICATED_RECORDS),),
        (Port("records", CLEAN_RECORDS),),
        "Emit cleaned records in a deterministic order.",
        parameters=(ParameterSpec("sort_key", "string", required=True),),
    ),
    _node(
        "example.ml.split.tail",
        implementations.split_regression_tail,
        "ml.split-regression",
        (Port("dataset", REGRESSION_DATASET),),
        (Port("split", REGRESSION_SPLIT),),
        "Reserve the last observations as a deterministic holdout.",
        parameters=(ParameterSpec("holdout_size", "integer", default=2),),
        failure_modes=(FailureMode("ml.invalid-split", False),),
    ),
    _node(
        "example.ml.split.alternating",
        implementations.split_regression_alternating,
        "ml.split-regression",
        (Port("dataset", REGRESSION_DATASET),),
        (Port("split", REGRESSION_SPLIT),),
        "Use deterministic alternating rows for train and holdout partitions.",
        failure_modes=(FailureMode("ml.invalid-split", False),),
    ),
    _node(
        "example.ml.train.mean",
        implementations.train_mean_regressor,
        "ml.train-regression",
        (Port("split", REGRESSION_SPLIT),),
        (Port("model", REGRESSION_MODEL),),
        "Fit an intercept-only regression baseline.",
    ),
    _node(
        "example.ml.train.linear",
        implementations.train_linear_regressor,
        "ml.train-regression",
        (Port("split", REGRESSION_SPLIT),),
        (Port("model", REGRESSION_MODEL),),
        "Fit a one-feature ordinary least-squares model.",
        failure_modes=(FailureMode("ml.constant-feature", False),),
    ),
    _node(
        "example.ml.evaluate",
        implementations.evaluate_regressor,
        "ml.evaluate-regression",
        (Port("split", REGRESSION_SPLIT), Port("model", REGRESSION_MODEL)),
        (Port("result", REGRESSION_RESULT),),
        "Measure holdout RMSE and generate requested predictions.",
        failure_modes=(FailureMode("ml.unknown-model", False),),
    ),
    _node(
        "example.ml.classification.split.tail",
        implementations.split_classification_tail,
        "ml.split-classification",
        (Port("dataset", CLASSIFICATION_DATASET),),
        (Port("split", CLASSIFICATION_SPLIT),),
        "Reserve the last labeled observations as a deterministic holdout.",
        parameters=(ParameterSpec("holdout_size", "integer", default=2),),
        failure_modes=(FailureMode("ml.invalid-split", False),),
    ),
    _node(
        "example.ml.classification.split.alternating",
        implementations.split_classification_alternating,
        "ml.split-classification",
        (Port("dataset", CLASSIFICATION_DATASET),),
        (Port("split", CLASSIFICATION_SPLIT),),
        "Use deterministic alternating rows for classification partitions.",
        failure_modes=(FailureMode("ml.invalid-split", False),),
    ),
    _node(
        "example.ml.classification.train.majority",
        implementations.train_majority_classifier,
        "ml.train-classification",
        (Port("split", CLASSIFICATION_SPLIT),),
        (Port("model", CLASSIFICATION_MODEL),),
        "Fit an explicit majority-class control model.",
        failure_modes=(FailureMode("ml.empty-training-set", False),),
    ),
    _node(
        "example.ml.classification.train.threshold",
        implementations.train_threshold_classifier,
        "ml.train-classification",
        (Port("split", CLASSIFICATION_SPLIT),),
        (Port("model", CLASSIFICATION_MODEL),),
        "Fit a one-feature binary threshold model.",
        failure_modes=(FailureMode("ml.nonbinary-target", False),),
    ),
    _node(
        "example.ml.classification.evaluate",
        implementations.evaluate_classifier,
        "ml.evaluate-classification",
        (Port("split", CLASSIFICATION_SPLIT), Port("model", CLASSIFICATION_MODEL)),
        (Port("result", CLASSIFICATION_RESULT),),
        "Measure holdout accuracy and generate requested class predictions.",
        failure_modes=(FailureMode("ml.unknown-model", False),),
    ),
)


def _parameters_for(node: NodeSpec) -> tuple[str, Mapping[str, Any]]:
    configured: dict[str, tuple[str, Mapping[str, Any]]] = {
        "example.web.project.schema": ("title-links", {"fields": ["title", "links"]}),
        "example.document.project.schema": (
            "invoice",
            {"required_fields": ["name", "invoice_total"]},
        ),
        "example.data.deduplicate.exact": ("company", {"key_fields": ["company"]}),
        "example.data.deduplicate.normalized": (
            "company",
            {"key_fields": ["company"]},
        ),
        "example.data.sort": ("company", {"sort_key": "company"}),
    }
    return configured.get(node.id, ("default", {}))


CANDIDATES = tuple(
    _candidate(node, suffix=_parameters_for(node)[0], parameters=_parameters_for(node)[1])
    for node in NODES
)

EXAMPLE_REGISTRY = Registry(
    id="example.real-world-registry",
    version="1.0.0",
    nodes=NODES,
    candidates=CANDIDATES,
)


def _candidate_id(node_id: str) -> str:
    node = next(item for item in NODES if item.id == node_id)
    suffix, _ = _parameters_for(node)
    return f"candidate.{node_id}.{suffix}"


def _slot(
    slot_id: str,
    purpose: str,
    input_ports: tuple[Port, ...],
    output_ports: tuple[Port, ...],
    capability: str,
    success: str,
    *,
    allowed_effects: tuple[str, ...] = (),
    optional: bool = False,
) -> SemanticSlot:
    return SemanticSlot(
        id=slot_id,
        purpose=purpose,
        inputs=input_ports,
        outputs=output_ports,
        success_contract=success,
        required_capabilities=(capability,),
        allowed_effects=allowed_effects,
        optional=optional,
    )


@dataclass(frozen=True)
class ExampleRoute:
    id: str
    description: str
    selection: Mapping[str, str]
    fallbacks: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    expected_accepted: bool = True

    def fallback_map(self) -> Mapping[str, tuple[str, ...]]:
        return self.fallbacks or {}


@dataclass(frozen=True)
class ExecutableExample:
    id: str
    title: str
    description: str
    program: ProgramGraph
    routes: tuple[ExampleRoute, ...]
    case: ExperimentCase
    policy: ExecutionPolicy
    objectives: tuple[Objective, ...]
    registry: Registry = EXAMPLE_REGISTRY

    def compile(self):
        compiler = Compiler()
        space = compiler.admit(self.program, self.registry)
        plans = {
            route.id: compiler.compile(
                self.program,
                self.registry,
                space,
                route.selection,
                fallbacks=route.fallback_map(),
            )
            for route in self.routes
        }
        return space, plans


def _browse_verifier(context: VerificationContext) -> VerificationResult:
    result = context.outputs["result"]
    accepted = result.get("title") == "Universal Graph Example" and result.get("links") == ["/alpha", "/beta"]
    return VerificationResult(
        accepted=accepted,
        outcome="schema-and-content-match" if accepted else "content-mismatch",
        metrics={"quality": 1.0 if accepted else 0.0},
        details={"expected_title": "Universal Graph Example"},
    )


def _document_verifier(context: VerificationContext) -> VerificationResult:
    expected = {"name": "Taylor Amarel", "invoice_total": "$125.50"}
    actual = context.outputs["result"]
    matches = sum(actual.get(key) == value for key, value in expected.items())
    quality = matches / len(expected)
    return VerificationResult(
        accepted=quality == 1.0,
        outcome="all-fields-grounded" if quality == 1.0 else "field-mismatch",
        metrics={"quality": quality},
        details={"expected": expected, "actual": actual},
    )


def _image_verifier(context: VerificationContext) -> VerificationResult:
    report = context.outputs["report"]
    accepted = (
        report.get("width") == 4
        and report.get("height") == 3
        and report.get("maximum", 0) > report.get("minimum", 0)
    )
    contrast = float(report.get("contrast", 0.0))
    return VerificationResult(
        accepted=accepted,
        outcome="image-measurements-valid" if accepted else "invalid-image-measurements",
        metrics={"quality": min(1.0, contrast / 15.0)},
        details={"report": report},
    )


def _data_verifier(context: VerificationContext) -> VerificationResult:
    records = context.outputs["records"]
    companies = [re.sub(r"[^a-z0-9]+", "", str(item.get("company", "")).lower()) for item in records]
    accepted = len(records) == 2 and len(companies) == len(set(companies))
    return VerificationResult(
        accepted=accepted,
        outcome="records-clean-and-unique" if accepted else "duplicate-or-count-mismatch",
        metrics={"quality": 1.0 if accepted else 0.0},
        details={"record_count": len(records), "normalized_companies": companies},
    )


def _ml_verifier(context: VerificationContext) -> VerificationResult:
    result = context.outputs["result"]
    rmse = float(result["rmse"])
    finite = all(math.isfinite(float(value)) for value in result["predictions"])
    accepted = finite and rmse <= 0.5
    return VerificationResult(
        accepted=accepted,
        outcome="holdout-threshold-met" if accepted else "holdout-threshold-missed",
        metrics={"quality": 1.0 / (1.0 + rmse), "rmse": rmse},
        details={"rmse_limit": 0.5, "model": result["model"]},
    )


def _classification_verifier(context: VerificationContext) -> VerificationResult:
    result = context.outputs["result"]
    accuracy = float(result["accuracy"])
    accepted = accuracy >= 0.9 and len(result["predictions"]) == 3
    return VerificationResult(
        accepted=accepted,
        outcome="holdout-threshold-met" if accepted else "holdout-threshold-missed",
        metrics={"quality": accuracy, "accuracy": accuracy},
        details={"accuracy_limit": 0.9, "model": result["model"]},
    )


BROWSE_PROGRAM = ProgramGraph(
    id="example.browse-and-scrape",
    version="1.0.0",
    task="Load one authorized web source and extract a declared page schema.",
    success_contract="An independent verifier accepts the exact title and link set.",
    slots=(
        _slot(
            "load",
            "Load the authorized web representation.",
            (Port("source", WEB_SOURCE),),
            (Port("html", HTML_DOCUMENT),),
            "web.load",
            "HTML is available for parsing.",
            allowed_effects=("network.read",),
        ),
        _slot(
            "extract",
            "Extract page content and links.",
            (Port("html", HTML_DOCUMENT),),
            (Port("page", PAGE_RECORD),),
            "web.extract",
            "Page fields are structurally present.",
        ),
        _slot(
            "project",
            "Project the requested scrape schema.",
            (Port("page", PAGE_RECORD),),
            (Port("result", SCRAPE_RESULT),),
            "web.project-schema",
            "The requested result fields exist.",
        ),
    ),
    edges=(Edge("load", "html", "extract", "html"), Edge("extract", "page", "project", "page")),
    inputs=(GraphInput("source", WEB_SOURCE, "load", "source"),),
    outputs=(GraphOutput("result", SCRAPE_RESULT, "project", "result"),),
    allowed_effects=("network.read",),
    granted_permissions=("network.read",),
)

DOCUMENT_PROGRAM = ProgramGraph(
    id="example.document-to-schema",
    version="1.0.0",
    task="Extract a requested schema from an unknown key/value document.",
    success_contract="An independent verifier matches every required field to expected evidence.",
    slots=(
        _slot("normalize", "Normalize document text.", (Port("document", DOCUMENT_TEXT),), (Port("text", NORMALIZED_TEXT),), "document.normalize", "Normalized text preserves field records."),
        _slot("extract", "Extract candidate key/value fields.", (Port("text", NORMALIZED_TEXT),), (Port("fields", FIELD_MAP),), "document.extract-fields", "Candidate fields are explicit."),
        _slot("project", "Project and require the target schema.", (Port("fields", FIELD_MAP),), (Port("result", DOCUMENT_RECORD),), "document.project-schema", "Every required output field is nonempty."),
    ),
    edges=(Edge("normalize", "text", "extract", "text"), Edge("extract", "fields", "project", "fields")),
    inputs=(GraphInput("document", DOCUMENT_TEXT, "normalize", "document"),),
    outputs=(GraphOutput("result", DOCUMENT_RECORD, "project", "result"),),
)

IMAGE_PROGRAM = ProgramGraph(
    id="example.image-check-and-process",
    version="1.0.0",
    task="Decode, optionally enhance, and inspect an image.",
    success_contract="An independent verifier accepts the measured dimensions and contrast.",
    slots=(
        _slot("decode", "Decode the image representation.", (Port("document", PGM_DOCUMENT),), (Port("image", GRAY_IMAGE),), "image.decode", "Every declared pixel is decoded."),
        _slot("enhance", "Apply or certify contrast processing.", (Port("image", GRAY_IMAGE),), (Port("image", GRAY_IMAGE),), "image.enhance", "Output remains a valid same-size grayscale image.", optional=True),
        _slot("inspect", "Measure image integrity and quality.", (Port("image", GRAY_IMAGE),), (Port("report", IMAGE_REPORT),), "image.inspect", "Dimensions, range, mean, and contrast are measured."),
    ),
    edges=(Edge("decode", "image", "enhance", "image"), Edge("enhance", "image", "inspect", "image")),
    inputs=(GraphInput("document", PGM_DOCUMENT, "decode", "document"),),
    outputs=(GraphOutput("report", IMAGE_REPORT, "inspect", "report"),),
)

DATA_PROGRAM = ProgramGraph(
    id="example.data-cleanup",
    version="1.0.0",
    task="Normalize, deduplicate, and deterministically emit business records.",
    success_contract="An independent verifier finds the expected unique entities.",
    slots=(
        _slot("normalize", "Normalize record fields and values.", (Port("records", RAW_RECORDS),), (Port("records", NORMALIZED_RECORDS),), "data.normalize-records", "Every record uses canonical field names."),
        _slot("deduplicate", "Remove duplicate entities.", (Port("records", NORMALIZED_RECORDS),), (Port("records", DEDUPLICATED_RECORDS),), "data.deduplicate", "No duplicate configured identity remains."),
        _slot("emit", "Emit deterministic cleaned records.", (Port("records", DEDUPLICATED_RECORDS),), (Port("records", CLEAN_RECORDS),), "data.emit-clean", "Output order is reproducible."),
    ),
    edges=(Edge("normalize", "records", "deduplicate", "records"), Edge("deduplicate", "records", "emit", "records")),
    inputs=(GraphInput("records", RAW_RECORDS, "normalize", "records"),),
    outputs=(GraphOutput("records", CLEAN_RECORDS, "emit", "records"),),
)

ML_PROGRAM = ProgramGraph(
    id="example.tabular-regression",
    version="1.0.0",
    task="Split tabular data, fit a regression candidate, and measure holdout behavior.",
    success_contract="An independent verifier accepts finite predictions below the RMSE limit.",
    slots=(
        _slot("split", "Create a leakage-visible train/holdout split.", (Port("dataset", REGRESSION_DATASET),), (Port("split", REGRESSION_SPLIT),), "ml.split-regression", "Train and holdout rows are nonempty."),
        _slot("train", "Fit one regression model contract.", (Port("split", REGRESSION_SPLIT),), (Port("model", REGRESSION_MODEL),), "ml.train-regression", "A serializable prediction model is produced."),
        _slot("evaluate", "Measure holdout error and predict requested values.", (Port("split", REGRESSION_SPLIT), Port("model", REGRESSION_MODEL)), (Port("result", REGRESSION_RESULT),), "ml.evaluate-regression", "RMSE and predictions are finite."),
    ),
    edges=(
        Edge("split", "split", "train", "split"),
        Edge("split", "split", "evaluate", "split"),
        Edge("train", "model", "evaluate", "model"),
    ),
    inputs=(GraphInput("dataset", REGRESSION_DATASET, "split", "dataset"),),
    outputs=(GraphOutput("result", REGRESSION_RESULT, "evaluate", "result"),),
)

CLASSIFICATION_PROGRAM = ProgramGraph(
    id="example.tabular-classification",
    version="1.0.0",
    task="Split labeled tabular data, fit a classifier, and measure holdout behavior.",
    success_contract="An independent verifier accepts accuracy above the declared limit.",
    slots=(
        _slot(
            "split",
            "Create a leakage-visible train/holdout split.",
            (Port("dataset", CLASSIFICATION_DATASET),),
            (Port("split", CLASSIFICATION_SPLIT),),
            "ml.split-classification",
            "Train and holdout rows are nonempty.",
        ),
        _slot(
            "train",
            "Fit one classification model contract.",
            (Port("split", CLASSIFICATION_SPLIT),),
            (Port("model", CLASSIFICATION_MODEL),),
            "ml.train-classification",
            "A serializable classification model is produced.",
        ),
        _slot(
            "evaluate",
            "Measure holdout accuracy and predict requested labels.",
            (Port("split", CLASSIFICATION_SPLIT), Port("model", CLASSIFICATION_MODEL)),
            (Port("result", CLASSIFICATION_RESULT),),
            "ml.evaluate-classification",
            "Accuracy and class predictions are explicit.",
        ),
    ),
    edges=(
        Edge("split", "split", "train", "split"),
        Edge("split", "split", "evaluate", "split"),
        Edge("train", "model", "evaluate", "model"),
    ),
    inputs=(GraphInput("dataset", CLASSIFICATION_DATASET, "split", "dataset"),),
    outputs=(GraphOutput("result", CLASSIFICATION_RESULT, "evaluate", "result"),),
)


def _route(
    route_id: str,
    description: str,
    choices: Mapping[str, str],
    fallbacks=None,
    *,
    expected_accepted: bool = True,
) -> ExampleRoute:
    return ExampleRoute(
        route_id,
        description,
        dict(choices),
        fallbacks or {},
        expected_accepted,
    )


EXAMPLE_TASKS = (
    ExecutableExample(
        "browse-and-scrape",
        "Browse and scrape",
        "Load an offline web fixture through interchangeable loaders and extractors.",
        BROWSE_PROGRAM,
        (
            _route("baseline", "Offline loader and structural parser.", {"load": _candidate_id("example.web.load.offline"), "extract": _candidate_id("example.web.extract.parser"), "project": _candidate_id("example.web.project.schema")}, {"extract": (_candidate_id("example.web.extract.regex"),)}),
            _route("alternative", "Urllib-compatible loader and regex extractor.", {"load": _candidate_id("example.web.load.urllib"), "extract": _candidate_id("example.web.extract.regex"), "project": _candidate_id("example.web.project.schema")}, {"extract": (_candidate_id("example.web.extract.parser"),)}),
        ),
        ExperimentCase(
            "case.browse-and-scrape",
            {"source": {"html": "<html><head><title>Universal Graph Example</title></head><body><a href='/alpha'>Alpha</a><a href='/beta'>Beta</a></body></html>"}},
            CallableVerifier("verifier.example.browse", _browse_verifier),
        ),
        ExecutionPolicy(granted_permissions=("network.read",), allowed_effects=("network.read",)),
        (Objective("quality", "maximize"), Objective("latency_ms", "minimize")),
    ),
    ExecutableExample(
        "document-to-schema",
        "Ingest and extract into schema",
        "Normalize an unstructured invoice and compare two extraction strategies.",
        DOCUMENT_PROGRAM,
        (
            _route("baseline", "Conservative normalization and line parser.", {"normalize": _candidate_id("example.document.normalize.conservative"), "extract": _candidate_id("example.document.extract.lines"), "project": _candidate_id("example.document.project.schema")}, {"extract": (_candidate_id("example.document.extract.regex"),)}),
            _route("alternative", "Compact normalization and regex parser.", {"normalize": _candidate_id("example.document.normalize.compact"), "extract": _candidate_id("example.document.extract.regex"), "project": _candidate_id("example.document.project.schema")}, {"extract": (_candidate_id("example.document.extract.lines"),)}),
        ),
        ExperimentCase("case.document-to-schema", {"document": " INVOICE\r\n Name:   Taylor Amarel  \r\n Invoice Total: $125.50 \r\n"}, CallableVerifier("verifier.example.document", _document_verifier)),
        ExecutionPolicy(),
        (Objective("quality", "maximize"), Objective("latency_ms", "minimize")),
    ),
    ExecutableExample(
        "image-check-and-process",
        "Check and process image",
        "Decode a real PGM payload, compare enhancement, and verify measurements.",
        IMAGE_PROGRAM,
        (
            _route("baseline", "Token decode with explicit no-op enhancement.", {"decode": _candidate_id("example.image.decode.tokens"), "enhance": _candidate_id("example.image.enhance.identity"), "inspect": _candidate_id("example.image.inspect.mean")}),
            _route("enhanced", "Line decode, min-max contrast, and histogram inspection.", {"decode": _candidate_id("example.image.decode.lines"), "enhance": _candidate_id("example.image.enhance.minmax"), "inspect": _candidate_id("example.image.inspect.histogram")}),
        ),
        ExperimentCase("case.image-check-and-process", {"document": "P2\n# four by three\n4 3\n15\n0 2 4 6\n8 10 12 14\n1 3 5 7\n"}, CallableVerifier("verifier.example.image", _image_verifier)),
        ExecutionPolicy(),
        (Objective("quality", "maximize"), Objective("latency_ms", "minimize")),
    ),
    ExecutableExample(
        "data-cleanup",
        "Data cleanup",
        "Compare conservative/aggressive normalization and exact/normalized dedupe.",
        DATA_PROGRAM,
        (
            _route(
                "baseline",
                "Conservative normalization and exact dedupe.",
                {
                    "normalize": _candidate_id(
                        "example.data.normalize.conservative"
                    ),
                    "deduplicate": _candidate_id(
                        "example.data.deduplicate.exact"
                    ),
                    "emit": _candidate_id("example.data.sort"),
                },
                {
                    "deduplicate": (
                        _candidate_id("example.data.deduplicate.normalized"),
                    )
                },
                expected_accepted=False,
            ),
            _route(
                "robust",
                "Aggressive normalization and normalized dedupe.",
                {
                    "normalize": _candidate_id(
                        "example.data.normalize.aggressive"
                    ),
                    "deduplicate": _candidate_id(
                        "example.data.deduplicate.normalized"
                    ),
                    "emit": _candidate_id("example.data.sort"),
                },
            ),
        ),
        ExperimentCase("case.data-cleanup", {"records": [{"Company": "ACME, Inc.", "Email": "A@EXAMPLE.COM", "Phone": "(555) 0100"}, {"company": "Acme Inc", "email": "a@example.com", "phone": "555-0100"}, {"company": "Beta LLC", "email": "b@example.com", "phone": "555-0200"}]}, CallableVerifier("verifier.example.data", _data_verifier)),
        ExecutionPolicy(),
        (Objective("quality", "maximize"), Objective("latency_ms", "minimize")),
    ),
    ExecutableExample(
        "tabular-regression",
        "Data science regression",
        "Compare split strategies and baseline/linear models with a real holdout oracle.",
        ML_PROGRAM,
        (
            _route(
                "control",
                "Tail holdout with an intercept-only baseline.",
                {
                    "split": _candidate_id("example.ml.split.tail"),
                    "train": _candidate_id("example.ml.train.mean"),
                    "evaluate": _candidate_id("example.ml.evaluate"),
                },
                {"train": (_candidate_id("example.ml.train.linear"),)},
                expected_accepted=False,
            ),
            _route(
                "linear",
                "Tail holdout with ordinary least squares.",
                {
                    "split": _candidate_id("example.ml.split.tail"),
                    "train": _candidate_id("example.ml.train.linear"),
                    "evaluate": _candidate_id("example.ml.evaluate"),
                },
            ),
            _route(
                "alternate-split",
                "Alternating holdout with ordinary least squares.",
                {
                    "split": _candidate_id("example.ml.split.alternating"),
                    "train": _candidate_id("example.ml.train.linear"),
                    "evaluate": _candidate_id("example.ml.evaluate"),
                },
            ),
        ),
        ExperimentCase("case.tabular-regression", {"dataset": {"rows": [{"x": value, "y": 2 * value + 1} for value in range(1, 10)], "predict": [10, 12]}}, CallableVerifier("verifier.example.ml", _ml_verifier)),
        ExecutionPolicy(),
        (Objective("quality", "maximize"), Objective("latency_ms", "minimize")),
    ),
    ExecutableExample(
        "tabular-classification",
        "Data science classification",
        "Compare split strategies and majority/threshold classifiers with a holdout oracle.",
        CLASSIFICATION_PROGRAM,
        (
            _route(
                "control",
                "Tail holdout with a majority-class control.",
                {
                    "split": _candidate_id("example.ml.classification.split.tail"),
                    "train": _candidate_id("example.ml.classification.train.majority"),
                    "evaluate": _candidate_id("example.ml.classification.evaluate"),
                },
                {
                    "train": (
                        _candidate_id("example.ml.classification.train.threshold"),
                    )
                },
                expected_accepted=False,
            ),
            _route(
                "threshold",
                "Tail holdout with a learned one-feature threshold.",
                {
                    "split": _candidate_id("example.ml.classification.split.tail"),
                    "train": _candidate_id("example.ml.classification.train.threshold"),
                    "evaluate": _candidate_id("example.ml.classification.evaluate"),
                },
            ),
            _route(
                "alternate-split",
                "Alternating holdout with the threshold classifier.",
                {
                    "split": _candidate_id(
                        "example.ml.classification.split.alternating"
                    ),
                    "train": _candidate_id("example.ml.classification.train.threshold"),
                    "evaluate": _candidate_id("example.ml.classification.evaluate"),
                },
            ),
        ),
        ExperimentCase(
            "case.tabular-classification",
            {
                "dataset": {
                    "rows": [
                        {"x": value, "label": int(value > 5)}
                        for value in range(1, 11)
                    ],
                    "predict": [2, 7, 12],
                }
            },
            CallableVerifier(
                "verifier.example.classification", _classification_verifier
            ),
        ),
        ExecutionPolicy(),
        (Objective("quality", "maximize"), Objective("latency_ms", "minimize")),
    ),
)


def get_example(example_id: str) -> ExecutableExample:
    try:
        return next(example for example in EXAMPLE_TASKS if example.id == example_id)
    except StopIteration as exc:
        known = ", ".join(example.id for example in EXAMPLE_TASKS)
        raise ValueError(f"unknown example {example_id!r}; known examples: {known}") from exc


def run_example(
    example_id: str,
    *,
    route: str = "all",
    artifact_root: str | Path | None = None,
    runtime: str = "in-process",
    receipt_journal: JsonlReceiptJournal | None = None,
) -> dict[str, Any]:
    """Compile and execute one route or a receipt-backed comparison of all routes."""
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
    space, plans_by_name = example.compile()
    store_factory = (
        (lambda: FileArtifactStore(Path(artifact_root)))
        if artifact_root is not None
        else MemoryArtifactStore
    )
    if route != "all":
        if route not in plans_by_name:
            known = ", ".join(plans_by_name)
            raise ValueError(f"unknown route {route!r}; known routes: {known}")
        result = executor.execute(
            plans_by_name[route],
            example.program,
            example.registry,
            space,
            example.case.inputs,
            task_case_id=example.case.id,
            verifier=example.case.verifier,
            policy=policy,
            artifact_store=store_factory(),
            seed=0,
            belief_revision="example.cold-start",
        )
        if receipt_journal is not None:
            receipt_journal.append(result.receipt)
        return {
            "example": example.id,
            "route": route,
            "runtime": runtime,
            "admitted_candidates": {
                slot_id: list(candidates) for slot_id, candidates in space.choices
            },
            "plan": plans_by_name[route].to_dict(),
            "execution": result.to_dict(),
        }

    plans = {plan.digest: plan for plan in plans_by_name.values()}
    design = ExperimentDesign(
        id=f"experiment.{example.id}",
        task_case_ids=(example.case.id,),
        plan_digests=tuple(plans),
        seeds=(0,),
        repetitions=1,
        objectives=example.objectives,
        control_plan_digest=next(iter(plans)),
    )
    experiment = ExperimentRunner(executor).run(
        design,
        plans=plans,
        cases={example.case.id: example.case},
        program=example.program,
        registry=example.registry,
        space=space,
        policy=policy,
        artifact_store_factory=store_factory,
        receipt_sink=receipt_journal,
        belief_revision="example.cold-start",
    )
    return {
        "example": example.id,
        "runtime": runtime,
        "routes": {name: plan.digest for name, plan in plans_by_name.items()},
        "admitted_candidates": {
            slot_id: list(candidates) for slot_id, candidates in space.choices
        },
        "experiment": experiment.to_dict(),
    }


__all__ = [
    "BROWSE_PROGRAM",
    "CANDIDATES",
    "CLASSIFICATION_PROGRAM",
    "DATA_PROGRAM",
    "DOCUMENT_PROGRAM",
    "EXAMPLE_REGISTRY",
    "EXAMPLE_TASKS",
    "ExecutableExample",
    "ExampleRoute",
    "IMAGE_PROGRAM",
    "ML_PROGRAM",
    "NODES",
    "get_example",
    "run_example",
]
