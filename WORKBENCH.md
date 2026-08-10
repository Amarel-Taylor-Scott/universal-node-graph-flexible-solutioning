# Hierarchical linear solution studio

The workbench represents an ordered solution in one unambiguous picture:

- each **macro stage** is one conceptual phase and visible submatrix;
- each macro stage expands into typed, ordered **atomic substeps**;
- each substep is one left-to-right selection column;
- every **atomic candidate** for that substep is stacked vertically in its column;
- a **route** selects one candidate in every substep column;
- a line joins consecutive selected candidates;
- contracts, filters, metrics, and optimization describe or compare the graph;
  they never become macro stages or execution substeps.

The bundled example contains 6 macro stages, 21 atomic substeps, 154 reusable
node definitions, 634 fully bound atomic candidates, and five complete routes.
The 21 substep candidate counts are
`81 × 22 × 23 × 15 × 15 × 38 × 29 × 35 × 25 × 36 × 29 × 33 × 24 × 68 × 25 × 19 × 27 × 21 × 23 × 26 × 20`,
producing 1,610,460,741,842,511,132,974,400,000,000 primary routes before
fallback ordering is considered.

Here, “every candidate” means every implementation admitted to the loaded node
registry, with every declared finite parameter choice expanded. Registry
discovery can add packages or generated nodes later; completeness validation
then guarantees that none of those eligible candidates is silently omitted
from its substep. Open-ended values such as a URL or document payload belong on
typed input ports. A configuration axis must be enumerated or deliberately
discretized before it can define a finite searchable candidate set.

```bash
browsergraph workbench -o browsergraph-workbench.html
```

The result is self-contained, works offline, and can load another version-2
workbench JSON file without a server. The same canonical data can be projected
five ways without changing its semantics.

## The seven separate concepts

| Concept | Canonical meaning | What it is not |
|---|---|---|
| Macro stage | One conceptual phase containing a contiguous submatrix | A route selection column |
| Atomic substep (`StageDefinition`) | One typed, independently selectable requirement; one left-to-right column | A broad phase containing several hidden actions |
| Node definition | Reusable implementation metadata and factory contract | A particular model/browser/parameter selection |
| Atomic candidate | One node definition with concrete parameter bindings | An unexpanded family of choices |
| Route | Exactly one primary candidate per atomic substep, plus optional fallbacks | A macro stage or optimization algorithm |
| Feedback channel | A typed receipt signal with producer, scope, consumer, and action | A task stage or an unlabeled backward edge |
| Optimizer | Evaluates and proposes routes under objectives and constraints | Part of the task’s ordered execution semantics |

This distinction fixes an important ambiguity. A definition such as
`Browser target` with five controllers, six binaries, and two display modes is
not one visible choice. `expand_node_candidates()` materializes all 60 concrete
bindings, such as:

```text
Browser adapter · Playwright · Firefox · headless
Browser adapter · Selenium · Chrome · headed
Browser adapter · CDP · Edge · headless
…57 more
```

Likewise, the schema-constrained LLM parser expands six model families and three
strategies into 18 visible candidates. The viewer shows every materialized
candidate in the corresponding substep by default; filtering changes what is
visible, not what exists in the registry.

## When a macro stage must split

A macro stage is deliberately not selectable. It must split into another
atomic substep whenever any of the following can vary independently:

- the required capability or implementation family;
- the input/output contract;
- whether the operation can be skipped with a typed pass-through;
- the failure, fallback, retry, or checkpoint policy;
- the permission or possible external effect;
- the evidence needed to prove success;
- the cost, latency, quality, or resource measurement;
- the optimizer's ability to replace the operation without replacing its
  neighbors.

```text
Task
└── Macro stage (conceptual phase / submatrix)
    └── Atomic substep (typed selection column)
        └── Node definition
            └── Atomic parameter binding
```

The hierarchy may recurse through a composite candidate that references a
child graph, but every compiled execution plan is flattened into one explicit,
ordered list of typed substeps before admission and execution.

## Wire model version 2

The portable workbench shape is standardized by
[`browsergraph/schemas/workbench.schema.json`](browsergraph/schemas/workbench.schema.json).

```text
WorkbenchDefinition
├── nodes[]       reusable NodeManifest definitions
├── candidates[]  concrete NodeCandidate parameter bindings
├── macro_stages[] conceptual phases listing contiguous substep IDs
├── stages[]      atomic ordered substep columns containing candidate IDs
├── solutions[]   routes mapping each substep ID to one candidate ID
├── feedback_channels[]  typed receipts flowing outside the execution line
├── optimization_profiles[]  data-driven objectives for ranking eligible choices
├── receipts[]     immutable route execution and verification evidence
└── optimization_decisions[] inspectable substep/macro-stage/route traces
```

The older `planes` name is accepted when loading version-1 data and remains a
Python compatibility alias. In version 2, `StageDefinition` is the atomic
selection unit (a substep), while `MacroStageDefinition` groups contiguous
substeps. “Plane” remains too easy to confuse with dimensions, policy,
contracts, and optimization.

## Candidate completeness

For atomic substep `s`, definition registry `N`, and concrete candidate registry `B`:

```text
C(s) = [b in B where b.node_id resolves to n in N
               and b binds valid parameter values for n
               and required_capabilities(s) ⊆ capabilities(n)
               and input_type(s) matches an input port of n
               and output_type(s) matches an output port of n]
```

`StageDefinition.with_discovered_candidates()` materializes this complete set.
`WorkbenchDefinition.validate()` rejects:

- unknown or invalid node definitions;
- unbound, unknown, or out-of-range candidate parameters;
- missing compatible candidates;
- candidates placed in technically incompatible substeps;
- macro stages that omit, duplicate, reorder, or mis-own substeps;
- routes that omit or add substeps;
- route choices and fallbacks outside the substep candidate set;
- disconnected output and input ports between consecutive substeps;
- incompatible declared output/input types between adjacent substep boundaries;
- invalid substep and solution identities or empty success contracts;
- fallbacks attached to unknown substeps;
- duplicate metrics inside an optimization profile.

There is no top-k limit in candidate expansion or discovery.

## Feedback and optimization contracts

Feedback is standardized without being inserted into the task route.
`FeedbackDefinition` declares:

| Field | Meaning |
|---|---|
| `signal` | Typed receipt or decision being observed |
| `scope` | Candidate, edge, atomic substep, macro stage, route, task, or registry attribution |
| `producer` / `consumer` | Component emitting and component learning or acting on the signal |
| `action` | Permitted response such as reject, retry, fallback, update a prior, constrain, rank, or invalidate |
| `required` | Whether absence of the channel prevents route admission or acceptance |

`OptimizationProfile` separately declares a strategy and weighted metric
objectives. Each `OptimizationObjective` has an explicit metric, direction
(`maximize` or `minimize`), and non-negative weight. Hard eligibility checks—
contracts, permissions, effects, and runtime requirements—run before scoring.
An objective may rank eligible candidates; it cannot legalize an ineligible
candidate or silently alter an atomic substep.

`ExecutionReceipt` records outcome, acceptance, verifier, route metrics,
atomic-substep outcomes, macro-stage aggregate outcomes, provenance, evidence
source, timestamps, and failure classification. `OptimizationDecision` records
its atomic-substep, macro-stage, or route scope,
profile, selected candidate mapping, eligible/rejected counts, score, objective
values, normalized contributions, alternatives, evidence snapshot, and reason.
Both are optional on initial design data and become durable evidence when real
runs or optimizer decisions exist.

## Canonical node definition

`NodeManifest` describes the reusable implementation. Its wire representation
is standardized by
[`browsergraph/schemas/node-manifest.schema.json`](browsergraph/schemas/node-manifest.schema.json).

| Field group | Meaning |
|---|---|
| `id`, `kind`, `name`, `version`, `description` | Stable implementation identity and documentation |
| `roles`, `capabilities`, `tags` | Atomic-substep eligibility and discovery taxonomy |
| `inputs`, `outputs` | Technical/semantic types, units, required ports, and schemas |
| `parameters` | Bindable dimensions and allowed values |
| `effects`, `permissions` | Possible state changes and required authority |
| `dependencies`, `resources`, `runtime` | Installation and execution requirements |
| `context`, `intelligence` | Declared context scopes, brokered access, micro-model mode, and authority to propose changes |
| `metrics` | Measured or predicted implementation priors |
| `source`, `docs` | Code and documentation locations |

Existing BrowserGraph nodes automatically receive an inferred manifest through
`manifest_of(node)`, `node.manifest()`, or the CLI:

```bash
browsergraph nodes --json
```

Authors can attach the complete definition without changing execution:

```python
from browsergraph import ParameterSpec, PortSpec, described_node
from browsergraph.nodes.base import Node, register


@register
@described_node(
    id="example.normalize_address",
    name="USPS-aware address normalizer",
    description="Normalizes an address and preserves field-level evidence.",
    roles=("transform",),
    capabilities=("canonicalize", "address_normalization"),
    inputs=(PortSpec("address", "RawAddress", semantic_type="postal-address"),),
    outputs=(PortSpec("address", "CanonicalAddress", semantic_type="postal-address"),),
    parameters=(
        ParameterSpec(
            "strategy", "string", default="conservative",
            choices=("conservative", "aggressive"),
        ),
    ),
    permissions=("network:usps",),
    dependencies=("usps-adapter>=1",),
    resources={"cpu": "small", "memory_mb": 128},
    runtime={"deterministic": True, "sandbox": "process"},
    source="my_package.address:NormalizeAddress",
    docs="docs/nodes/normalize-address.md",
)
class NormalizeAddress(Node):
    kind = "normalize_address"
    reads = ("address",)
    writes = ("address",)
    needs_browser = False

    def __init__(self, strategy: str = "conservative"):
        super().__init__()
        self.strategy = strategy

    def run(self, ctx):
        return ctx
```

`NodeDefinition` remains the thin executable wrapper around a manifest and
factory. `NodeCandidate` is deliberately separate: it describes one concrete
choice in the graph search space.

```python
from browsergraph import (
    NodeCandidate,
    NodeDefinition,
    candidate_id,
    manifest_of,
)

definition = NodeDefinition(manifest_of(NormalizeAddress), NormalizeAddress)
candidate = NodeCandidate(
    id=candidate_id(definition.manifest.id, {"strategy": "aggressive"}),
    node_id=definition.manifest.id,
    parameters={"strategy": "aggressive"},
)
node = definition.build(**candidate.parameters)
```

## Constructing a complete hierarchical stage matrix

```python
from browsergraph import (
    MacroStageDefinition,
    SolutionDefinition,
    StageDefinition,
    WorkbenchDefinition,
    expand_node_candidates,
)

nodes = tuple(node_manifests)
candidates = expand_node_candidates(nodes)

stages = (
    StageDefinition(
        id="load.resolve",
        macro_stage_id="load",
        name="Resolve input",
        input_type="TaskReference",
        output_type="ResolvedReference",
        success="the source identity is explicit",
        required_capabilities=("load.resolve",),
    ),
    StageDefinition(
        id="load.retrieve",
        macro_stage_id="load",
        name="Retrieve input",
        input_type="ResolvedReference",
        output_type="InputHandle",
        success="the authorized input is readable and versioned",
        required_capabilities=("load.retrieve",),
    ),
    StageDefinition(
        id="extract.parse",
        macro_stage_id="extract",
        name="Extract fields",
        input_type="InputHandle",
        output_type="CandidateResult",
        success="the requested schema is populated with evidence",
        required_capabilities=("extract.parse",),
    ),
    StageDefinition(
        id="extract.verify",
        macro_stage_id="extract",
        name="Verify fields",
        input_type="CandidateResult",
        output_type="VerifiedOutcome",
        success="independent field and source validation passes",
        required_capabilities=("extract.verify",),
    ),
)

macro_stages = (
    MacroStageDefinition(
        id="load", name="Load document", input_type="TaskReference",
        output_type="InputHandle", success="input is readable and versioned",
        substeps=("load.resolve", "load.retrieve"),
    ),
    MacroStageDefinition(
        id="extract", name="Extract and verify", input_type="InputHandle",
        output_type="VerifiedOutcome", success="verified fields are available",
        substeps=("extract.parse", "extract.verify"),
    ),
)

stages = tuple(
    stage.with_discovered_candidates(nodes, candidates)
    for stage in stages
)

solution = SolutionDefinition(
    id="deterministic",
    name="Deterministic route",
    route={
        "load.resolve": "example.local_reference",
        "load.retrieve": "example.local_file",
        "extract.parse": "example.regex_extractor",
        "extract.verify": "example.schema_verifier",
    },
)

workbench = WorkbenchDefinition(
    title="Document extraction stage matrix",
    task="Extract a declared schema from an unknown document",
    success="independent field and source validation passes",
    nodes=nodes,
    candidates=candidates,
    macro_stages=macro_stages,
    stages=stages,
    solutions=(solution,),
).assert_valid()

workbench.write_html("document-stage-matrix.html")
```

## Five synchronized projections

The studio keeps the execution topology literal while offering different views
for different questions:

| Projection | Question it answers | Structure |
|---|---|---|
| Hierarchical submatrices | What can perform each atomic part of every macro step? | Six macro-stage groups contain 21 ordered substep columns; definitions group every vertically stacked atomic binding; enabled solutions appear as connected route rows |
| Path network | What does the complete adjacent choice structure look like? | Macro-stage bands contain every substep and atomic candidate; faint lines show every runnable adjacent possibility or a deterministic sample of compatible routes; incompatible edges are excluded and counted |
| Compare routes | How do complete solutions differ? | One solution per row and one substep per column, with macro context, baseline differences, Pareto status, evidence, and fallbacks |
| Build step by step | Which candidate should this route select now? | A 21-substep rail, every current-substep candidate, explicit policy blocks, objective contribution trace, macro-stage and route-wide proposals, and live validation |
| Feedback and optimization | How does the system learn without corrupting the task topology? | The route remains linear while a route evidence summary and typed receipts flow through a separate observe → attribute → diagnose → propose → gate → learn control plane |

Across the projections:

- clicking any candidate replaces only that atomic substep in a separate Custom route;
- every selected route remains exactly one candidate per ordered substep;
- search, role, and permission filters never alter the underlying registry;
- candidate families make the definition-versus-binding distinction visible;
- policy-ineligible candidates remain visible and explain why they are blocked;
- the builder validates macro ownership, substep membership, adjacent technical ports, permissions,
  effects, and deterministic-runtime requirements;
- recommendations normalize quality, latency, and cost priors only within the
  current substep and active eligibility policy;
- recommendation explanations expose eligible count, top alternatives,
  normalized score, and each objective's contribution;
- macro-stage proposals optimize only the active submatrix and preserve all
  other substep selections;
- route-wide proposals choose one eligible candidate per substep and then
  revalidate the complete route;
- complete workbench JSON and the current route can be copied directly, and
  normalized JSON can be downloaded without a server;
- the inspector keeps bindings separate from definition metadata, ports,
  permissions, effects, dependencies, runtime, and evidence.

Optimization consumes route receipts and updates route metrics or rankings. It
does not change what a macro stage or atomic substep means and does not appear
as an extra substep unless the task itself explicitly requires an optimization
action.

## CLI

Generate the default explorer and normalized version-2 data:

```bash
browsergraph workbench \
  --export-data examples/workbench-demo.json \
  -o examples/universal-graph-workbench.html
```

Render custom data:

```bash
browsergraph workbench my-workbench.json -o my-workbench.html
```

Open a specific projection first:

```bash
browsergraph workbench --view builder -o route-builder.html
browsergraph workbench --view network -o path-network.html
browsergraph workbench --view compare -o route-comparison.html
browsergraph workbench --view feedback -o feedback-loop.html
```

Generate the full multi-file suite and normalized data:

```bash
browsergraph workbench --suite examples/workbench-suite
```

The suite writes `index.html`, `path-network.html`, `compare-routes.html`,
`build-route.html`, `feedback-loop.html`, and `workbench.json`. Each HTML file
still contains every projection; its filename simply chooses the first view.
