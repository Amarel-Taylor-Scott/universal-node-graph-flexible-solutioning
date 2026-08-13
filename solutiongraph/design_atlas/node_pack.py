"""Typed, executable node pack for evidence-driven data-science design."""

from __future__ import annotations

from collections.abc import Iterable

from solutiongraph.authoring import build_python_registry, define_python_node
from solutiongraph.design_atlas.nodes import (
    derive_context_node,
    plan_human_review_node,
    plan_llm_review_node,
    render_report_node,
    resolve_answers_node,
)
from solutiongraph.discovery import (
    ArtifactReference,
    NodeDescriptor,
    NodePackManifest,
    PortMeaning,
    SearchDocument,
)
from solutiongraph.interrogation.node_pack import (
    INTERROGATION_FIELD_MAP,
    INTERROGATION_PROFILE,
)
from solutiongraph.model import (
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

REPOSITORY_SOURCE = (
    "https://github.com/Amarel-Taylor-Scott/universal-node-graph-flexible-solutioning"
)

DESIGN_TASK_REQUEST = ValueType("design-atlas.task-request")
DESIGN_CONTEXT = ValueType("design-atlas.context")
DESIGN_PLAN = ValueType("design-atlas.plan")
DESIGN_ANSWER_SET = ValueType("design-atlas.answer-set")
DESIGN_DOSSIER = ValueType("design-atlas.dossier")
DESIGN_REPORT_BUNDLE = ValueType("design-atlas.report-bundle")

_INVALID_INPUT = (FailureMode("design-atlas.invalid-input", False),)
_EFFORT_PARAMETER = ParameterSpec(
    "effort_level",
    "string",
    default="E3",
    choices=("E1", "E3", "E5", "E7", "E10"),
)
_SEED_PARAMETER = ParameterSpec(
    "random_seed",
    "integer",
    default=0,
    choices=(0, 17, 41),
    description="Explicit exploration seeds keep one deterministic route from dominating.",
)

CONTEXT_DEFINITION = define_python_node(
    node_id="design-atlas.derive-context",
    function=derive_context_node,
    inputs=(
        Port("dataset_profile", INTERROGATION_PROFILE),
        Port("semantic_field_map", INTERROGATION_FIELD_MAP),
        Port("task_request", DESIGN_TASK_REQUEST),
    ),
    outputs=(Port("context", DESIGN_CONTEXT),),
    capabilities=("design-atlas.derive-context",),
    description=(
        "Join declared task intent to aggregate-only profile evidence and preserve exact "
        "profile and semantic-map digests."
    ),
    failure_modes=_INVALID_INPUT,
    source="solutiongraph/design_atlas/nodes/derive_context.py",
)

HUMAN_PLAN_DEFINITION = define_python_node(
    node_id="design-atlas.plan-human-review",
    function=plan_human_review_node,
    inputs=(Port("context", DESIGN_CONTEXT),),
    outputs=(Port("design_plan", DESIGN_PLAN),),
    capabilities=("design-atlas.plan-review",),
    description=(
        "Compile the complete visibility ledger and allocate the effort-bounded selection "
        "to a human reviewer under explicit authority."
    ),
    parameters=(_EFFORT_PARAMETER, _SEED_PARAMETER),
    permissions=("human.review",),
    failure_modes=_INVALID_INPUT,
    source="solutiongraph/design_atlas/nodes/plan_review.py",
)

LLM_PLAN_DEFINITION = define_python_node(
    node_id="design-atlas.plan-llm-review",
    function=plan_llm_review_node,
    inputs=(Port("context", DESIGN_CONTEXT),),
    outputs=(Port("design_plan", DESIGN_PLAN),),
    capabilities=("design-atlas.plan-review",),
    description=(
        "Compile the same review contract for a provider-neutral model responder; "
        "model.invoke must be granted before compiler admission."
    ),
    parameters=(_EFFORT_PARAMETER, _SEED_PARAMETER),
    permissions=("model.invoke",),
    failure_modes=_INVALID_INPUT,
    source="solutiongraph/design_atlas/nodes/plan_review.py",
)

RESOLVE_DEFINITION = define_python_node(
    node_id="design-atlas.resolve-answers",
    function=resolve_answers_node,
    inputs=(
        Port("design_plan", DESIGN_PLAN),
        Port("answer_set", DESIGN_ANSWER_SET),
    ),
    outputs=(Port("design_dossier", DESIGN_DOSSIER),),
    capabilities=("design-atlas.resolve-answers",),
    description=(
        "Validate plan-bound branches and evidence references, with an optional fail-closed "
        "policy that rejects unanswered, blocked, abstained, or provisional work."
    ),
    parameters=(
        ParameterSpec(
            "resolution_policy",
            "string",
            default="allow-provisional",
            choices=("allow-provisional", "evidence-required"),
        ),
    ),
    failure_modes=_INVALID_INPUT,
    source="solutiongraph/design_atlas/nodes/resolve_answers.py",
)

REPORT_DEFINITION = define_python_node(
    node_id="design-atlas.render-report",
    function=render_report_node,
    inputs=(
        Port("context", DESIGN_CONTEXT),
        Port("design_plan", DESIGN_PLAN),
        Port("design_dossier", DESIGN_DOSSIER),
    ),
    outputs=(Port("report_bundle", DESIGN_REPORT_BUNDLE),),
    capabilities=("design-atlas.render-report",),
    description=(
        "Render content-addressed JSON payload, Markdown, and self-contained HTML without "
        "filesystem, model, or network effects."
    ),
    failure_modes=_INVALID_INPUT,
    source="solutiongraph/design_atlas/nodes/render_report.py",
)

DESIGN_ATLAS_NODE_DEFINITIONS = (
    CONTEXT_DEFINITION,
    HUMAN_PLAN_DEFINITION,
    LLM_PLAN_DEFINITION,
    RESOLVE_DEFINITION,
    REPORT_DEFINITION,
)
DESIGN_ATLAS_NODE_SPECS = tuple(item.spec for item in DESIGN_ATLAS_NODE_DEFINITIONS)
DESIGN_ATLAS_CANDIDATES = tuple(
    candidate
    for definition in DESIGN_ATLAS_NODE_DEFINITIONS
    for candidate in definition.candidates()
)
DESIGN_ATLAS_REGISTRY = build_python_registry(
    "registry.data-science-design-atlas",
    "1.0.0",
    DESIGN_ATLAS_NODE_DEFINITIONS,
    candidates=DESIGN_ATLAS_CANDIDATES,
)

DESIGN_ATLAS_DESCRIPTORS = tuple(
    NodeDescriptor(
        node_id=node.id,
        node_version=node.version,
        node_spec_digest=node.digest,
        title=node.id.rsplit(".", 1)[-1].replace("-", " ").title(),
        summary=node.description,
        purposes=(node.description,),
        solutions=("Compose this stage into an evidence-driven design feedback loop.",),
        actions=node.capabilities,
        domains=("data.science", "machine.learning", "ai.assurance"),
        tags=("design-atlas", "typed-node", "runtime.python", "evidence-aware"),
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
                text=node.description,
                targets=("node", "inputs", "outputs"),
                source_digest=node.digest,
            ),
        ),
        extensions=(("design-atlas.maturity", "reference"),),
    )
    for node in DESIGN_ATLAS_NODE_SPECS
)

DESIGN_ATLAS_NODE_PACK = NodePackManifest(
    id="design-atlas.data-science-node-pack",
    version="1.0.0",
    description=(
        "Five individually importable typed nodes for aggregate context derivation, "
        "authority-separated human or LLM planning, evidence-aware resolution, and portable reports."
    ),
    node_spec_digests=tuple(node.digest for node in DESIGN_ATLAS_NODE_SPECS),
    descriptor_digests=tuple(item.digest for item in DESIGN_ATLAS_DESCRIPTORS),
    artifacts=tuple(
        ArtifactReference(
            name=f"artifact.{node.id}",
            media_type="text/x-python",
            digest=node.implementation_digest,
            uri=f"python://{node.entrypoint}",
            annotations=(("org.opencontainers.image.title", node.entrypoint),),
        )
        for node in DESIGN_ATLAS_NODE_SPECS
    ),
    source=REPOSITORY_SOURCE,
    license="MIT",
    extensions=(("design-atlas.maturity", "reference"),),
)


def _slot(slot_id: str, purpose: str, definition, success_contract: str) -> SemanticSlot:
    return SemanticSlot(
        slot_id,
        purpose,
        definition.spec.inputs,
        definition.spec.outputs,
        success_contract,
        required_capabilities=definition.spec.capabilities,
    )


def design_atlas_program(
    *,
    granted_permissions: Iterable[str] = ("human.review",),
) -> ProgramGraph:
    """Build the reference graph with an explicit reviewer authority boundary."""
    return ProgramGraph(
        id="design-atlas.data-science-feedback-loop",
        version="1.0.0",
        task=(
            "Derive a data-science task context, allocate an effort-aware design review, "
            "resolve plan-bound answers, and render an auditable dossier."
        ),
        success_contract=(
            "All 112 questions remain visible, selected answers bind to the exact plan, "
            "and promotion policy is explicit."
        ),
        slots=(
            _slot(
                "context",
                "Derive aggregate task context.",
                CONTEXT_DEFINITION,
                "Context binds declared intent to exact aggregate evidence digests.",
            ),
            _slot(
                "plan",
                "Allocate an authority-aware review plan.",
                HUMAN_PLAN_DEFINITION,
                "Selected, deferred, blocked, and inapplicable questions remain visible.",
            ),
            _slot(
                "resolve",
                "Resolve plan-bound answers.",
                RESOLVE_DEFINITION,
                "Every accepted decision cites evidence and every unresolved item remains explicit.",
            ),
            _slot(
                "report",
                "Render the portable report bundle.",
                REPORT_DEFINITION,
                "JSON, Markdown, and HTML carry the same bound context, plan, and dossier.",
            ),
        ),
        edges=(
            Edge("context", "context", "plan", "context"),
            Edge("plan", "design_plan", "resolve", "design_plan"),
            Edge("context", "context", "report", "context"),
            Edge("plan", "design_plan", "report", "design_plan"),
            Edge("resolve", "design_dossier", "report", "design_dossier"),
        ),
        inputs=(
            GraphInput("dataset_profile", INTERROGATION_PROFILE, "context", "dataset_profile"),
            GraphInput(
                "semantic_field_map",
                INTERROGATION_FIELD_MAP,
                "context",
                "semantic_field_map",
            ),
            GraphInput("task_request", DESIGN_TASK_REQUEST, "context", "task_request"),
            GraphInput("answer_set", DESIGN_ANSWER_SET, "resolve", "answer_set"),
        ),
        outputs=(
            GraphOutput("context", DESIGN_CONTEXT, "context", "context"),
            GraphOutput("design_plan", DESIGN_PLAN, "plan", "design_plan"),
            GraphOutput("design_dossier", DESIGN_DOSSIER, "resolve", "design_dossier"),
            GraphOutput("report_bundle", DESIGN_REPORT_BUNDLE, "report", "report_bundle"),
        ),
        granted_permissions=tuple(dict.fromkeys(granted_permissions)),
        invariants=(
            "Only aggregate dataset profiles and semantic maps enter this graph.",
            "The planning candidate's reviewer permission must be explicitly granted.",
            "Answer sets bind to the exact content-addressed plan.",
            "Cataloged techniques remain non-executable until separate node evidence exists.",
        ),
    )


DESIGN_ATLAS_PROGRAM = design_atlas_program()

__all__ = [
    "CONTEXT_DEFINITION",
    "DESIGN_ANSWER_SET",
    "DESIGN_ATLAS_CANDIDATES",
    "DESIGN_ATLAS_DESCRIPTORS",
    "DESIGN_ATLAS_NODE_DEFINITIONS",
    "DESIGN_ATLAS_NODE_PACK",
    "DESIGN_ATLAS_NODE_SPECS",
    "DESIGN_ATLAS_PROGRAM",
    "DESIGN_ATLAS_REGISTRY",
    "DESIGN_CONTEXT",
    "DESIGN_DOSSIER",
    "DESIGN_PLAN",
    "DESIGN_REPORT_BUNDLE",
    "DESIGN_TASK_REQUEST",
    "HUMAN_PLAN_DEFINITION",
    "LLM_PLAN_DEFINITION",
    "REPORT_DEFINITION",
    "RESOLVE_DEFINITION",
    "design_atlas_program",
]
