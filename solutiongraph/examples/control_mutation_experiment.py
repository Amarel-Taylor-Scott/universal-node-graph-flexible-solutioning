"""A six-route control-versus-mutated-topology experiment configuration."""

from __future__ import annotations

from solutiongraph.authoring import build_python_registry, define_python_node
from solutiongraph.evidence import Objective
from solutiongraph.examples.control_mutation_cleaning_nodes import (
    clip_single_upper_outlier,
    preserve_values,
)
from solutiongraph.examples.control_mutation_estimation_nodes import (
    estimate_mean,
    estimate_median,
)
from solutiongraph.executor import CallableVerifier, ExecutionPolicy, VerificationResult
from solutiongraph.experiments import ExperimentCase
from solutiongraph.graph_experiments import GraphControl, GraphExperimentSpec
from solutiongraph.model import (
    Edge,
    GraphInput,
    GraphOutput,
    Idempotency,
    Port,
    ProgramGraph,
    SemanticSlot,
    ValueType,
)
from solutiongraph.search import SearchBudget, SearchMode
from solutiongraph.topology import TopologyFamily, TopologySearchBudget, TopologyVariant

PAYLOAD = ValueType("example.control-mutation-payload")
TASK = "Estimate the robust center of a small numeric payload."
SUCCESS = "The emitted estimate is independently compared with the declared fixture target."


def _definition(node_id, function, capabilities, description):
    return define_python_node(
        node_id=node_id,
        function=function,
        inputs=(Port("payload", PAYLOAD),),
        outputs=(Port("payload", PAYLOAD),),
        capabilities=capabilities,
        description=description,
        idempotency=Idempotency.IDEMPOTENT,
        preconditions=("The payload contains a nonempty numeric values list.",),
        postconditions=(
            "The returned payload preserves its source values or records a transform.",
        ),
        verifier="verifier.example.control-mutation",
    )


CONTROL_MUTATION_DEFINITIONS = (
    _definition(
        "example.control-mutation.clean-preserve",
        preserve_values,
        ("experiment.clean",),
        "Preserve values as an explicit identity cleaning route.",
    ),
    _definition(
        "example.control-mutation.clean-clip-outlier",
        clip_single_upper_outlier,
        ("experiment.clean",),
        "Clip one upper outlier before estimation.",
    ),
    _definition(
        "example.control-mutation.estimate-mean",
        estimate_mean,
        ("experiment.direct-estimate", "experiment.estimate"),
        "Estimate the payload center with the arithmetic mean.",
    ),
    _definition(
        "example.control-mutation.estimate-median",
        estimate_median,
        ("experiment.direct-estimate", "experiment.estimate"),
        "Estimate the payload center with the median.",
    ),
)

CONTROL_MUTATION_CANDIDATES = tuple(
    definition.candidate({}, candidate_id=f"candidate.{definition.spec.id}")
    for definition in CONTROL_MUTATION_DEFINITIONS
)

CONTROL_MUTATION_REGISTRY = build_python_registry(
    "example.control-mutation-registry",
    "1.0.0",
    CONTROL_MUTATION_DEFINITIONS,
    candidates=CONTROL_MUTATION_CANDIDATES,
)


def _slot(slot_id: str, capability: str, purpose: str) -> SemanticSlot:
    return SemanticSlot(
        slot_id,
        purpose,
        (Port("payload", PAYLOAD),),
        (Port("payload", PAYLOAD),),
        "The selected implementation emits a typed payload and records its method.",
        required_capabilities=(capability,),
    )


CONTROL_PROGRAM = ProgramGraph(
    "example.control-mutation-direct",
    "1.0.0",
    TASK,
    SUCCESS,
    (_slot("estimate", "experiment.direct-estimate", "Estimate without a cleaning stage."),),
    (),
    (GraphInput("payload", PAYLOAD, "estimate", "payload"),),
    (GraphOutput("result", PAYLOAD, "estimate", "payload"),),
)

MUTATED_PROGRAM = ProgramGraph(
    "example.control-mutation-staged",
    "1.0.0",
    TASK,
    SUCCESS,
    (
        _slot("clean", "experiment.clean", "Apply one explicit cleaning policy."),
        _slot("estimate", "experiment.estimate", "Estimate after the cleaning policy."),
    ),
    (Edge("clean", "payload", "estimate", "payload"),),
    (GraphInput("payload", PAYLOAD, "clean", "payload"),),
    (GraphOutput("result", PAYLOAD, "estimate", "payload"),),
)

CONTROL_MUTATION_FAMILY = TopologyFamily(
    "topology.example.control-mutation",
    "1.0.0",
    TASK,
    SUCCESS,
    (
        TopologyVariant(
            "topology.example.direct-control",
            "Direct control graph",
            CONTROL_PROGRAM,
            "Establish a one-node control topology.",
            tags=("topology.role.control",),
        ),
        TopologyVariant(
            "topology.example.cleaning-mutation",
            "Cleaning-stage mutation",
            MUTATED_PROGRAM,
            "Insert an independently replaceable cleaning obligation before estimation.",
            parent_variant_id="topology.example.direct-control",
            operators=("operator.insert-slot",),
            tags=("topology.role.mutation",),
        ),
    ),
)


def verify_estimate(context):
    result = context.outputs["result"]
    error = abs(float(result["estimate"]) - float(result["target"]))
    quality = 1.0 / (1.0 + error)
    accepted = error <= 0.5
    return VerificationResult(
        accepted,
        "estimate-within-tolerance" if accepted else "estimate-outside-tolerance",
        {"quality": quality},
        {"absolute_error": error, "methods": result.get("methods", [])},
    )


CONTROL_MUTATION_CASE = ExperimentCase(
    "case.control-mutation.numeric-outlier",
    {"payload": {"values": [1.0, 2.0, 3.0, 100.0], "target": 2.25}},
    CallableVerifier("verifier.example.control-mutation", verify_estimate),
)


def control_mutation_experiment_spec() -> GraphExperimentSpec:
    """Return a complete exhaustive experiment that executes all six routes."""

    return GraphExperimentSpec(
        id="experiment.control-vs-mutated-graph",
        family=CONTROL_MUTATION_FAMILY,
        registry=CONTROL_MUTATION_REGISTRY,
        cases=(CONTROL_MUTATION_CASE,),
        objectives=(
            Objective("quality", "maximize", weight=1.0, hard_minimum=0.5),
            Objective("latency_ms", "minimize", weight=0.05),
        ),
        control=GraphControl(
            "topology.example.direct-control",
            {"estimate": "candidate.example.control-mutation.estimate-mean"},
        ),
        search_budget=TopologySearchBudget(
            route_budget=SearchBudget(SearchMode.EXHAUSTIVE, result_limit=6),
            result_limit=6,
        ),
        policy=ExecutionPolicy(),
        require_complete_grid=True,
    )


__all__ = [
    "CONTROL_MUTATION_CANDIDATES",
    "CONTROL_MUTATION_CASE",
    "CONTROL_MUTATION_DEFINITIONS",
    "CONTROL_MUTATION_FAMILY",
    "CONTROL_MUTATION_REGISTRY",
    "CONTROL_PROGRAM",
    "MUTATED_PROGRAM",
    "control_mutation_experiment_spec",
    "verify_estimate",
]
