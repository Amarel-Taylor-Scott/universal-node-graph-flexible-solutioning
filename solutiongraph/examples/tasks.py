"""Executable examples that use one universal registry and executor."""

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
from solutiongraph.examples import arena_nodes as arena_implementations
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

CUSTOMER_BUNDLE = ValueType("example.customer-bundle")
CUSTOMER_GROUPS = ValueType("example.customer-groups")
GOLDEN_CUSTOMERS = ValueType("example.golden-customers")

ADDRESS_BUNDLE = ValueType("example.address-bundle")
VERIFIED_ADDRESSES = ValueType("example.verified-addresses")

PRODUCT_SOURCES = ValueType("example.product-sources")
PRODUCT_ROWS = ValueType("example.product-rows")
VERIFIED_PRODUCTS = ValueType("example.verified-products")

TIME_SERIES = ValueType("example.time-series")
FORECAST_RESULT = ValueType("example.forecast-result")

ORGANIZATION_RECORDS = ValueType("example.organization-records")
ORGANIZATION_BLOCKS = ValueType("example.organization-blocks")
ENTITY_COMPONENTS = ValueType("example.entity-components")

REPOSITORY_SNAPSHOT = ValueType("example.repository-snapshot")
REPAIR_PROPOSAL = ValueType("example.repair-proposal")
REPAIR_REPORT = ValueType("example.repair-report")

RAW_FEEDS = ValueType("example.raw-feeds")
FEED_ROWS = ValueType("example.feed-rows")
ANALYTICAL_DATASET = ValueType("example.analytical-dataset")


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
        entrypoint=f"{function.__module__}:{function.__name__}",
        description=description,
        parameters=parameters,
        capabilities=(capability,),
        effects=effects,
        permissions=permissions,
        determinism=determinism,
        idempotency=Idempotency.IDEMPOTENT,
        failure_modes=failure_modes,
        source=function.__module__.replace(".", "/") + ".py",
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


def _arena_node(
    node_id: str,
    function: Callable[..., Any],
    capability: str,
    input_name: str,
    input_type: ValueType,
    output_name: str,
    output_type: ValueType,
    description: str,
) -> NodeSpec:
    return _node(
        node_id,
        function,
        capability,
        (Port(input_name, input_type),),
        (Port(output_name, output_type),),
        description,
    )


NODES += tuple(
    _arena_node(*definition)
    for definition in (
        (
            "example.customer.normalize.conservative",
            arena_implementations.normalize_customers_conservative,
            "customer.normalize",
            "bundle",
            CUSTOMER_BUNDLE,
            "bundle",
            CUSTOMER_BUNDLE,
            "Normalize customer keys and contact fields conservatively.",
        ),
        (
            "example.customer.normalize.canonical",
            arena_implementations.normalize_customers_canonical,
            "customer.normalize",
            "bundle",
            CUSTOMER_BUNDLE,
            "bundle",
            CUSTOMER_BUNDLE,
            "Normalize names, contacts, and common address tokens canonically.",
        ),
        (
            "example.customer.validate.syntax",
            arena_implementations.validate_customer_contacts_syntax,
            "customer.validate-contacts",
            "bundle",
            CUSTOMER_BUNDLE,
            "bundle",
            CUSTOMER_BUNDLE,
            "Check contact syntax without claiming external authority.",
        ),
        (
            "example.customer.validate.reference",
            arena_implementations.validate_customer_contacts_reference,
            "customer.validate-contacts",
            "bundle",
            CUSTOMER_BUNDLE,
            "bundle",
            CUSTOMER_BUNDLE,
            "Check contacts against an explicitly supplied offline reference fixture.",
        ),
        (
            "example.customer.resolve.email",
            arena_implementations.resolve_customers_by_email,
            "customer.resolve",
            "bundle",
            CUSTOMER_BUNDLE,
            "groups",
            CUSTOMER_GROUPS,
            "Resolve identities by exact normalized email.",
        ),
        (
            "example.customer.resolve.multikey",
            arena_implementations.resolve_customers_multikey,
            "customer.resolve",
            "bundle",
            CUSTOMER_BUNDLE,
            "groups",
            CUSTOMER_GROUPS,
            "Resolve identities with email, phone, name, and address evidence.",
        ),
        (
            "example.customer.emit.first",
            arena_implementations.emit_customer_first,
            "customer.emit-golden",
            "groups",
            CUSTOMER_GROUPS,
            "records",
            GOLDEN_CUSTOMERS,
            "Emit the first record in each entity group with provenance.",
        ),
        (
            "example.customer.emit.complete",
            arena_implementations.emit_customer_complete,
            "customer.emit-golden",
            "groups",
            CUSTOMER_GROUPS,
            "records",
            GOLDEN_CUSTOMERS,
            "Merge the most complete verified fields with source provenance.",
        ),
        (
            "example.address.parse.commas",
            arena_implementations.parse_addresses_commas,
            "address.parse",
            "bundle",
            ADDRESS_BUNDLE,
            "bundle",
            ADDRESS_BUNDLE,
            "Parse comma-delimited addresses into typed components.",
        ),
        (
            "example.address.parse.structured",
            arena_implementations.parse_addresses_structured,
            "address.parse",
            "bundle",
            ADDRESS_BUNDLE,
            "bundle",
            ADDRESS_BUNDLE,
            "Parse United States city, region, and postal-code structure.",
        ),
        (
            "example.address.normalize.basic",
            arena_implementations.normalize_addresses_basic,
            "address.normalize",
            "bundle",
            ADDRESS_BUNDLE,
            "bundle",
            ADDRESS_BUNDLE,
            "Normalize casing and whitespace only.",
        ),
        (
            "example.address.normalize.postal",
            arena_implementations.normalize_addresses_postal,
            "address.normalize",
            "bundle",
            ADDRESS_BUNDLE,
            "bundle",
            ADDRESS_BUNDLE,
            "Apply a small Publication-28-inspired abbreviation fixture.",
        ),
        (
            "example.address.verify.exact",
            arena_implementations.verify_addresses_exact,
            "address.verify-reference",
            "bundle",
            ADDRESS_BUNDLE,
            "bundle",
            ADDRESS_BUNDLE,
            "Require exact equality with a supplied offline reference directory.",
        ),
        (
            "example.address.verify.alias",
            arena_implementations.verify_addresses_alias_aware,
            "address.verify-reference",
            "bundle",
            ADDRESS_BUNDLE,
            "bundle",
            ADDRESS_BUNDLE,
            "Compare canonical alphanumeric forms to the offline reference directory.",
        ),
        (
            "example.address.emit",
            arena_implementations.emit_verified_addresses,
            "address.emit",
            "bundle",
            ADDRESS_BUNDLE,
            "records",
            VERIFIED_ADDRESSES,
            "Emit deterministic standardized address records and match codes.",
        ),
        (
            "example.product.acquire.preserve",
            arena_implementations.acquire_product_sources_preserve,
            "product.acquire",
            "sources",
            PRODUCT_SOURCES,
            "sources",
            PRODUCT_SOURCES,
            "Preserve authorized captured HTML sources.",
        ),
        (
            "example.product.acquire.sorted",
            arena_implementations.acquire_product_sources_sorted,
            "product.acquire",
            "sources",
            PRODUCT_SOURCES,
            "sources",
            PRODUCT_SOURCES,
            "Canonicalize captured-source order by URL.",
        ),
        (
            "example.product.extract.regex",
            arena_implementations.extract_products_regex,
            "product.extract",
            "sources",
            PRODUCT_SOURCES,
            "products",
            PRODUCT_ROWS,
            "Extract the fixture product microformat with a bounded expression.",
        ),
        (
            "example.product.extract.parser",
            arena_implementations.extract_products_parser,
            "product.extract",
            "sources",
            PRODUCT_SOURCES,
            "products",
            PRODUCT_ROWS,
            "Extract the fixture product microformat with HTMLParser.",
        ),
        (
            "example.product.normalize.float",
            arena_implementations.normalize_product_prices_float,
            "product.normalize",
            "products",
            PRODUCT_ROWS,
            "products",
            PRODUCT_ROWS,
            "Normalize display prices through floating-point conversion.",
        ),
        (
            "example.product.normalize.decimal",
            arena_implementations.normalize_product_prices_decimal,
            "product.normalize",
            "products",
            PRODUCT_ROWS,
            "products",
            PRODUCT_ROWS,
            "Normalize monetary values into integer cents with Decimal.",
        ),
        (
            "example.product.verify.single",
            arena_implementations.verify_products_single_source,
            "product.verify",
            "products",
            PRODUCT_ROWS,
            "products",
            VERIFIED_PRODUCTS,
            "Retain single-source evidence without calling it independently verified.",
        ),
        (
            "example.product.verify.cross-source",
            arena_implementations.verify_products_cross_source,
            "product.verify",
            "products",
            PRODUCT_ROWS,
            "products",
            VERIFIED_PRODUCTS,
            "Require matching SKU and price evidence from independent captured sources.",
        ),
        (
            "example.forecast.prepare.observed",
            arena_implementations.prepare_series_observed,
            "forecast.prepare",
            "series",
            TIME_SERIES,
            "series",
            TIME_SERIES,
            "Use complete observed training values as supplied.",
        ),
        (
            "example.forecast.prepare.interpolate",
            arena_implementations.prepare_series_interpolate,
            "forecast.prepare",
            "series",
            TIME_SERIES,
            "series",
            TIME_SERIES,
            "Interpolate missing interior observations deterministically.",
        ),
        (
            "example.forecast.fit.mean",
            arena_implementations.fit_forecast_mean,
            "forecast.fit",
            "series",
            TIME_SERIES,
            "series",
            TIME_SERIES,
            "Fit an explicit historical-mean control model.",
        ),
        (
            "example.forecast.fit.trend",
            arena_implementations.fit_forecast_trend,
            "forecast.fit",
            "series",
            TIME_SERIES,
            "series",
            TIME_SERIES,
            "Fit a deterministic linear trend model.",
        ),
        (
            "example.forecast.generate",
            arena_implementations.generate_forecast,
            "forecast.generate",
            "series",
            TIME_SERIES,
            "series",
            TIME_SERIES,
            "Generate horizon-aligned point predictions from the frozen model.",
        ),
        (
            "example.forecast.interval.fixed",
            arena_implementations.calibrate_intervals_fixed,
            "forecast.calibrate-intervals",
            "series",
            TIME_SERIES,
            "result",
            FORECAST_RESULT,
            "Attach a narrow fixed-width control interval.",
        ),
        (
            "example.forecast.interval.residual",
            arena_implementations.calibrate_intervals_residual,
            "forecast.calibrate-intervals",
            "series",
            TIME_SERIES,
            "result",
            FORECAST_RESULT,
            "Calibrate interval width from in-sample absolute residuals.",
        ),
        (
            "example.entity.normalize.basic",
            arena_implementations.normalize_organizations_basic,
            "entity.normalize",
            "records",
            ORGANIZATION_RECORDS,
            "records",
            ORGANIZATION_RECORDS,
            "Normalize organization names and domains conservatively.",
        ),
        (
            "example.entity.normalize.legal",
            arena_implementations.normalize_organizations_legal,
            "entity.normalize",
            "records",
            ORGANIZATION_RECORDS,
            "records",
            ORGANIZATION_RECORDS,
            "Normalize common legal suffix variants.",
        ),
        (
            "example.entity.block.domain",
            arena_implementations.block_organizations_domain,
            "entity.block",
            "records",
            ORGANIZATION_RECORDS,
            "blocked",
            ORGANIZATION_BLOCKS,
            "Generate candidate pairs sharing a normalized web domain.",
        ),
        (
            "example.entity.block.tokens",
            arena_implementations.block_organizations_tokens,
            "entity.block",
            "records",
            ORGANIZATION_RECORDS,
            "blocked",
            ORGANIZATION_BLOCKS,
            "Generate candidate pairs sharing name tokens or domain evidence.",
        ),
        (
            "example.entity.link.exact",
            arena_implementations.link_organizations_exact,
            "entity.link",
            "blocked",
            ORGANIZATION_BLOCKS,
            "linked",
            ORGANIZATION_BLOCKS,
            "Link candidate pairs only when normalized names are identical.",
        ),
        (
            "example.entity.link.evidence",
            arena_implementations.link_organizations_evidence,
            "entity.link",
            "blocked",
            ORGANIZATION_BLOCKS,
            "linked",
            ORGANIZATION_BLOCKS,
            "Link pairs supported by at least two independent fields.",
        ),
        (
            "example.entity.components",
            arena_implementations.build_entity_components,
            "entity.components",
            "linked",
            ORGANIZATION_BLOCKS,
            "entities",
            ENTITY_COMPONENTS,
            "Build deterministic connected components with source record IDs.",
        ),
        (
            "example.repair.inspect.ast",
            arena_implementations.inspect_code_ast,
            "repair.inspect",
            "repository",
            REPOSITORY_SNAPSHOT,
            "proposal",
            REPAIR_PROPOSAL,
            "Inspect the bounded fixture source with Python AST.",
        ),
        (
            "example.repair.inspect.tests",
            arena_implementations.inspect_code_tests,
            "repair.inspect",
            "repository",
            REPOSITORY_SNAPSHOT,
            "proposal",
            REPAIR_PROPOSAL,
            "Inspect the fixed failing test contract.",
        ),
        (
            "example.repair.propose.operator",
            arena_implementations.propose_operator_repair,
            "repair.propose",
            "proposal",
            REPAIR_PROPOSAL,
            "proposal",
            REPAIR_PROPOSAL,
            "Propose a minimal operator replacement.",
        ),
        (
            "example.repair.propose.contract",
            arena_implementations.propose_contract_repair,
            "repair.propose",
            "proposal",
            REPAIR_PROPOSAL,
            "proposal",
            REPAIR_PROPOSAL,
            "Derive a bounded repair hypothesis from fixed tests.",
        ),
        (
            "example.repair.apply.exact",
            arena_implementations.apply_repair_exact,
            "repair.apply",
            "proposal",
            REPAIR_PROPOSAL,
            "proposal",
            REPAIR_PROPOSAL,
            "Apply one exact content replacement.",
        ),
        (
            "example.repair.apply.line",
            arena_implementations.apply_repair_line,
            "repair.apply",
            "proposal",
            REPAIR_PROPOSAL,
            "proposal",
            REPAIR_PROPOSAL,
            "Apply one line-scoped return-expression replacement.",
        ),
        (
            "example.repair.test.ast",
            arena_implementations.test_repair_ast,
            "repair.test",
            "proposal",
            REPAIR_PROPOSAL,
            "report",
            REPAIR_REPORT,
            "Run fixed cases through a restricted AST interpreter.",
        ),
        (
            "example.repair.test.symbolic",
            arena_implementations.test_repair_symbolic,
            "repair.test",
            "proposal",
            REPAIR_PROPOSAL,
            "report",
            REPAIR_REPORT,
            "Require both symbolic operator structure and fixed-case success.",
        ),
        (
            "example.feed.decode.csv-module",
            arena_implementations.decode_feeds_csv_module,
            "feed.decode",
            "feeds",
            RAW_FEEDS,
            "rows",
            FEED_ROWS,
            "Decode CSV with the standard library and combine captured JSON rows.",
        ),
        (
            "example.feed.decode.lines",
            arena_implementations.decode_feeds_line_parser,
            "feed.decode",
            "feeds",
            RAW_FEEDS,
            "rows",
            FEED_ROWS,
            "Decode the bounded CSV fixture line by line and combine JSON rows.",
        ),
        (
            "example.feed.normalize.strict",
            arena_implementations.normalize_feed_rows_strict,
            "feed.normalize",
            "rows",
            FEED_ROWS,
            "rows",
            FEED_ROWS,
            "Require already numeric amount fields.",
        ),
        (
            "example.feed.normalize.coerce",
            arena_implementations.normalize_feed_rows_coerce,
            "feed.normalize",
            "rows",
            FEED_ROWS,
            "rows",
            FEED_ROWS,
            "Normalize names and explicitly parse currency-formatted amounts.",
        ),
        (
            "example.feed.reconcile.priority",
            arena_implementations.reconcile_feed_rows_priority,
            "feed.reconcile",
            "rows",
            FEED_ROWS,
            "rows",
            FEED_ROWS,
            "Choose one whole record according to fixed source priority.",
        ),
        (
            "example.feed.reconcile.complete",
            arena_implementations.reconcile_feed_rows_complete,
            "feed.reconcile",
            "rows",
            FEED_ROWS,
            "rows",
            FEED_ROWS,
            "Merge complementary nonempty fields and retain source lineage.",
        ),
        (
            "example.feed.validate.strict",
            arena_implementations.validate_feed_rows_strict,
            "feed.validate",
            "rows",
            FEED_ROWS,
            "dataset",
            ANALYTICAL_DATASET,
            "Separate rows that do not meet the analytical schema.",
        ),
        (
            "example.feed.validate.lineage",
            arena_implementations.validate_feed_rows_quarantine,
            "feed.validate",
            "rows",
            FEED_ROWS,
            "dataset",
            ANALYTICAL_DATASET,
            "Validate schema and report whether every row retains source lineage.",
        ),
    )
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


def _customer_verifier(context: VerificationContext) -> VerificationResult:
    records = context.outputs["records"]
    alice = next(
        (record for record in records if record.get("email") == "alice@example.com"),
        {},
    )
    required = ("name", "email", "phone", "address")
    complete = sum(bool(alice.get(field)) for field in required) / len(required)
    accepted = (
        len(records) == 2
        and complete == 1.0
        and set(alice.get("verified_fields", ())) == {"email", "phone"}
        and len(alice.get("provenance", ())) == 3
    )
    return VerificationResult(
        accepted,
        "golden-table-matches-oracle" if accepted else "golden-table-mismatch",
        {"quality": complete if len(records) == 2 else complete / 2},
        {"record_count": len(records), "alice": alice},
    )


def _address_verifier(context: VerificationContext) -> VerificationResult:
    records = context.outputs["records"]
    verified = sum(record.get("verified") is True for record in records)
    accepted = (
        len(records) == 2
        and verified == 2
        and all(record.get("authority") == "offline-reference-fixture" for record in records)
        and {record.get("postal_code") for record in records} == {"62704", "63101"}
    )
    return VerificationResult(
        accepted,
        "reference-addresses-match" if accepted else "reference-address-mismatch",
        {"quality": verified / len(records) if records else 0.0},
        {
            "authority_scope": "offline-reference-fixture-not-usps",
            "verified": verified,
        },
    )


def _product_verifier(context: VerificationContext) -> VerificationResult:
    products = context.outputs["products"]
    accepted = (
        len(products) == 2
        and all(product.get("verified") is True for product in products)
        and {product.get("sku") for product in products} == {"SKU-1", "SKU-2"}
        and all(len(product.get("evidence_sources", ())) == 2 for product in products)
    )
    verified = sum(product.get("verified") is True for product in products)
    return VerificationResult(
        accepted,
        "products-independently-corroborated" if accepted else "product-evidence-insufficient",
        {"quality": verified / 2},
        {"product_count": len(products), "verified_count": verified},
    )


def _forecast_verifier(context: VerificationContext) -> VerificationResult:
    result = context.outputs["result"]
    actual = [float(value) for value in result["holdout"]]
    predictions = [float(value) for value in result["predictions"]]
    mae = sum(abs(left - right) for left, right in zip(actual, predictions, strict=True)) / len(actual)
    covered = sum(
        low <= value <= high
        for value, (low, high) in zip(actual, result["intervals"], strict=True)
    )
    coverage = covered / len(actual)
    accepted = mae <= 0.75 and coverage == 1.0
    return VerificationResult(
        accepted,
        "forecast-and-interval-thresholds-met" if accepted else "forecast-threshold-missed",
        {"quality": 1.0 / (1.0 + mae), "mae": mae, "coverage": coverage},
        {"mae_limit": 0.75, "required_coverage": 1.0},
    )


def _entity_verifier(context: VerificationContext) -> VerificationResult:
    entities = context.outputs["entities"]
    components = sorted(sorted(entity["record_ids"]) for entity in entities)
    expected = [["org-1", "org-2"], ["org-3"]]
    accepted = components == expected
    correct_pairs = int(["org-1", "org-2"] in components)
    return VerificationResult(
        accepted,
        "entity-components-match-oracle" if accepted else "entity-component-mismatch",
        {"quality": float(correct_pairs)},
        {"expected": expected, "actual": components},
    )


def _repair_verifier(context: VerificationContext) -> VerificationResult:
    report = context.outputs["report"]
    accepted = (
        report.get("passed") is True
        and report.get("passed_cases") == report.get("total_cases") == 3
        and report.get("changed_files") == ["math_utils.py"]
        and "return a + b" in report.get("source", "")
    )
    return VerificationResult(
        accepted,
        "repair-tests-and-scope-pass" if accepted else "repair-verification-failed",
        {"quality": report.get("passed_cases", 0) / max(1, report.get("total_cases", 0))},
        {"changed_files": report.get("changed_files", [])},
    )


def _feed_verifier(context: VerificationContext) -> VerificationResult:
    dataset = context.outputs["dataset"]
    rows = dataset["rows"]
    total = sum(float(row["amount"]) for row in rows)
    accepted = (
        len(rows) == 3
        and not dataset["quarantine"]
        and math.isclose(total, 60.5)
        and all(bool(row.get("sources") or row.get("source")) for row in rows)
    )
    return VerificationResult(
        accepted,
        "analytical-dataset-valid" if accepted else "analytical-dataset-invalid",
        {"quality": len(rows) / 3 if not dataset["quarantine"] else len(rows) / 6},
        {"row_count": len(rows), "quarantine_count": len(dataset["quarantine"]), "total": total},
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

CUSTOMER_PROGRAM = ProgramGraph(
    id="example.golden-customer-table",
    version="1.0.0",
    task="Build a verified golden customer table from fragmented source records.",
    success_contract="An independent oracle accepts entity count, field completeness, contact verification, and provenance.",
    slots=(
        _slot("normalize", "Normalize customer fields without erasing provenance.", (Port("bundle", CUSTOMER_BUNDLE),), (Port("bundle", CUSTOMER_BUNDLE),), "customer.normalize", "Every record has canonical keys and source identity."),
        _slot("validate", "Validate contact claims at an explicit trust level.", (Port("bundle", CUSTOMER_BUNDLE),), (Port("bundle", CUSTOMER_BUNDLE),), "customer.validate-contacts", "Every verification claim names its method."),
        _slot("resolve", "Resolve records into candidate customer identities.", (Port("bundle", CUSTOMER_BUNDLE),), (Port("groups", CUSTOMER_GROUPS),), "customer.resolve", "Every source record belongs to exactly one group."),
        _slot("emit", "Merge each group into one golden record.", (Port("groups", CUSTOMER_GROUPS),), (Port("records", GOLDEN_CUSTOMERS),), "customer.emit-golden", "Golden records retain field values and source provenance."),
    ),
    edges=(
        Edge("normalize", "bundle", "validate", "bundle"),
        Edge("validate", "bundle", "resolve", "bundle"),
        Edge("resolve", "groups", "emit", "groups"),
    ),
    inputs=(GraphInput("bundle", CUSTOMER_BUNDLE, "normalize", "bundle"),),
    outputs=(GraphOutput("records", GOLDEN_CUSTOMERS, "emit", "records"),),
)

ADDRESS_PROGRAM = ProgramGraph(
    id="example.address-reference-verification",
    version="1.0.0",
    task="Standardize addresses and compare them with an explicitly supplied reference directory.",
    success_contract="The independent oracle accepts canonical components and explicit offline-reference match evidence.",
    slots=(
        _slot("parse", "Parse raw address strings into components.", (Port("bundle", ADDRESS_BUNDLE),), (Port("bundle", ADDRESS_BUNDLE),), "address.parse", "Street, city, region, and postal code are explicit."),
        _slot("normalize", "Normalize components into a postal comparison form.", (Port("bundle", ADDRESS_BUNDLE),), (Port("bundle", ADDRESS_BUNDLE),), "address.normalize", "Normalization is deterministic and preserves source index."),
        _slot("verify", "Compare addresses with the named offline reference fixture.", (Port("bundle", ADDRESS_BUNDLE),), (Port("bundle", ADDRESS_BUNDLE),), "address.verify-reference", "Each row has authority, match code, and boolean verdict."),
        _slot("emit", "Emit deterministic standardized records.", (Port("bundle", ADDRESS_BUNDLE),), (Port("records", VERIFIED_ADDRESSES),), "address.emit", "Every source address produces one result row."),
    ),
    edges=(
        Edge("parse", "bundle", "normalize", "bundle"),
        Edge("normalize", "bundle", "verify", "bundle"),
        Edge("verify", "bundle", "emit", "bundle"),
    ),
    inputs=(GraphInput("bundle", ADDRESS_BUNDLE, "parse", "bundle"),),
    outputs=(GraphOutput("records", VERIFIED_ADDRESSES, "emit", "records"),),
)

PRODUCT_PROGRAM = ProgramGraph(
    id="example.verified-product-dataset",
    version="1.0.0",
    task="Extract a product dataset from authorized captured pages and corroborate it across sources.",
    success_contract="An independent oracle accepts exact SKUs, integer prices, and two-source evidence.",
    slots=(
        _slot("acquire", "Prepare authorized captured HTML sources.", (Port("sources", PRODUCT_SOURCES),), (Port("sources", PRODUCT_SOURCES),), "product.acquire", "Captured bytes and source URLs remain paired."),
        _slot("extract", "Extract product records from each capture.", (Port("sources", PRODUCT_SOURCES),), (Port("products", PRODUCT_ROWS),), "product.extract", "Each row includes SKU, name, price text, and source URL."),
        _slot("normalize", "Normalize product fields and monetary representation.", (Port("products", PRODUCT_ROWS),), (Port("products", PRODUCT_ROWS),), "product.normalize", "Every amount is an integer number of cents."),
        _slot("verify", "Corroborate product claims across independent captures.", (Port("products", PRODUCT_ROWS),), (Port("products", VERIFIED_PRODUCTS),), "product.verify", "Verification never exceeds available source evidence."),
    ),
    edges=(
        Edge("acquire", "sources", "extract", "sources"),
        Edge("extract", "products", "normalize", "products"),
        Edge("normalize", "products", "verify", "products"),
    ),
    inputs=(GraphInput("sources", PRODUCT_SOURCES, "acquire", "sources"),),
    outputs=(GraphOutput("products", VERIFIED_PRODUCTS, "verify", "products"),),
)

FORECAST_PROGRAM = ProgramGraph(
    id="example.calibrated-time-series-forecast",
    version="1.0.0",
    task="Fit a point forecast and attach empirically testable prediction intervals.",
    success_contract="An independent holdout oracle accepts point error and interval coverage thresholds.",
    slots=(
        _slot("prepare", "Regularize or certify the observed series.", (Port("series", TIME_SERIES),), (Port("series", TIME_SERIES),), "forecast.prepare", "Training values are finite and ordered."),
        _slot("fit", "Fit one declared forecasting model.", (Port("series", TIME_SERIES),), (Port("series", TIME_SERIES),), "forecast.fit", "The model is serializable and identifies its family."),
        _slot("forecast", "Generate horizon-aligned point predictions.", (Port("series", TIME_SERIES),), (Port("series", TIME_SERIES),), "forecast.generate", "Prediction count equals the declared horizon."),
        _slot("intervals", "Calibrate an interval around every point forecast.", (Port("series", TIME_SERIES),), (Port("result", FORECAST_RESULT),), "forecast.calibrate-intervals", "Every prediction has finite lower and upper bounds."),
    ),
    edges=(
        Edge("prepare", "series", "fit", "series"),
        Edge("fit", "series", "forecast", "series"),
        Edge("forecast", "series", "intervals", "series"),
    ),
    inputs=(GraphInput("series", TIME_SERIES, "prepare", "series"),),
    outputs=(GraphOutput("result", FORECAST_RESULT, "intervals", "result"),),
)

ENTITY_PROGRAM = ProgramGraph(
    id="example.organization-entity-linking",
    version="1.0.0",
    task="Resolve duplicate organization records into an auditable entity graph.",
    success_contract="An independent entity oracle accepts the exact connected components.",
    slots=(
        _slot("normalize", "Normalize organization identity fields.", (Port("records", ORGANIZATION_RECORDS),), (Port("records", ORGANIZATION_RECORDS),), "entity.normalize", "Source record IDs and raw names remain present."),
        _slot("block", "Generate bounded candidate record pairs.", (Port("records", ORGANIZATION_RECORDS),), (Port("blocked", ORGANIZATION_BLOCKS),), "entity.block", "Every pair references two known records."),
        _slot("link", "Score and accept supported identity links.", (Port("blocked", ORGANIZATION_BLOCKS),), (Port("linked", ORGANIZATION_BLOCKS),), "entity.link", "Every accepted link was in the candidate pair set."),
        _slot("components", "Build deterministic entity components.", (Port("linked", ORGANIZATION_BLOCKS),), (Port("entities", ENTITY_COMPONENTS),), "entity.components", "Every record belongs to exactly one component."),
    ),
    edges=(
        Edge("normalize", "records", "block", "records"),
        Edge("block", "blocked", "link", "blocked"),
        Edge("link", "linked", "components", "linked"),
    ),
    inputs=(GraphInput("records", ORGANIZATION_RECORDS, "normalize", "records"),),
    outputs=(GraphOutput("entities", ENTITY_COMPONENTS, "components", "entities"),),
)

REPAIR_PROGRAM = ProgramGraph(
    id="example.tested-code-repair",
    version="1.0.0",
    task="Inspect, patch, and independently test one bounded broken repository fixture.",
    success_contract="The independent oracle accepts all fixed cases and exact changed-file scope.",
    slots=(
        _slot("inspect", "Inspect source or failing test evidence.", (Port("repository", REPOSITORY_SNAPSHOT),), (Port("proposal", REPAIR_PROPOSAL),), "repair.inspect", "Findings retain the immutable source and tests."),
        _slot("propose", "Form one bounded repair hypothesis.", (Port("proposal", REPAIR_PROPOSAL),), (Port("proposal", REPAIR_PROPOSAL),), "repair.propose", "The patch names old content, new content, and a hypothesis."),
        _slot("apply", "Apply the patch to an isolated fixture snapshot.", (Port("proposal", REPAIR_PROPOSAL),), (Port("proposal", REPAIR_PROPOSAL),), "repair.apply", "Changed-file scope is explicit."),
        _slot("test", "Test the patched behavior without executing arbitrary source.", (Port("proposal", REPAIR_PROPOSAL),), (Port("report", REPAIR_REPORT),), "repair.test", "All fixed cases and changed files are reported."),
    ),
    edges=(
        Edge("inspect", "proposal", "propose", "proposal"),
        Edge("propose", "proposal", "apply", "proposal"),
        Edge("apply", "proposal", "test", "proposal"),
    ),
    inputs=(GraphInput("repository", REPOSITORY_SNAPSHOT, "inspect", "repository"),),
    outputs=(GraphOutput("report", REPAIR_REPORT, "test", "report"),),
)

FEED_PROGRAM = ProgramGraph(
    id="example.multi-feed-analytical-dataset",
    version="1.0.0",
    task="Decode heterogeneous captured feeds into one validated analytical dataset.",
    success_contract="An independent oracle accepts row count, reconciled total, quarantine state, and lineage.",
    slots=(
        _slot("decode", "Decode captured CSV and JSON representations.", (Port("feeds", RAW_FEEDS),), (Port("rows", FEED_ROWS),), "feed.decode", "Every decoded row names its source."),
        _slot("normalize", "Normalize typed analytical fields.", (Port("rows", FEED_ROWS),), (Port("rows", FEED_ROWS),), "feed.normalize", "Conversion failures are explicit, never silently zero-filled."),
        _slot("reconcile", "Reconcile duplicate source records.", (Port("rows", FEED_ROWS),), (Port("rows", FEED_ROWS),), "feed.reconcile", "Every emitted identity has deterministic field precedence and lineage."),
        _slot("validate", "Validate and quarantine rows against the analytical contract.", (Port("rows", FEED_ROWS),), (Port("dataset", ANALYTICAL_DATASET),), "feed.validate", "Valid and quarantined rows are disjoint and complete."),
    ),
    edges=(
        Edge("decode", "rows", "normalize", "rows"),
        Edge("normalize", "rows", "reconcile", "rows"),
        Edge("reconcile", "rows", "validate", "rows"),
    ),
    inputs=(GraphInput("feeds", RAW_FEEDS, "decode", "feeds"),),
    outputs=(GraphOutput("dataset", ANALYTICAL_DATASET, "validate", "dataset"),),
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

EXAMPLE_TASKS += (
    ExecutableExample(
        "golden-customer-table",
        "Verified golden customer table",
        "Compare contact validation, identity resolution, and field-level merge strategies.",
        CUSTOMER_PROGRAM,
        (
            _route(
                "control",
                "Syntax checks, exact email grouping, and first-record emission.",
                {
                    "normalize": _candidate_id("example.customer.normalize.conservative"),
                    "validate": _candidate_id("example.customer.validate.syntax"),
                    "resolve": _candidate_id("example.customer.resolve.email"),
                    "emit": _candidate_id("example.customer.emit.first"),
                },
                expected_accepted=False,
            ),
            _route(
                "reference-multikey",
                "Reference-backed contacts, multi-key resolution, and completeness merge.",
                {
                    "normalize": _candidate_id("example.customer.normalize.canonical"),
                    "validate": _candidate_id("example.customer.validate.reference"),
                    "resolve": _candidate_id("example.customer.resolve.multikey"),
                    "emit": _candidate_id("example.customer.emit.complete"),
                },
            ),
        ),
        ExperimentCase(
            "case.golden-customer-table",
            {
                "bundle": {
                    "records": [
                        {"source_record": "crm-1", "Name": "alice smith", "Email": "ALICE@EXAMPLE.COM", "Phone": "", "Address": "10 Main Street"},
                        {"source_record": "support-7", "name": "Alice Smith", "email": "", "phone": "(555) 0100", "address": "10 MAIN ST"},
                        {"source_record": "billing-3", "name": "Alice Smith", "email": "alice@example.com", "phone": "555-0100", "address": ""},
                        {"source_record": "crm-2", "name": "Bob Jones", "email": "bob@example.com", "phone": "555-0200", "address": "20 Oak Ave"},
                    ],
                    "contact_directory": {
                        "emails": ["alice@example.com", "bob@example.com"],
                        "phones": ["5550100", "5550200"],
                    },
                }
            },
            CallableVerifier("verifier.example.customer", _customer_verifier),
        ),
        ExecutionPolicy(),
        (Objective("quality", "maximize", hard_minimum=1.0), Objective("latency_ms", "minimize", weight=0.1)),
    ),
    ExecutableExample(
        "address-reference-verification",
        "Address standardization and reference verification",
        "Demonstrate the production USPS connector seam using an honestly labeled offline authority fixture.",
        ADDRESS_PROGRAM,
        (
            _route(
                "control",
                "Basic normalization with exact reference comparison.",
                {
                    "parse": _candidate_id("example.address.parse.commas"),
                    "normalize": _candidate_id("example.address.normalize.basic"),
                    "verify": _candidate_id("example.address.verify.exact"),
                    "emit": _candidate_id("example.address.emit"),
                },
                expected_accepted=False,
            ),
            _route(
                "postal-alias",
                "Structured parsing, postal abbreviations, and alias-aware comparison.",
                {
                    "parse": _candidate_id("example.address.parse.structured"),
                    "normalize": _candidate_id("example.address.normalize.postal"),
                    "verify": _candidate_id("example.address.verify.alias"),
                    "emit": _candidate_id("example.address.emit"),
                },
            ),
        ),
        ExperimentCase(
            "case.address-reference-verification",
            {
                "bundle": {
                    "addresses": [
                        "123 Main Street Apt 4, Springfield, IL 62704",
                        "500 Market Avenue, St Louis, MO 63101",
                    ],
                    "reference_directory": [
                        {"street": "123 MAIN ST APT 4", "city": "SPRINGFIELD", "region": "IL", "postal_code": "62704"},
                        {"street": "500 MARKET AVE", "city": "ST LOUIS", "region": "MO", "postal_code": "63101"},
                    ],
                }
            },
            CallableVerifier("verifier.example.address", _address_verifier),
        ),
        ExecutionPolicy(),
        (Objective("quality", "maximize", hard_minimum=1.0), Objective("latency_ms", "minimize", weight=0.1)),
    ),
    ExecutableExample(
        "verified-product-dataset",
        "Verified product dataset",
        "Extract products from captured pages and require independent two-source corroboration.",
        PRODUCT_PROGRAM,
        (
            _route(
                "control",
                "Parser extraction with explicitly insufficient single-source verification.",
                {
                    "acquire": _candidate_id("example.product.acquire.preserve"),
                    "extract": _candidate_id("example.product.extract.parser"),
                    "normalize": _candidate_id("example.product.normalize.float"),
                    "verify": _candidate_id("example.product.verify.single"),
                },
                expected_accepted=False,
            ),
            _route(
                "corroborated",
                "Canonical source order, parser extraction, Decimal money, and cross-source verification.",
                {
                    "acquire": _candidate_id("example.product.acquire.sorted"),
                    "extract": _candidate_id("example.product.extract.parser"),
                    "normalize": _candidate_id("example.product.normalize.decimal"),
                    "verify": _candidate_id("example.product.verify.cross-source"),
                },
            ),
            _route(
                "corroborated-regex",
                "Regex extraction with cross-source corroboration as an alternate route.",
                {
                    "acquire": _candidate_id("example.product.acquire.preserve"),
                    "extract": _candidate_id("example.product.extract.regex"),
                    "normalize": _candidate_id("example.product.normalize.decimal"),
                    "verify": _candidate_id("example.product.verify.cross-source"),
                },
            ),
        ),
        ExperimentCase(
            "case.verified-product-dataset",
            {
                "sources": [
                    {"url": "https://fixture.example/catalog-a", "html": "<article data-sku='SKU-1'><h2>Widget</h2><span class='price'>$19.99</span></article><article data-sku='SKU-2'><h2>Gadget</h2><span class='price'>$8.50</span></article>"},
                    {"url": "https://fixture.example/catalog-b", "html": "<article data-sku='SKU-1'><h2>Widget</h2><span class='price'>$19.99</span></article><article data-sku='SKU-2'><h2>Gadget</h2><span class='price'>$8.50</span></article>"},
                ]
            },
            CallableVerifier("verifier.example.product", _product_verifier),
        ),
        ExecutionPolicy(),
        (Objective("quality", "maximize", hard_minimum=1.0), Objective("latency_ms", "minimize", weight=0.1)),
    ),
    ExecutableExample(
        "calibrated-time-series-forecast",
        "Calibrated time-series forecast",
        "Compare mean/trend models and fixed/empirical interval strategies on a fixed holdout.",
        FORECAST_PROGRAM,
        (
            _route(
                "control",
                "Historical mean with a narrow fixed interval.",
                {
                    "prepare": _candidate_id("example.forecast.prepare.observed"),
                    "fit": _candidate_id("example.forecast.fit.mean"),
                    "forecast": _candidate_id("example.forecast.generate"),
                    "intervals": _candidate_id("example.forecast.interval.fixed"),
                },
                expected_accepted=False,
            ),
            _route(
                "trend-residual",
                "Linear trend with residual-calibrated intervals.",
                {
                    "prepare": _candidate_id("example.forecast.prepare.interpolate"),
                    "fit": _candidate_id("example.forecast.fit.trend"),
                    "forecast": _candidate_id("example.forecast.generate"),
                    "intervals": _candidate_id("example.forecast.interval.residual"),
                },
            ),
        ),
        ExperimentCase(
            "case.calibrated-time-series-forecast",
            {"series": {"train": [1, 2, 3, 4, 5, 6, 7, 8], "holdout": [9, 10], "horizon": 2}},
            CallableVerifier("verifier.example.forecast", _forecast_verifier),
        ),
        ExecutionPolicy(),
        (
            Objective("quality", "maximize"),
            Objective("mae", "minimize", hard_maximum=0.75),
            Objective("coverage", "maximize", hard_minimum=1.0),
            Objective("latency_ms", "minimize", weight=0.1),
        ),
    ),
    ExecutableExample(
        "organization-entity-linking",
        "Organization entity linking",
        "Compare normalization, blocking, and link evidence before building entity components.",
        ENTITY_PROGRAM,
        (
            _route(
                "control",
                "Basic normalization, domain blocking, and exact-name links.",
                {
                    "normalize": _candidate_id("example.entity.normalize.basic"),
                    "block": _candidate_id("example.entity.block.domain"),
                    "link": _candidate_id("example.entity.link.exact"),
                    "components": _candidate_id("example.entity.components"),
                },
                expected_accepted=False,
            ),
            _route(
                "multi-evidence",
                "Legal-suffix normalization, token blocking, and multi-field evidence.",
                {
                    "normalize": _candidate_id("example.entity.normalize.legal"),
                    "block": _candidate_id("example.entity.block.tokens"),
                    "link": _candidate_id("example.entity.link.evidence"),
                    "components": _candidate_id("example.entity.components"),
                },
            ),
            _route(
                "canonical-exact",
                "Legal normalization makes an exact-name linker sufficient.",
                {
                    "normalize": _candidate_id("example.entity.normalize.legal"),
                    "block": _candidate_id("example.entity.block.domain"),
                    "link": _candidate_id("example.entity.link.exact"),
                    "components": _candidate_id("example.entity.components"),
                },
            ),
        ),
        ExperimentCase(
            "case.organization-entity-linking",
            {
                "records": [
                    {"id": "org-1", "name": "Acme Inc.", "domain": "acme.example", "address": "10 Main St"},
                    {"id": "org-2", "name": "ACME Incorporated", "domain": "www.acme.example", "address": "10 Main Street"},
                    {"id": "org-3", "name": "Beta LLC", "domain": "beta.example", "address": "20 Oak Ave"},
                ]
            },
            CallableVerifier("verifier.example.entity", _entity_verifier),
        ),
        ExecutionPolicy(),
        (Objective("quality", "maximize", hard_minimum=1.0), Objective("latency_ms", "minimize", weight=0.1)),
    ),
    ExecutableExample(
        "tested-code-repair",
        "Tested code repair",
        "Inspect and repair a bounded source fixture with two proposal, application, and test strategies.",
        REPAIR_PROGRAM,
        (
            _route(
                "ast-operator",
                "AST inspection, explicit operator patch, exact apply, and restricted case execution.",
                {
                    "inspect": _candidate_id("example.repair.inspect.ast"),
                    "propose": _candidate_id("example.repair.propose.operator"),
                    "apply": _candidate_id("example.repair.apply.exact"),
                    "test": _candidate_id("example.repair.test.ast"),
                },
            ),
            _route(
                "contract-symbolic",
                "Test-contract inspection, derived patch, line apply, and symbolic verification.",
                {
                    "inspect": _candidate_id("example.repair.inspect.tests"),
                    "propose": _candidate_id("example.repair.propose.contract"),
                    "apply": _candidate_id("example.repair.apply.line"),
                    "test": _candidate_id("example.repair.test.symbolic"),
                },
            ),
        ),
        ExperimentCase(
            "case.tested-code-repair",
            {
                "repository": {
                    "files": {"math_utils.py": "def add(a, b):\n    return a - b\n"},
                    "tests": [
                        {"args": [2, 3], "expected": 5},
                        {"args": [-1, 4], "expected": 3},
                        {"args": [0, 0], "expected": 0},
                    ],
                }
            },
            CallableVerifier("verifier.example.repair", _repair_verifier),
        ),
        ExecutionPolicy(),
        (Objective("quality", "maximize", hard_minimum=1.0), Objective("latency_ms", "minimize", weight=0.1)),
    ),
    ExecutableExample(
        "multi-feed-analytical-dataset",
        "Validated multi-feed analytical dataset",
        "Decode, normalize, reconcile, and validate captured CSV and JSON feeds.",
        FEED_PROGRAM,
        (
            _route(
                "control",
                "Strict numeric parsing and whole-record source priority.",
                {
                    "decode": _candidate_id("example.feed.decode.lines"),
                    "normalize": _candidate_id("example.feed.normalize.strict"),
                    "reconcile": _candidate_id("example.feed.reconcile.priority"),
                    "validate": _candidate_id("example.feed.validate.strict"),
                },
                expected_accepted=False,
            ),
            _route(
                "coerce-and-merge",
                "Standard CSV decoding, explicit currency parsing, completeness merge, and lineage validation.",
                {
                    "decode": _candidate_id("example.feed.decode.csv-module"),
                    "normalize": _candidate_id("example.feed.normalize.coerce"),
                    "reconcile": _candidate_id("example.feed.reconcile.complete"),
                    "validate": _candidate_id("example.feed.validate.lineage"),
                },
            ),
            _route(
                "coerce-priority",
                "Line decoding, explicit currency parsing, source priority, and strict validation.",
                {
                    "decode": _candidate_id("example.feed.decode.lines"),
                    "normalize": _candidate_id("example.feed.normalize.coerce"),
                    "reconcile": _candidate_id("example.feed.reconcile.priority"),
                    "validate": _candidate_id("example.feed.validate.strict"),
                },
            ),
        ),
        ExperimentCase(
            "case.multi-feed-analytical-dataset",
            {
                "feeds": {
                    "csv": "id,name,amount\n1,alice,10.50\n2,bob,$20.00\n",
                    "json": [
                        {"id": "2", "name": "Bob", "amount": 20, "category": "B"},
                        {"id": "3", "name": "Cara", "amount": 30, "category": "C"},
                    ],
                }
            },
            CallableVerifier("verifier.example.feed", _feed_verifier),
        ),
        ExecutionPolicy(),
        (Objective("quality", "maximize", hard_minimum=1.0), Objective("latency_ms", "minimize", weight=0.1)),
    ),
)

# Import after the shared dataclasses and core examples exist.  The extended
# module owns a separate registry so adding cross-domain fixtures does not turn
# the original teaching registry into one misleading universal deployment.
from solutiongraph.examples.extended_tasks import EXTENDED_EXAMPLE_TASKS  # noqa: E402

EXAMPLE_TASKS = (*EXAMPLE_TASKS, *EXTENDED_EXAMPLE_TASKS)


def all_examples() -> tuple[ExecutableExample, ...]:
    """Return core fixtures plus lazily loaded reusable-pack compositions."""
    # Lazy import avoids making the foundational example dataclasses depend on
    # the standard-library pack while that pack itself is being imported.
    from solutiongraph.stdlib_pack import STDLIB_DATA_QUALITY_EXAMPLE

    return (*EXAMPLE_TASKS, STDLIB_DATA_QUALITY_EXAMPLE)


def get_example(example_id: str) -> ExecutableExample:
    examples = all_examples()
    try:
        return next(example for example in examples if example.id == example_id)
    except StopIteration as exc:
        known = ", ".join(example.id for example in examples)
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
    "all_examples",
    "get_example",
    "run_example",
]
