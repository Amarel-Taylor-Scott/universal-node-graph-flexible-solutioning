"""browsergraph — composable browser automation as nodes over a dimension space.

Any engine (playwright / patchright / selenium / cdp / mock) × any binary,
transport, display, stealth and behaviour setting, driven by graphs of reusable
nodes. Action nodes talk to a `BrowserPort`, never to an engine directly, so a
node written once runs on every engine.
"""
from browsergraph.contracts import Contract, ContractError, contract_of
from browsergraph.dimensions import (
    Behavior,
    Binary,
    Display,
    Engine,
    Identity,
    LLMConfig,
    LLMControl,
    Spec,
    Stealth,
    Transport,
    is_valid,
    validate,
)
from browsergraph.graph import Edge, EdgeKind, Graph, RunResult, run
from browsergraph.manifest import (
    NodeDefinition,
    NodeManifest,
    ParameterSpec,
    PortSpec,
    described_node,
    manifest_of,
)
from browsergraph.ports import BrowserPort, Context, Element, PageState
from browsergraph.workbench import (
    WORKBENCH_VIEWS,
    ExecutionReceipt,
    FeedbackDefinition,
    MacroStageDefinition,
    NodeCandidate,
    OptimizationDecision,
    OptimizationObjective,
    OptimizationProfile,
    PlaneDefinition,
    SolutionDefinition,
    StageDefinition,
    WorkbenchDefinition,
    candidate_id,
    expand_node_candidates,
    workbench_schema,
)

__version__ = "0.2.0"
__all__ = [
    "Behavior", "Binary", "Display", "Engine", "Identity", "LLMConfig",
    "LLMControl", "Spec", "Stealth", "Transport", "is_valid", "validate",
    "Graph", "RunResult", "run", "Edge", "EdgeKind",
    "BrowserPort", "Context", "Element", "PageState",
    "Contract", "ContractError", "contract_of",
    "PortSpec", "ParameterSpec", "NodeManifest", "NodeDefinition",
    "manifest_of", "described_node",
    "NodeCandidate", "FeedbackDefinition", "ExecutionReceipt",
    "OptimizationObjective", "OptimizationDecision",
    "OptimizationProfile", "MacroStageDefinition", "StageDefinition", "PlaneDefinition",
    "SolutionDefinition", "WorkbenchDefinition", "candidate_id",
    "expand_node_candidates", "workbench_schema", "WORKBENCH_VIEWS",
]
