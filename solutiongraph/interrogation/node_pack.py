"""Typed node pack and executable program for semantic data interrogation."""

from __future__ import annotations

from solutiongraph.authoring import build_python_registry, define_python_node
from solutiongraph.discovery import (
    ArtifactReference,
    NodeDescriptor,
    NodePackManifest,
    PortMeaning,
    SearchDocument,
)
from solutiongraph.interrogation.nodes import (
    apply_shadow_node,
    execute_questions_node,
    map_fields_node,
    plan_questions_node,
    profile_records_node,
    propose_repairs_node,
    rebind_plan_node,
    verify_repairs_node,
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

INTERROGATION_RECORDS = ValueType("interrogation.records")
INTERROGATION_PROFILE = ValueType("interrogation.dataset-profile")
INTERROGATION_FIELD_MAP = ValueType("interrogation.semantic-field-map")
INTERROGATION_PLAN = ValueType("interrogation.question-plan")
INTERROGATION_FINDINGS = ValueType("interrogation.finding-set")
INTERROGATION_REPAIR_PROPOSAL = ValueType("interrogation.repair-proposal")
INTERROGATION_APPLICATION = ValueType("interrogation.repair-application")
INTERROGATION_VERIFICATION = ValueType("interrogation.verification-receipt")

_INVALID_INPUT = (FailureMode("interrogation.invalid-input", False),)

PROFILE_DEFINITION = define_python_node(
    node_id="interrogation.profile-records",
    function=profile_records_node,
    inputs=(Port("records", INTERROGATION_RECORDS),),
    outputs=(
        Port("records", INTERROGATION_RECORDS),
        Port("profile", INTERROGATION_PROFILE),
    ),
    capabilities=("interrogation.profile-records",),
    description=(
        "Create an aggregate-only, content-addressed profile and pass records through "
        "without retaining raw sample values in the profile."
    ),
    parameters=(
        ParameterSpec(
            "sample_limit",
            "integer",
            default=0,
            choices=(0, 1000),
            description="Zero profiles every row; 1000 is an explicit bounded alternative.",
        ),
    ),
    failure_modes=_INVALID_INPUT,
    source="solutiongraph/interrogation/nodes/profile_records.py",
)

MAP_DEFINITION = define_python_node(
    node_id="interrogation.map-semantic-fields",
    function=map_fields_node,
    inputs=(Port("profile", INTERROGATION_PROFILE),),
    outputs=(Port("semantic_field_map", INTERROGATION_FIELD_MAP),),
    capabilities=("interrogation.map-semantic-fields",),
    description=(
        "Map field names to versioned concepts using an explicit exact, conservative, "
        "or broad policy; a match never implies validity."
    ),
    parameters=(
        ParameterSpec(
            "mapping_strategy",
            "string",
            default="conservative",
            choices=("exact", "conservative", "broad"),
        ),
    ),
    failure_modes=_INVALID_INPUT,
    source="solutiongraph/interrogation/nodes/map_fields.py",
)

PLAN_DEFINITION = define_python_node(
    node_id="interrogation.plan-questions",
    function=plan_questions_node,
    inputs=(
        Port("profile", INTERROGATION_PROFILE),
        Port("semantic_field_map", INTERROGATION_FIELD_MAP),
    ),
    outputs=(Port("question_plan", INTERROGATION_PLAN),),
    capabilities=("interrogation.plan-questions",),
    description=(
        "Compile a complete visible plan, selecting eligible questions under an explicit "
        "effort, exploration, and cost budget."
    ),
    parameters=(
        ParameterSpec(
            "effort_level",
            "string",
            default="E3",
            choices=("E1", "E3", "E5", "E7", "E10"),
        ),
        ParameterSpec(
            "planning_strategy",
            "string",
            default="risk-first",
            choices=("risk-first", "coverage-first"),
        ),
        ParameterSpec(
            "random_seed",
            "integer",
            default=0,
            choices=(0, 17, 41),
            description="Explicit exploration seeds prevent a single historical route from dominating.",
        ),
    ),
    failure_modes=_INVALID_INPUT,
    source="solutiongraph/interrogation/nodes/plan_questions.py",
)

EXECUTE_DEFINITION = define_python_node(
    node_id="interrogation.execute-questions",
    function=execute_questions_node,
    inputs=(
        Port("records", INTERROGATION_RECORDS),
        Port("profile", INTERROGATION_PROFILE),
        Port("semantic_field_map", INTERROGATION_FIELD_MAP),
        Port("question_plan", INTERROGATION_PLAN),
    ),
    outputs=(Port("finding_set", INTERROGATION_FINDINGS),),
    capabilities=("interrogation.execute-questions",),
    description=(
        "Execute only selected deterministic checks and emit implementation-bound receipts "
        "plus privacy-minimized findings."
    ),
    failure_modes=(
        *_INVALID_INPUT,
        FailureMode("interrogation.check-adapter-error", False),
    ),
    source="solutiongraph/interrogation/nodes/execute_questions.py",
)

PROPOSE_DEFINITION = define_python_node(
    node_id="interrogation.propose-repairs",
    function=propose_repairs_node,
    inputs=(
        Port("records", INTERROGATION_RECORDS),
        Port("finding_set", INTERROGATION_FINDINGS),
    ),
    outputs=(Port("repair_proposal", INTERROGATION_REPAIR_PROPOSAL),),
    capabilities=("interrogation.propose-repairs",),
    description=(
        "Translate supported findings into conservative, reversible patches while retaining "
        "uncertain changes as review-only operations."
    ),
    parameters=(
        ParameterSpec(
            "repair_strategy",
            "string",
            default="safe-only",
            choices=("safe-only", "safe-and-review"),
        ),
    ),
    failure_modes=_INVALID_INPUT,
    source="solutiongraph/interrogation/nodes/propose_repairs.py",
)

APPLY_DEFINITION = define_python_node(
    node_id="interrogation.apply-shadow-repairs",
    function=apply_shadow_node,
    inputs=(
        Port("records", INTERROGATION_RECORDS),
        Port("repair_proposal", INTERROGATION_REPAIR_PROPOSAL),
    ),
    outputs=(
        Port("shadow_records", INTERROGATION_RECORDS),
        Port("application_receipt", INTERROGATION_APPLICATION),
    ),
    capabilities=("interrogation.apply-shadow-repairs",),
    description=(
        "Apply digest-checked operations to a deep shadow copy and emit an exact reversible receipt."
    ),
    parameters=(
        ParameterSpec(
            "include_review_operations",
            "boolean",
            default=False,
            choices=(False, True),
        ),
    ),
    failure_modes=_INVALID_INPUT,
    source="solutiongraph/interrogation/nodes/apply_shadow.py",
)

REBIND_DEFINITION = define_python_node(
    node_id="interrogation.rebind-verification-plan",
    function=rebind_plan_node,
    inputs=(
        Port("question_plan", INTERROGATION_PLAN),
        Port("shadow_profile", INTERROGATION_PROFILE),
        Port("shadow_field_map", INTERROGATION_FIELD_MAP),
    ),
    outputs=(Port("verification_plan", INTERROGATION_PLAN),),
    capabilities=("interrogation.rebind-verification-plan",),
    description=(
        "Bind the same selected checks to the shadow profile so verification cannot silently "
        "choose an easier post-repair suite."
    ),
    failure_modes=_INVALID_INPUT,
    source="solutiongraph/interrogation/nodes/rebind_plan.py",
)

VERIFY_DEFINITION = define_python_node(
    node_id="interrogation.verify-repairs",
    function=verify_repairs_node,
    inputs=(
        Port("source_records", INTERROGATION_RECORDS),
        Port("shadow_records", INTERROGATION_RECORDS),
        Port("repair_proposal", INTERROGATION_REPAIR_PROPOSAL),
        Port("application_receipt", INTERROGATION_APPLICATION),
        Port("before_findings", INTERROGATION_FINDINGS),
        Port("after_findings", INTERROGATION_FINDINGS),
    ),
    outputs=(Port("verification", INTERROGATION_VERIFICATION),),
    capabilities=("interrogation.verify-repairs",),
    description=(
        "Independently diff source and shadow data, compare finding signatures, and fail closed "
        "on undeclared or harmful changes."
    ),
    parameters=(
        ParameterSpec("strict", "boolean", default=True, choices=(True, False)),
    ),
    verifier="verifier.independent-shadow-diff",
    failure_modes=_INVALID_INPUT,
    source="solutiongraph/interrogation/nodes/verify_repairs.py",
)

INTERROGATION_NODE_DEFINITIONS = (
    PROFILE_DEFINITION,
    MAP_DEFINITION,
    PLAN_DEFINITION,
    EXECUTE_DEFINITION,
    PROPOSE_DEFINITION,
    APPLY_DEFINITION,
    REBIND_DEFINITION,
    VERIFY_DEFINITION,
)
INTERROGATION_NODE_SPECS = tuple(item.spec for item in INTERROGATION_NODE_DEFINITIONS)
INTERROGATION_CANDIDATES = tuple(
    candidate
    for definition in INTERROGATION_NODE_DEFINITIONS
    for candidate in definition.candidates()
)
INTERROGATION_REGISTRY = build_python_registry(
    "registry.semantic-interrogation",
    "1.0.0",
    INTERROGATION_NODE_DEFINITIONS,
    candidates=INTERROGATION_CANDIDATES,
)

INTERROGATION_DESCRIPTORS = tuple(
    NodeDescriptor(
        node_id=node.id,
        node_version=node.version,
        node_spec_digest=node.digest,
        title=node.id.rsplit(".", 1)[-1].replace("-", " ").title(),
        summary=node.description,
        purposes=(node.description,),
        solutions=("Compose this stage into an auditable data interrogation feedback loop.",),
        actions=node.capabilities,
        domains=("data.quality", "data.engineering", "ai.assurance"),
        tags=("question-bank", "shadow-repair", "typed-node", "runtime.python"),
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
        extensions=(("interrogation.maturity", "reference"),),
    )
    for node in INTERROGATION_NODE_SPECS
)

INTERROGATION_NODE_PACK = NodePackManifest(
    id="interrogation.semantic-data-node-pack",
    version="1.0.0",
    description=(
        "Eight individually importable typed nodes for aggregate profiling, semantic mapping, "
        "effort-aware question planning, deterministic checks, conservative proposals, reversible "
        "shadow application, fixed-suite reruns, and independent verification."
    ),
    node_spec_digests=tuple(node.digest for node in INTERROGATION_NODE_SPECS),
    descriptor_digests=tuple(item.digest for item in INTERROGATION_DESCRIPTORS),
    artifacts=tuple(
        ArtifactReference(
            name=f"artifact.{node.id}",
            media_type="text/x-python",
            digest=node.implementation_digest,
            uri=f"python://{node.entrypoint}",
            annotations=(("org.opencontainers.image.title", node.entrypoint),),
        )
        for node in INTERROGATION_NODE_SPECS
    ),
    source=REPOSITORY_SOURCE,
    license="MIT",
    extensions=(("interrogation.maturity", "reference"),),
)


def _slot(
    slot_id: str,
    purpose: str,
    definition,
    success_contract: str,
) -> SemanticSlot:
    return SemanticSlot(
        slot_id,
        purpose,
        definition.spec.inputs,
        definition.spec.outputs,
        success_contract,
        required_capabilities=definition.spec.capabilities,
    )


INTERROGATION_PROGRAM = ProgramGraph(
    id="interrogation.semantic-data-feedback-loop",
    version="1.0.0",
    task=(
        "Interrogate generic records with semantic question banks, propose conservative repairs, "
        "and independently verify a shadow result."
    ),
    success_contract=(
        "Every question is visible, every executed check has a receipt, source records are not "
        "mutated, and the independent verifier explicitly promotes, quarantines, or rejects the shadow."
    ),
    slots=(
        _slot("source_profile", "Profile source records.", PROFILE_DEFINITION, "The profile is aggregate-only and bound to the full input digest."),
        _slot("source_map", "Map source fields to concepts.", MAP_DEFINITION, "Every source field is mapped once or listed as unmapped."),
        _slot("question_plan", "Compile a visible effort-aware question plan.", PLAN_DEFINITION, "Selected, deferred, blocked, and inapplicable questions remain visible."),
        _slot("source_checks", "Execute source checks.", EXECUTE_DEFINITION, "Each selected check emits an implementation-bound receipt."),
        _slot("repair_proposal", "Propose reversible repairs.", PROPOSE_DEFINITION, "Every proposed change cites a finding and preserves its before value."),
        _slot("shadow_apply", "Apply the proposal to a shadow copy.", APPLY_DEFINITION, "The source stays unchanged and every applied operation is receipted."),
        _slot("shadow_profile", "Profile the shadow records.", PROFILE_DEFINITION, "The shadow profile identifies the exact shadow digest."),
        _slot("shadow_map", "Map shadow fields to concepts.", MAP_DEFINITION, "Shadow mapping uses the declared mapping policy."),
        _slot("verification_plan", "Rebind the original selected checks.", REBIND_DEFINITION, "Verification preserves the source suite rather than replanning it."),
        _slot("shadow_checks", "Rerun checks on the shadow.", EXECUTE_DEFINITION, "After findings use the same selected question definitions."),
        _slot("verify", "Verify repair effects independently.", VERIFY_DEFINITION, "Undeclared or harmful changes fail closed."),
    ),
    edges=(
        Edge("source_profile", "profile", "source_map", "profile"),
        Edge("source_profile", "profile", "question_plan", "profile"),
        Edge("source_map", "semantic_field_map", "question_plan", "semantic_field_map"),
        Edge("source_profile", "records", "source_checks", "records"),
        Edge("source_profile", "profile", "source_checks", "profile"),
        Edge("source_map", "semantic_field_map", "source_checks", "semantic_field_map"),
        Edge("question_plan", "question_plan", "source_checks", "question_plan"),
        Edge("source_profile", "records", "repair_proposal", "records"),
        Edge("source_checks", "finding_set", "repair_proposal", "finding_set"),
        Edge("source_profile", "records", "shadow_apply", "records"),
        Edge("repair_proposal", "repair_proposal", "shadow_apply", "repair_proposal"),
        Edge("shadow_apply", "shadow_records", "shadow_profile", "records"),
        Edge("shadow_profile", "profile", "shadow_map", "profile"),
        Edge("question_plan", "question_plan", "verification_plan", "question_plan"),
        Edge("shadow_profile", "profile", "verification_plan", "shadow_profile"),
        Edge("shadow_map", "semantic_field_map", "verification_plan", "shadow_field_map"),
        Edge("shadow_profile", "records", "shadow_checks", "records"),
        Edge("shadow_profile", "profile", "shadow_checks", "profile"),
        Edge("shadow_map", "semantic_field_map", "shadow_checks", "semantic_field_map"),
        Edge("verification_plan", "verification_plan", "shadow_checks", "question_plan"),
        Edge("source_profile", "records", "verify", "source_records"),
        Edge("shadow_profile", "records", "verify", "shadow_records"),
        Edge("repair_proposal", "repair_proposal", "verify", "repair_proposal"),
        Edge("shadow_apply", "application_receipt", "verify", "application_receipt"),
        Edge("source_checks", "finding_set", "verify", "before_findings"),
        Edge("shadow_checks", "finding_set", "verify", "after_findings"),
    ),
    inputs=(GraphInput("records", INTERROGATION_RECORDS, "source_profile", "records"),),
    outputs=(
        GraphOutput("source_profile", INTERROGATION_PROFILE, "source_profile", "profile"),
        GraphOutput("semantic_field_map", INTERROGATION_FIELD_MAP, "source_map", "semantic_field_map"),
        GraphOutput("question_plan", INTERROGATION_PLAN, "question_plan", "question_plan"),
        GraphOutput("before_findings", INTERROGATION_FINDINGS, "source_checks", "finding_set"),
        GraphOutput("repair_proposal", INTERROGATION_REPAIR_PROPOSAL, "repair_proposal", "repair_proposal"),
        GraphOutput("repaired_records", INTERROGATION_RECORDS, "shadow_apply", "shadow_records"),
        GraphOutput("repair_application", INTERROGATION_APPLICATION, "shadow_apply", "application_receipt"),
        GraphOutput("after_findings", INTERROGATION_FINDINGS, "shadow_checks", "finding_set"),
        GraphOutput("verification", INTERROGATION_VERIFICATION, "verify", "verification"),
    ),
    invariants=(
        "Questions remain declarative obligations and are never executable NodeSpecs.",
        "Typed ports use nominal equality; no edge performs an implicit conversion.",
        "Source records are not mutated in place.",
        "The after-check suite preserves the source selected-question identities.",
        "Standards references provide semantics but do not grant authority or truth.",
    ),
)

__all__ = [
    "INTERROGATION_APPLICATION",
    "INTERROGATION_CANDIDATES",
    "INTERROGATION_DESCRIPTORS",
    "INTERROGATION_FIELD_MAP",
    "INTERROGATION_FINDINGS",
    "INTERROGATION_NODE_DEFINITIONS",
    "INTERROGATION_NODE_PACK",
    "INTERROGATION_NODE_SPECS",
    "INTERROGATION_PLAN",
    "INTERROGATION_PROFILE",
    "INTERROGATION_PROGRAM",
    "INTERROGATION_RECORDS",
    "INTERROGATION_REGISTRY",
    "INTERROGATION_REPAIR_PROPOSAL",
    "INTERROGATION_VERIFICATION",
]
