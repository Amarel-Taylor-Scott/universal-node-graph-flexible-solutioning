"""Searchable standard-library node pack and an executable composition example."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from solutiongraph import stdlib_nodes as implementations
from solutiongraph.authoring import (
    PythonNodeDefinition,
    bind_candidate,
    build_python_registry,
    define_python_node,
)
from solutiongraph.discovery import (
    ArtifactReference,
    NodeDescriptor,
    NodePackManifest,
    PortMeaning,
    SearchDocument,
)
from solutiongraph.evidence import Objective
from solutiongraph.examples.tasks import ExampleRoute, ExecutableExample
from solutiongraph.executor import (
    CallableVerifier,
    ExecutionPolicy,
    VerificationContext,
    VerificationResult,
)
from solutiongraph.experiments import ExperimentCase
from solutiongraph.model import (
    Candidate,
    Edge,
    FailureMode,
    GraphInput,
    GraphOutput,
    ParameterSpec,
    Port,
    ProgramGraph,
    SemanticSlot,
    ValueType,
)
from solutiongraph.pack_library import REPOSITORY_SOURCE

STDLIB_TEXT = ValueType("stdlib.text", media_type="text/plain")
STDLIB_JSON_TEXT = ValueType("stdlib.json-text", media_type="application/json")
STDLIB_JSON_VALUE = ValueType("stdlib.json-value")
STDLIB_RECORDS = ValueType("stdlib.records")
STDLIB_PROFILE = ValueType("stdlib.records-profile")
STDLIB_DIGEST = ValueType("stdlib.content-digest", media_type="text/plain")


def _definition(
    node_id: str,
    function: Callable[..., Any],
    capability: str | tuple[str, ...],
    inputs: tuple[Port, ...],
    outputs: tuple[Port, ...],
    description: str,
    *,
    parameters: tuple[ParameterSpec, ...] = (),
    failure_modes: tuple[FailureMode, ...] = (),
) -> PythonNodeDefinition:
    capabilities = (capability,) if isinstance(capability, str) else capability
    return define_python_node(
        node_id=node_id,
        function=function,
        inputs=inputs,
        outputs=outputs,
        capabilities=capabilities,
        description=description,
        parameters=parameters,
        failure_modes=failure_modes,
        source="solutiongraph/stdlib_nodes.py",
    )


_RECORD_TRANSFORM_CAPABILITIES = (
    "records.normalize-keys",
    "records.trim-strings",
    "records.normalize-missing",
    "records.casefold-fields",
    "records.deduplicate",
    "records.require-fields",
    "records.filter-complete",
    "records.sort",
)

STANDARD_LIBRARY_DEFINITIONS = (
    _definition(
        "stdlib.records.identity",
        implementations.identity_records,
        ("control.identity", *_RECORD_TRANSFORM_CAPABILITIES),
        (Port("records", STDLIB_RECORDS),),
        (Port("records", STDLIB_RECORDS),),
        "Explicit no-op candidate that copies records and can occupy optional cleanup steps.",
    ),
    _definition(
        "stdlib.text.normalize-unicode",
        implementations.normalize_unicode,
        "text.normalize-unicode",
        (Port("text", STDLIB_TEXT),),
        (Port("text", STDLIB_TEXT),),
        "Normalize text using an explicitly bound Unicode normalization form.",
        parameters=(ParameterSpec("form", "string", default="NFKC", choices=("NFC", "NFKC")),),
    ),
    _definition(
        "stdlib.text.normalize-whitespace",
        implementations.normalize_whitespace,
        "text.normalize-whitespace",
        (Port("text", STDLIB_TEXT),),
        (Port("text", STDLIB_TEXT),),
        "Normalize whitespace while preserving lines or compacting all whitespace.",
        parameters=(ParameterSpec("mode", "string", default="lines", choices=("lines", "compact")),),
    ),
    _definition(
        "stdlib.text.strip-controls",
        implementations.strip_control_characters,
        "text.strip-controls",
        (Port("text", STDLIB_TEXT),),
        (Port("text", STDLIB_TEXT),),
        "Remove Unicode control characters under an explicit newline policy.",
        parameters=(ParameterSpec("preserve_newlines", "boolean", default=True, choices=(True, False)),),
    ),
    _definition(
        "stdlib.data.parse-json",
        implementations.parse_json_value,
        "data.parse-json",
        (Port("text", STDLIB_JSON_TEXT),),
        (Port("value", STDLIB_JSON_VALUE),),
        "Parse strict JSON without repair.",
        failure_modes=(FailureMode("data.invalid-json", False),),
    ),
    _definition(
        "stdlib.data.parse-jsonl",
        implementations.parse_json_lines,
        "data.parse-records",
        (Port("text", STDLIB_TEXT),),
        (Port("records", STDLIB_RECORDS),),
        "Parse newline-delimited JSON objects.",
        failure_modes=(FailureMode("data.invalid-jsonl", False),),
    ),
    _definition(
        "stdlib.data.parse-delimited",
        implementations.parse_delimited_records,
        "data.parse-records",
        (Port("text", STDLIB_TEXT),),
        (Port("records", STDLIB_RECORDS),),
        "Parse comma-, semicolon-, or tab-delimited records.",
        parameters=(ParameterSpec("delimiter", "string", default=",", choices=(",", ";", "\t")),),
        failure_modes=(FailureMode("data.invalid-delimited", False),),
    ),
    _definition(
        "stdlib.records.normalize-keys",
        implementations.normalize_record_keys,
        "records.normalize-keys",
        (Port("records", STDLIB_RECORDS),),
        (Port("records", STDLIB_RECORDS),),
        "Normalize top-level record keys with collision detection.",
        parameters=(ParameterSpec("mode", "string", default="snake", choices=("lower", "snake")),),
        failure_modes=(FailureMode("records.key-collision", False),),
    ),
    _definition(
        "stdlib.records.trim-strings",
        implementations.trim_record_strings,
        "records.trim-strings",
        (Port("records", STDLIB_RECORDS),),
        (Port("records", STDLIB_RECORDS),),
        "Trim string fields with a shallow or recursive policy.",
        parameters=(ParameterSpec("recursive", "boolean", default=False, choices=(False, True)),),
    ),
    _definition(
        "stdlib.records.normalize-missing",
        implementations.normalize_missing_values,
        "records.normalize-missing",
        (Port("records", STDLIB_RECORDS),),
        (Port("records", STDLIB_RECORDS),),
        "Map an explicitly configured set of string sentinels to null.",
        parameters=(
            ParameterSpec(
                "sentinels",
                "array[string]",
                default=("", "na", "n/a", "null", "none"),
            ),
        ),
    ),
    _definition(
        "stdlib.records.casefold-fields",
        implementations.casefold_record_fields,
        "records.casefold-fields",
        (Port("records", STDLIB_RECORDS),),
        (Port("records", STDLIB_RECORDS),),
        "Case-fold only explicitly selected fields.",
        parameters=(ParameterSpec("fields", "array[string]", required=True),),
    ),
    _definition(
        "stdlib.records.project-fields",
        implementations.project_record_fields,
        "records.project-fields",
        (Port("records", STDLIB_RECORDS),),
        (Port("records", STDLIB_RECORDS),),
        "Project records to an explicitly ordered field set.",
        parameters=(ParameterSpec("fields", "array[string]", required=True),),
    ),
    _definition(
        "stdlib.records.require-fields",
        implementations.require_record_fields,
        "records.require-fields",
        (Port("records", STDLIB_RECORDS),),
        (Port("records", STDLIB_RECORDS),),
        "Reject records missing configured nonempty fields.",
        parameters=(ParameterSpec("fields", "array[string]", required=True),),
        failure_modes=(FailureMode("records.required-field-missing", False),),
    ),
    _definition(
        "stdlib.records.filter-complete",
        implementations.filter_complete_records,
        "records.filter-complete",
        (Port("records", STDLIB_RECORDS),),
        (Port("records", STDLIB_RECORDS),),
        "Keep records containing every configured nonempty field.",
        parameters=(ParameterSpec("fields", "array[string]", required=True),),
    ),
    _definition(
        "stdlib.records.deduplicate",
        implementations.deduplicate_records,
        "records.deduplicate",
        (Port("records", STDLIB_RECORDS),),
        (Port("records", STDLIB_RECORDS),),
        "Deduplicate by exact or canonicalized configured keys.",
        parameters=(
            ParameterSpec("key_fields", "array[string]", required=True),
            ParameterSpec("canonical", "boolean", default=False, choices=(False, True)),
        ),
    ),
    _definition(
        "stdlib.records.sort",
        implementations.sort_records,
        "records.sort",
        (Port("records", STDLIB_RECORDS),),
        (Port("records", STDLIB_RECORDS),),
        "Sort records deterministically by configured fields.",
        parameters=(
            ParameterSpec("fields", "array[string]", required=True),
            ParameterSpec("reverse", "boolean", default=False, choices=(False, True)),
        ),
    ),
    _definition(
        "stdlib.records.profile",
        implementations.profile_records,
        "records.profile",
        (Port("records", STDLIB_RECORDS),),
        (Port("profile", STDLIB_PROFILE),),
        "Measure row count, field union, and missingness deterministically.",
    ),
    _definition(
        "stdlib.records.hash",
        implementations.hash_records,
        "records.hash",
        (Port("records", STDLIB_RECORDS),),
        (Port("digest", STDLIB_DIGEST),),
        "Content-address an exact ordered record collection.",
    ),
    _definition(
        "stdlib.records.emit-profile",
        implementations.emit_records_with_profile,
        "records.emit-profile",
        (Port("records", STDLIB_RECORDS),),
        (Port("records", STDLIB_RECORDS), Port("profile", STDLIB_PROFILE)),
        "Emit cleaned records and a quality profile as separately typed outputs.",
        parameters=(ParameterSpec("include_digest", "boolean", default=True, choices=(True, False)),),
    ),
)

_DEFINITION_BY_ID = {item.spec.id: item for item in STANDARD_LIBRARY_DEFINITIONS}


def _candidate(
    node_id: str,
    suffix: str,
    parameters: Mapping[str, Any] | None = None,
) -> Candidate:
    return bind_candidate(
        _DEFINITION_BY_ID[node_id].spec,
        parameters or {},
        candidate_id=f"candidate.{node_id}.{suffix}",
    )


STANDARD_LIBRARY_CANDIDATES = (
    _candidate("stdlib.records.identity", "default"),
    _candidate("stdlib.text.normalize-unicode", "nfc", {"form": "NFC"}),
    _candidate("stdlib.text.normalize-unicode", "nfkc", {"form": "NFKC"}),
    _candidate("stdlib.text.normalize-whitespace", "lines", {"mode": "lines"}),
    _candidate("stdlib.text.normalize-whitespace", "compact", {"mode": "compact"}),
    _candidate("stdlib.text.strip-controls", "preserve-lines", {"preserve_newlines": True}),
    _candidate("stdlib.text.strip-controls", "all", {"preserve_newlines": False}),
    _candidate("stdlib.data.parse-json", "strict"),
    _candidate("stdlib.data.parse-jsonl", "strict"),
    _candidate("stdlib.data.parse-delimited", "csv", {"delimiter": ","}),
    _candidate("stdlib.data.parse-delimited", "semicolon", {"delimiter": ";"}),
    _candidate("stdlib.data.parse-delimited", "tsv", {"delimiter": "\t"}),
    _candidate("stdlib.records.normalize-keys", "lower", {"mode": "lower"}),
    _candidate("stdlib.records.normalize-keys", "snake", {"mode": "snake"}),
    _candidate("stdlib.records.trim-strings", "shallow", {"recursive": False}),
    _candidate("stdlib.records.trim-strings", "recursive", {"recursive": True}),
    _candidate("stdlib.records.normalize-missing", "common"),
    _candidate("stdlib.records.casefold-fields", "email", {"fields": ("email",)}),
    _candidate("stdlib.records.casefold-fields", "company", {"fields": ("company",)}),
    _candidate(
        "stdlib.records.casefold-fields",
        "company-email",
        {"fields": ("company", "email")},
    ),
    _candidate(
        "stdlib.records.project-fields",
        "entity-core",
        {"fields": ("id", "company", "email")},
    ),
    _candidate("stdlib.records.require-fields", "email", {"fields": ("email",)}),
    _candidate(
        "stdlib.records.require-fields",
        "company-email",
        {"fields": ("company", "email")},
    ),
    _candidate(
        "stdlib.records.filter-complete",
        "company-email",
        {"fields": ("company", "email")},
    ),
    _candidate(
        "stdlib.records.deduplicate",
        "email-exact",
        {"key_fields": ("email",), "canonical": False},
    ),
    _candidate(
        "stdlib.records.deduplicate",
        "email-canonical",
        {"key_fields": ("email",), "canonical": True},
    ),
    _candidate(
        "stdlib.records.deduplicate",
        "company-email-canonical",
        {"key_fields": ("company", "email"), "canonical": True},
    ),
    _candidate(
        "stdlib.records.sort",
        "company-ascending",
        {"fields": ("company",), "reverse": False},
    ),
    _candidate("stdlib.records.profile", "basic"),
    _candidate("stdlib.records.hash", "sha256"),
    _candidate("stdlib.records.emit-profile", "with-digest", {"include_digest": True}),
    _candidate("stdlib.records.emit-profile", "without-digest", {"include_digest": False}),
)

STANDARD_LIBRARY_REGISTRY = build_python_registry(
    "registry.solutiongraph-stdlib",
    "1.0.0",
    STANDARD_LIBRARY_DEFINITIONS,
    candidates=STANDARD_LIBRARY_CANDIDATES,
)
STANDARD_LIBRARY_NODE_SPECS = tuple(item.spec for item in STANDARD_LIBRARY_DEFINITIONS)

STANDARD_LIBRARY_DESCRIPTORS = tuple(
    NodeDescriptor(
        node_id=node.id,
        node_version=node.version,
        node_spec_digest=node.digest,
        title=node.id.rsplit(".", 1)[-1].replace("-", " ").title(),
        summary=node.description,
        purposes=(node.description,),
        solutions=("Compose this primitive into typed data preparation graphs.",),
        actions=node.capabilities,
        domains=("data.engineering",),
        tags=("stdlib.reusable", "runtime.python"),
        aliases=tuple(capability.replace(".", " ") for capability in node.capabilities),
        ports=tuple(
            PortMeaning("input", port.name, port.description or f"Typed {port.name} input.")
            for port in node.inputs
        )
        + tuple(
            PortMeaning("output", port.name, port.description or f"Typed {port.name} output.")
            for port in node.outputs
        ),
        documents=(
            SearchDocument(
                id=f"document.{node.id}",
                text=(
                    f"{node.description} Inputs: {', '.join(port.name for port in node.inputs) or 'none'}. "
                    f"Outputs: {', '.join(port.name for port in node.outputs) or 'none'}."
                ),
                targets=("node", "inputs", "outputs"),
                source_digest=node.digest,
            ),
        ),
        extensions=(("stdlib.maturity", "reference"),),
    )
    for node in STANDARD_LIBRARY_NODE_SPECS
)

STANDARD_LIBRARY_NODE_PACK = NodePackManifest(
    id="stdlib.data-foundation-node-pack",
    version="1.0.0",
    description=(
        "Reusable, dependency-free, typed text and record primitives with explicit "
        "no-op candidates, curated parameter bindings, and discovery sidecars."
    ),
    node_spec_digests=tuple(node.digest for node in STANDARD_LIBRARY_NODE_SPECS),
    descriptor_digests=tuple(item.digest for item in STANDARD_LIBRARY_DESCRIPTORS),
    artifacts=tuple(
        ArtifactReference(
            name=f"artifact.{node.id}",
            media_type="text/x-python",
            digest=node.implementation_digest,
            uri=f"python://{node.entrypoint}",
            annotations=(("org.opencontainers.image.title", node.entrypoint),),
        )
        for node in STANDARD_LIBRARY_NODE_SPECS
    ),
    source=REPOSITORY_SOURCE,
    license="MIT",
    extensions=(("stdlib.maturity", "reference"),),
)


def _slot(slot_id: str, purpose: str, capability: str) -> SemanticSlot:
    return SemanticSlot(
        slot_id,
        purpose,
        (Port("records", STDLIB_RECORDS),),
        (Port("records", STDLIB_RECORDS),),
        "The output remains a JSON-compatible record collection.",
        required_capabilities=(capability,),
    )


STDLIB_DATA_QUALITY_PROGRAM = ProgramGraph(
    id="example.stdlib-data-quality",
    version="1.0.0",
    task="Clean, deduplicate, validate, and profile a generic record collection.",
    success_contract=(
        "An independent verifier accepts unique normalized emails, complete entity "
        "fields, and a profile bound to the emitted records."
    ),
    slots=(
        _slot("normalize_keys", "Normalize record keys.", "records.normalize-keys"),
        _slot("trim_strings", "Trim string values.", "records.trim-strings"),
        _slot("normalize_missing", "Normalize missing sentinels.", "records.normalize-missing"),
        _slot("casefold_fields", "Normalize selected case-insensitive fields.", "records.casefold-fields"),
        _slot("deduplicate", "Remove duplicate entities by an explicit key policy.", "records.deduplicate"),
        _slot("validate", "Require the task's mandatory fields.", "records.require-fields"),
        SemanticSlot(
            "emit",
            "Emit cleaned records and a quality profile.",
            (Port("records", STDLIB_RECORDS),),
            (Port("records", STDLIB_RECORDS), Port("profile", STDLIB_PROFILE)),
            "Records and their deterministic profile are emitted together.",
            required_capabilities=("records.emit-profile",),
        ),
    ),
    edges=(
        Edge("normalize_keys", "records", "trim_strings", "records"),
        Edge("trim_strings", "records", "normalize_missing", "records"),
        Edge("normalize_missing", "records", "casefold_fields", "records"),
        Edge("casefold_fields", "records", "deduplicate", "records"),
        Edge("deduplicate", "records", "validate", "records"),
        Edge("validate", "records", "emit", "records"),
    ),
    inputs=(GraphInput("records", STDLIB_RECORDS, "normalize_keys", "records"),),
    outputs=(
        GraphOutput("records", STDLIB_RECORDS, "emit", "records"),
        GraphOutput("profile", STDLIB_PROFILE, "emit", "profile"),
    ),
)


def _stdlib_verifier(context: VerificationContext) -> VerificationResult:
    records = context.outputs["records"]
    profile = context.outputs["profile"]
    emails = [str(record.get("email", "")) for record in records]
    accepted = (
        len(records) == 2
        and len(emails) == len(set(emails))
        and all(email == email.casefold() and email for email in emails)
        and all(record.get("company") for record in records)
        and profile.get("row_count") == len(records)
        and str(profile.get("records_digest", "")).startswith("sha256:")
    )
    checks = sum(
        (
            len(records) == 2,
            len(emails) == len(set(emails)),
            all(email == email.casefold() and email for email in emails),
            all(record.get("company") for record in records),
            profile.get("row_count") == len(records),
            str(profile.get("records_digest", "")).startswith("sha256:"),
        )
    )
    return VerificationResult(
        accepted,
        "clean-record-contract-met" if accepted else "clean-record-contract-missed",
        {"quality": checks / 6},
        {"row_count": len(records), "emails": emails, "profile": profile},
    )


def _route(
    route_id: str,
    description: str,
    selection: Mapping[str, str],
    *,
    expected_accepted: bool,
) -> ExampleRoute:
    return ExampleRoute(
        route_id,
        description,
        dict(selection),
        {},
        expected_accepted,
    )


STDLIB_DATA_QUALITY_EXAMPLE = ExecutableExample(
    "stdlib-data-quality",
    "Reusable standard-library data quality",
    "Compose generic node-pack primitives rather than task-specific workflow functions.",
    STDLIB_DATA_QUALITY_PROGRAM,
    (
        _route(
            "control",
            "Lower keys, trim, preserve email case, and deduplicate exact email values.",
            {
                "normalize_keys": "candidate.stdlib.records.normalize-keys.lower",
                "trim_strings": "candidate.stdlib.records.trim-strings.shallow",
                "normalize_missing": "candidate.stdlib.records.normalize-missing.common",
                "casefold_fields": "candidate.stdlib.records.casefold-fields.company",
                "deduplicate": "candidate.stdlib.records.deduplicate.email-exact",
                "validate": "candidate.stdlib.records.require-fields.email",
                "emit": "candidate.stdlib.records.emit-profile.with-digest",
            },
            expected_accepted=False,
        ),
        _route(
            "robust",
            "Snake-case keys, recursively trim, case-fold identity fields, and dedupe canonical email.",
            {
                "normalize_keys": "candidate.stdlib.records.normalize-keys.snake",
                "trim_strings": "candidate.stdlib.records.trim-strings.recursive",
                "normalize_missing": "candidate.stdlib.records.normalize-missing.common",
                "casefold_fields": "candidate.stdlib.records.casefold-fields.company-email",
                "deduplicate": "candidate.stdlib.records.deduplicate.email-canonical",
                "validate": "candidate.stdlib.records.require-fields.company-email",
                "emit": "candidate.stdlib.records.emit-profile.with-digest",
            },
            expected_accepted=True,
        ),
        _route(
            "pass-through-control",
            "Use explicit identity candidates for every optional cleanup obligation.",
            {
                "normalize_keys": "candidate.stdlib.records.identity.default",
                "trim_strings": "candidate.stdlib.records.identity.default",
                "normalize_missing": "candidate.stdlib.records.identity.default",
                "casefold_fields": "candidate.stdlib.records.identity.default",
                "deduplicate": "candidate.stdlib.records.identity.default",
                "validate": "candidate.stdlib.records.identity.default",
                "emit": "candidate.stdlib.records.emit-profile.with-digest",
            },
            expected_accepted=False,
        ),
    ),
    ExperimentCase(
        "case.stdlib-data-quality",
        {
            "records": [
                {"Company": " Acme Labs ", "Email": "A@EXAMPLE.COM", "Status": "N/A"},
                {"company": "acme labs", "email": "a@example.com", "status": ""},
                {"Company": "Beta LLC", "Email": "b@example.com", "Status": "active"},
            ]
        },
        CallableVerifier("verifier.stdlib.data-quality", _stdlib_verifier),
    ),
    ExecutionPolicy(),
    (Objective("quality", "maximize", hard_minimum=1.0), Objective("latency_ms", "minimize", weight=0.1)),
    registry=STANDARD_LIBRARY_REGISTRY,
)


__all__ = [
    "STANDARD_LIBRARY_CANDIDATES",
    "STANDARD_LIBRARY_DEFINITIONS",
    "STANDARD_LIBRARY_DESCRIPTORS",
    "STANDARD_LIBRARY_NODE_PACK",
    "STANDARD_LIBRARY_NODE_SPECS",
    "STANDARD_LIBRARY_REGISTRY",
    "STDLIB_DATA_QUALITY_EXAMPLE",
    "STDLIB_DATA_QUALITY_PROGRAM",
    "STDLIB_DIGEST",
    "STDLIB_JSON_TEXT",
    "STDLIB_JSON_VALUE",
    "STDLIB_PROFILE",
    "STDLIB_RECORDS",
    "STDLIB_TEXT",
]
