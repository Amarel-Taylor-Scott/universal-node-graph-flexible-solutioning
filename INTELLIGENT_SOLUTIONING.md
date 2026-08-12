# Intelligent task solutioning and graph improvement

This guide connects the repository's task contracts, compiler, history-aware
starting points, graph mutations, execution evidence, and controlled studies
into one inspectable lifecycle. The implementation is domain-neutral: the same
interfaces can represent data cleaning, geotemporal enrichment, ML pipelines,
document processing, service workflows, synthetic-data generation, and LLM
evaluation harnesses.

The key boundary is unchanged: learned history and generated mutations may
propose work, but only the compiler can admit a route and only the independent
task oracle can accept an execution.

## Five-minute paths

Inspect the recognized task, admitted route space, effort policy, historical
recommendations, and protected history-blind lanes without executing anything:

```bash
solutiongraph solutioning inspect data-cleanup --effort 1
```

Run the same lifecycle through compilation, execution, verification, ranking,
and negative-transfer analysis:

```bash
solutiongraph solutioning run data-cleanup --effort 1
```

Run a complete cold-start, immutable memory update, warm-start, graph mutation,
control experiment, and paired study:

```bash
python examples/intelligent_solutioning_study.py
```

Inspect the available claim-safe external benchmark profiles and normalize an
explicit Kaggle-style source manifest:

```bash
solutiongraph benchmarks adapters
python examples/external_benchmark_adapter.py
```

All four commands use local mechanism fixtures. They do not download private
data, call a model provider, submit competition entries, or claim production
performance.

## One lifecycle, replaceable seams

```text
TaskContract + immutable cases + independent TaskOracle
  -> validate exact task/program/registry/case identity
  -> recognize task family and progressive fingerprint attributes
  -> retrieve similar positive and failure-preserving historical episodes
  -> build diverse starts under an explicit effort policy
       - historical routes
       - category/topic/shape priors
       - canonical baseline
       - randomized sprouts
       - protected history-blind controls
  -> compiler admission against one closed registry snapshot
  -> compile each proposal to a content-addressed FrozenPlan
  -> execute common cases/seeds under one runtime policy
  -> independently verify and retain every accepted or rejected RunReceipt
  -> apply hard gates, Pareto ranking, and explicit weighted projections
  -> assess matched-budget negative transfer
  -> close development evidence into a new immutable HistoricalMemory snapshot

Explicit parent topology
  -> apply a typed deterministic mutation operator
  -> preserve the external task interface and mutation ancestry
  -> compiler-validate the complete child graph
  -> enter an explicit TopologyFamily
  -> run fixed-control versus mutation route grids
  -> analyze paired receipts with uncertainty and practical-effect thresholds
  -> promote, reject, or continue collecting evidence
```

The lifecycle deliberately avoids a single opaque `optimize()` function. Each
stage is public so a team can inspect it, replace it, or put a stronger runtime,
retrieval service, scheduler, artifact store, or evaluator behind the same
typed boundary.

## The quality-of-life API

`TaskSolutionRequest` is a frozen dataclass that carries the values that would
otherwise be passed through many orchestration functions:

- exact `TaskContract`, `ProgramGraph`, and `Registry`;
- executable cases and verifier identities;
- `ExecutionPolicy` and optional durable receipt sink;
- immutable historical memory and optional precomputed fingerprint;
- effort and retrieval policies;
- fixed baseline selection, holdout case IDs, and random seed.

Use the one-call path when defaults are sufficient:

```python
from solutiongraph import solve_task
from solutiongraph.examples import example_solution_request

request = example_solution_request("data-cleanup", effort=1)
result = solve_task(request)

print(result.status)
print(result.champion.digest if result.champion else "no accepted champion")
print(result.negative_transfer.status)
```

Use the staged engine when a human, agent, or service must inspect or intervene:

```python
from solutiongraph import TaskSolutionEngine

engine = TaskSolutionEngine()
problems = engine.validate(request)
fingerprint = engine.recognize(request)
recommendations = engine.retrieve(request, fingerprint=fingerprint)
binding = engine.bind(request)
starting_plans = engine.route(request, binding)
result = engine.execute(request, binding)
evidence = engine.get_evidence(result)
memory_update = engine.learn(request, result)
```

A binding is content-bound to the request and admitted space. Reusing it after
the task, oracle, graph, registry, cases, policy, or history changes fails
closed. `learn()` returns a new memory snapshot and update receipt; it never
mutates or silently replaces the input history.

## Intelligent starts without history lock-in

The task fingerprint can combine progressively available attributes. Useful
families include:

- task operation: clean, validate, enrich, merge, transform, predict, rank,
  generate, extract, evaluate, red-team, deploy, or recover;
- learning shape: regression, classification, ranking, forecasting,
  clustering, anomaly detection, reinforcement learning, or generation;
- data subject and modality: finance, health, people, events, geography,
  documents, images, audio, source code, telemetry, or mixed multimodal input;
- table shape: rows, columns, sparse/dense ratios, cardinality, missingness,
  duplicate rates, type entropy, and train/serve schema drift;
- statistical shape: skew, tails, modes, imbalance, outliers, stationarity,
  autocorrelation, feature dependence, collinearity, and target leakage risk;
- operational shape: latency and cost budget, data classification, residency,
  allowed effects, secrets, hardware, freshness, and reliability objectives;
- graph shape: number of obligations, branching/join patterns, compatible
  candidate counts, and route-space size;
- semantic representations: task-description embeddings, schema embeddings,
  aggregate column-profile embeddings, and failure-cluster embeddings.

Exact compiler and oracle identities are not embedding features to be guessed.
They remain strict versioned references. Aggregate fingerprints should avoid
raw sensitive records, record their extraction version, and distinguish
missing attributes from measured zeroes.

Historical retrieval is advisory. Every effort policy retains one or more
history-blind lanes, and randomized sprouts explore alternatives around
compatible anchors. Negative-transfer analysis compares historical and blind
lanes under matched budgets so a stale prior can be detected rather than
quietly becoming the default forever.

## Typed graph mutations

`GraphMutationEngine` provides five conservative reference operators:

| Operator | Purpose |
|---|---|
| `InsertSlotAfterInput` | Add a typed obligation immediately after one public input |
| `InsertSlotOnEdge` | Split one exact internal edge with a new obligation |
| `InsertSlotBeforeOutput` | Add a typed obligation before one public output |
| `RemoveLinearSlot` | Ablate one unambiguous internal pass-through position |
| `ReplaceSlotContract` | Refine an obligation while preserving every exact port |

Each operation is deterministic and serializable. The engine emits a
`MutationReceipt` containing parent and child identities, operator parameters,
rationale, hypothesis, proposer, tags, and interface-preservation evidence.
The child must be content-distinct, keep the public input/output contract, have
acyclic lineage, and pass ordinary compiler validation.

```python
from solutiongraph import GraphMutationEngine, InsertSlotAfterInput, MutationContext

mutation = GraphMutationEngine().apply(
    parent_variant,
    InsertSlotAfterInput(new_slot, "payload", "payload", "payload"),
    MutationContext(
        child_variant_id="topology.example.cleaned",
        child_title="Clean before estimation",
        child_program_id="program.example.cleaned",
        child_program_version="1.0.0",
        rationale="Make the cleaning policy independently substitutable.",
        hypothesis="A robust cleaner improves held-out acceptance.",
        proposer_id="proposer.example",
    ),
)
```

These operators cover common linear edits. Branches, joins, maps, bounded
loops, and composite subgraphs should use the structured-control lowering
protocol or new narrowly typed mutation operators. A mutation is never edited
into a running plan and never inherits node admission from its parent.

## Control, mutation, and paired studies

`GraphExperimentRunner` executes an exact fixed control and declared topology/
route alternatives on common cases, seeds, repetitions, objectives, verifier,
and runtime policy. `ExperimentStudyRunner` consumes the resulting immutable
ledger; it does not rerun or rewrite evidence.

A `StudyDesign` freezes:

- the exact control and candidate plan digests;
- task cases and objectives;
- pairing keys (case, seed, input, verifier, and environment identity);
- confidence level and deterministic bootstrap seed;
- minimum paired observations;
- practical-effect thresholds;
- acceptance non-inferiority and minimum acceptance-rate gates.

The study reports raw and direction-oriented deltas, bootstrap intervals,
win/tie rates, unmatched receipts, hard-objective status, and a conservative
`study.promote`, `study.reject`, or `study.continue` verdict. A promotion is
evidence for the declared sample and boundary, not a universal superiority
claim. Consequential promotion still needs inaccessible holdouts, an enforcing
runtime, operational review, and rollback evidence.

## External benchmark adapters

External benchmark ecosystems differ in licenses, data access, harnesses,
metrics, leakage rules, submission formats, and claims. The reference adapters
normalize those facts into a strict task/case bundle without pretending to be
the external authority.

Bundled profiles cover:

- Kaggle and MLE-bench competition-style ML tasks;
- SkillsBench matched skill/no-skill agent evaluations;
- SWE-bench repository repair tasks;
- BrowserGym browser-agent environments;
- DueCare-style linked LLM evaluation and feedback boundaries.

Every request must declare exact source ID, version, URI, claim scope, licensed
case identities, evaluator identity, and profile-specific metadata. Adapters do
not fetch datasets, resolve credentials, build containers, execute systems,
submit results, or certify a public score. Those are separate authorized
runtime nodes and evaluation services.

## Mapping common engineering work into graphs

The reusable unit is an independently verifiable obligation, not a fashionable
tool name. Typical families map as follows:

| Family | Example obligations and replaceable strategies |
|---|---|
| Data cleaning | profile -> normalize types -> deduplicate -> impute -> detect outliers -> validate contract |
| Data verification | schema -> cross-field rules -> authority lookup -> reconciliation -> quarantine -> evidence report |
| Data enrichment | entity resolution -> licensed lookup -> confidence -> provenance -> conflict policy -> quality gate |
| GIS enrichment | parse address -> geocode -> boundary join -> Census/reference validation -> spatial confidence -> policy filter |
| Time enrichment | normalize timezone -> calendar/holiday join -> event-time window -> seasonality -> freshness -> leakage check |
| Time + GIS | temporal normalization -> spatial join -> place-time event lookup -> confidence fusion -> privacy -> validation |
| Feature engineering | leakage-safe split -> transformations -> encoding -> selection -> stability -> feature contract |
| Supervised ML | baseline -> candidate families -> tuning -> calibration -> slice tests -> release/rollback |
| Unsupervised ML | representation -> distance policy -> cluster/anomaly alternatives -> stability -> interpretation -> review |
| Synthetic data | source policy -> generator alternatives -> constraint repair -> fidelity -> privacy -> downstream utility gate |
| Reinforcement learning | environment contract -> behavior data -> reward/evaluator -> policy alternatives -> off-policy safety -> promotion |
| Documents/media | ingest -> classify -> extract/transform -> ground -> render -> structural and visual verification |
| Backend systems | validate request -> authorize -> transact -> emit event -> reconcile -> compensate/observe |
| Frontend systems | build -> static/a11y checks -> journey alternatives -> visual regression -> performance -> release gate |
| LLM evaluation | scenarios -> SUT graph -> atomic graders -> blinded panel -> failure clusters -> human promotion |
| LLM red teaming | threat taxonomy -> adversarial generation -> policy-constrained execution -> independent judging -> severity -> remediation replay |

The checked-in Arena, templates, engineering showcase, and data-science pack
already provide executable mechanism fixtures for these families. New
production integrations should add source-bound node packs and task-specific
cases rather than fork the compiler.

## Extension points

High-value extensions can remain independent packages:

- a governed feature/profile extractor that emits versioned fingerprint facts;
- a vector or hybrid historical index that returns signed retrieval receipts;
- Bayesian, evolutionary, bandit, or multi-fidelity supervisors that emit the
  existing search and allocation records;
- narrowly typed branch/join/subgraph mutation operators;
- enforcing Kubernetes, microVM, Wasm, or remote execution adapters;
- warehouse, GIS, model-provider, browser, ticketing, and observability node packs;
- real benchmark importers with license checks and separately owned evaluators;
- experiment registries, dashboards, and approval workflows built from the
  portable reports and immutable receipts.

An extension must not bypass task identity, registry snapshots, compiler
admission, frozen-plan reconstruction, independent verification, or evidence
retention. Unknown metadata belongs in versioned extensions; executable truth
belongs in the strict core contracts.

## Evidence and claim boundaries

The repository's bundled data is intentionally small and transparent. It proves
that the mechanisms compile, execute, reject controls, retain evidence, and
round-trip through strict schemas. It does not prove that one node, graph,
optimizer, or historical prior is best on real workloads.

Before making an external claim:

1. freeze the exact task, source, cases, oracle, program family, registry, and
   runtime environment;
2. separate development cases from candidate-inaccessible holdouts;
3. run matched control and candidate allocations with enough independent pairs;
4. retain failures, unmatched observations, abstentions, and negative transfer;
5. publish the claim scope, raw receipts, uncertainty, cost, coverage, and known
   limitations;
6. require human approval and a rollback path for consequential deployment.

See `TAEDRI_TASK_FINGERPRINT_HISTORY_INFORMED_SEARCH.md`,
`GRAPH_EXPERIMENTS.md`, `BENCHMARK_PROTOCOL.md`,
`TASK_AND_SOLUTION_PACK_PROTOCOL.md`, and `EXECUTION_PROTOCOL.md` for the
normative details.
