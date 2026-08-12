# Architecture

Layout, and the conventions that keep it extensible. The repository now has a
domain-neutral compiler core and a browser adapter; the browser package no
longer defines the universal ontology.

```
solutiongraph/
├── model.py              semantic graph, strict node ABI, registry, frozen plan
├── compiler.py           graph validation, full admission, route compilation
├── discovery.py          descriptors, embedding spaces, handshake, snapshots, node packs
├── templates.py          semantic stages, reusable templates, refinement policies
├── template_authoring.py strict linear blueprint parser/compiler
├── template_library.py   original reference decompositions
├── template_library_extended.py  thirteen additional application templates
├── template_library_market.py    twelve additional cross-domain templates
├── tasking.py            task/case/oracle contracts + exact solution-pack closure
├── authoring.py          source-bound Python node definitions and candidate expansion
├── stdlib_nodes.py       dependency-free reusable text/data primitives
├── stdlib_pack.py        19-node/32-binding reference pack + executable graph
├── pack_library.py       canonical portable node-pack collection
├── benchmarking.py       controlled arms, runner, evidence model, offline report
├── benchmark_library.py  six bundled task/solution benchmark packs
├── benchmark_adapters.py strict external source-manifest normalization seams
├── search.py             prior, beam, sprout, exhaustive search + honest accounting
├── topology.py           explicit alternative DAG families + route search accounting
├── graph_experiments.py  fixed controls + comparable topology/route execution evidence
├── mutations.py          deterministic compiler-gated topology authoring operators
├── studies.py            paired uncertainty analysis over immutable run receipts
├── structured.py         composite and bounded-loop lowering to atomic DAGs
├── adaptive.py           planned/executed successive promotion + explicit early stopping
├── evidence.py           receipts, experiments, Pareto fronts, learned priors
├── ranking.py            reusable post-execution hard gates, Pareto flags, weighted projection
├── artifacts.py          replaceable content-addressed memory/file store boundary
├── durable.py            exact-identity completed-prefix checkpoints and resume
├── executor.py           strict frozen-plan recheck + reference Python runtime
├── streaming.py          finite event-time conformance adapter
├── saga.py               effectful action/compensation reference runner
├── compatibility.py      optional exact node/port operational sidecars
├── provenance.py         W3C PROV, OpenLineage, and SLSA projections
├── conformance.py        installed-wheel advanced mechanism gate
├── subprocess_runtime.py bounded lifecycle adapter with strict JSON/bytes ABI
├── ledger.py             content-chained, fsync-backed local receipt journal
├── experiments.py        receipt-producing plan/case/seed allocation
├── campaign.py           population lineage, hard budgets, and evaluator boundaries
├── harnessing.py         linked graph roles, authorities, flows, and feedback firewall
├── intelligence.py       task fingerprints, historical retrieval, starts, and effort
├── solutioning.py        staged task-to-history solutioning quality-of-life façade
├── task_categories.py    open 95-category multi-label DAG taxonomy
├── examples/             47 release-gated programs + modular control/mutation quickstart
├── reference_nodes.py    small executable node-pack demonstration
├── catalog.py            deterministic catalogue projection
├── scaffold.py           transactional coding-harness starter workspaces
└── schemas/              strict portable JSON Schema 2020-12 wire contracts

catalog/
├── index.json            content-addressed template/node-pack/benchmark index
├── templates/            544 atomic obligations across 31 varied templates
├── nodepacks/            six portable registries and discovery sidecars
├── harnesses/            strict linked-graph evaluation-harness artifact
├── arena/                52 cross-domain task-family contracts
└── benchmarks/           six task/solution packs and 24 immutable cases

browsergraph/
├── ports.py              BrowserPort protocol + Context — the seam
├── graph.py              Graph (DAG), run(), RunResult
├── manifest.py           portable node/context/intelligence manifest + thin wrapper
├── workbench.py          macro stages, atomic substeps, bindings, routes, receipts, validation
├── demo.py               6-macro / 21-substep / 154-definition / 634-candidate demonstration
├── schemas/              portable JSON Schemas
├── assets/               self-contained multi-view studio template
├── dimensions/           the axes a run varies along
│   ├── enums.py            Engine, Binary, Transport, Display, Stealth, LLMControl
│   ├── settings.py         Behavior, Identity, LLMConfig (structured axes)
│   ├── capability.py       per-engine metadata tables
│   ├── spec.py             Spec — one resolved point
│   └── rules.py            validate() — which points can run
├── nodes/                units of work
│   ├── base.py             Node, REGISTRY, register(), make()
│   ├── actions.py          navigate, click, type, wait_for, extract, scroll, screenshot
│   └── llm.py              llm_selector, llm_verify
├── drivers/              engine adapters implementing BrowserPort
│   ├── mock.py             reference implementation, no browser needed
│   ├── playwright_driver.py  playwright / patchright / camoufox
│   └── selenium_driver.py    selenium / selenium_uc / seleniumbase
├── heal.py               self-healing selectors + drift ledger
├── lint.py               static checks on a graph
├── combos.py             enumerate the valid space
├── sample.py             pairwise covering arrays
├── doctor.py             prerequisite checks
├── config.py             YAML/JSON -> Graph + Spec
├── server.py             HTTP adapter (stdlib)
└── cli.py                CLI adapter
```

## Universal representation pipeline

```text
task contract
  → task recognition + progressive fingerprint
  → historical retrieval + diverse effort portfolio + protected blind lanes
  → semantic template + task-specific ProgramGraph or TopologyFamily
  → deterministic structured-control lowering when required
  → registry capability negotiation + DiscoveryQuery
  → DiscoveryReceipt + closed-world RegistrySnapshot
  → AdmittedSpace + rejection reasons
  → BeliefModel-guided topology + prior / beam / seeded sprouts / adaptive allocation
  → content-addressed FrozenPlan
  → optional fixed-control versus explicit-topology experiment allocation
  → executor policy recheck + runtime adapter
  → exact checkpoint after each successful/skipped prefix
  → content-addressed node and graph-output artifacts
  → independent verifier
  → immutable RunReceipt
  → paired receipt study + promote/reject/continue recommendation when requested
  → W3C PROV / OpenLineage / SLSA projection when requested
  → CampaignDecision + preserved population lineage
  → new BeliefModel revision
  → immutable development-history snapshot when explicitly closed
```

Only the compiler crosses the definition-to-plan boundaries. Beliefs cannot
weaken contracts, and receipts cannot mutate history. See
`UNIVERSAL_NODE_GRAPH_SPEC.md` for the normative rules.

`ReferenceExecutor` reconstructs a supplied plan through the compiler before
running it and requires exact equality with the supplied program, registry,
admitted space, primary bindings, and frozen fallbacks. Its default Python
runtime is explicitly in-process and suitable for trusted fixtures, not hostile
code. `SubprocessPythonRuntime` is a bundled replacement that adds a fresh child,
strict portable-value protocol, wall-clock termination, reduced environment,
and optional POSIX limits while explicitly remaining a lifecycle—not
adversarial—boundary. `JsonlReceiptJournal` supplies immediate local durable
append and tamper evidence, while `FileCheckpointStore` supplies exact local
prefix resume. Production harnesses replace `RuntimeAdapter`,
`ArtifactStore`, checkpoint coordination, and receipt persistence while preserving the plan and receipt
boundary described in `EXECUTION_PROTOCOL.md`.

An LLM-generated improvement loop sits outside this pipeline. It stores each
compiled proposal as a `CandidateRecord`, preserves all parents in a
`CampaignLedger`, and binds the campaign to a `CampaignBudget` and immutable
`EvaluationBoundary`. These records are orchestration contracts, not a sandbox,
optimizer implementation, or second compiler. See `AUTORESEARCH_REVIEW.md`.

`TaskSolutionEngine` composes the recognition, initialization, compiler,
solver, evidence, and history-closure stages without merging their authority.
`GraphMutationEngine` produces complete child programs with explicit ancestry;
the ordinary compiler decides whether they are valid. `ExperimentStudyRunner`
reads immutable receipts and never edits experiment evidence. External
benchmark adapters normalize exact source manifests but perform no network,
credential, execution, submission, or certification action. See
`INTELLIGENT_SOLUTIONING.md`.

Discovery is deliberately asymmetric: registries may evolve continuously, but
a compiler consumes an immutable receipt-backed snapshot. Optional descriptions
and embeddings can improve nomination without ever changing executable truth.

## Why dimensions is a package and nodes is a package

Both started as single files. `dimensions.py` reached 274 lines carrying five
distinct concerns — the axes, their metadata, structured settings, the Spec,
and the rules — and DIMENSIONS.md proposes nine more axis groups. Splitting by
**concern** (not by individual dimension) means adding an axis touches one file:

- a new axis value → `enums.py`
- a new engine's install/binary facts → `capability.py`
- a new compatibility rule → `rules.py`

One file per dimension would be over-fragmentation: `Display` is six lines and
has no behaviour of its own.

The same reasoning applies to `nodes/`: grouped by **category** (actions, llm,
and later control/flow), not one file per node. A node is typically 20 lines;
a file each would be noise.

## The adapter layers, and the one-way rule

```
core        ports.py, graph.py, dimensions/     pure, no I/O
adapters    drivers/, server.py, cli.py         translate to/from the outside
extensions  nodes/, heal.py, lint.py            build on core, never on adapters
```

`solutiongraph` is the language-neutral compilation layer. `manifest.py` and
`workbench.py` are the earlier viewer-facing description/validation layers and
will migrate through explicit adapters rather than a breaking rewrite. Macro
stages group contiguous typed substeps but never become selectable route nodes.
They do not import an engine or execute a node. The HTML asset consumes serialized
workbench data and is therefore another adapter, not part of graph execution.

**Nothing in `core` imports from `adapters`.** A node that reached into
Playwright directly would work on one engine and silently break the rest, and
that is precisely the failure mode this design exists to prevent.

## Base classes: what is a Protocol, what is a class

Two different needs, deliberately handled differently.

**`BrowserPort` is a `Protocol`** (structural). A driver need not inherit
anything — it just implements twelve methods. That keeps adapters free of a
dependency on us and makes third-party drivers trivial. It is also why
`MockBrowser` inherits nothing.

**`Node` is a base class** (nominal). Nodes share real behaviour and defaults —
`name`, the `reads`/`writes`/`mutates`/`verifies` declarations, `__repr__` — so
inheritance carries weight rather than just a contract.

Rule of thumb used here: **Protocol when you want implementations you do not
control; base class when you want to give implementations something.**

## Extending

### A new node

```python
from browsergraph.nodes.base import Node, register
from browsergraph.ports import Context

@register                          # makes it available to config-driven graphs
class SelectOption(Node):
    kind = "select_option"         # the key used in YAML/JSON
    interacts = True               # so the linter knows it needs the element
    mutates = True                 # so BG003 requires verification afterwards

    def __init__(self, selector: str, value: str, name: str = ""):
        super().__init__(name)
        self.selector, self.value = selector, value

    def run(self, ctx: Context) -> Context:
        ctx.browser.click(self.selector)   # BrowserPort only — never an engine
        return ctx
```

Declaring `mutates`/`interacts`/`verifies` is not decoration: `lint.py` reasons
about them, so an undeclared node silently opts out of the checks.

### A new engine

1. Add the value to `Engine` in `dimensions/enums.py`
2. Add its rows to `ENGINE_FAMILY`, `ENGINE_BINARIES`, `ENGINE_IMPORT`,
   `ENGINE_REQUIREMENT` in `capability.py`
3. Add any incompatibility to `rules.py`
4. Write an adapter implementing `BrowserPort`
5. Route it in `drivers/build()`

**No node changes.** That is the test of whether the seam is holding.

`test_every_engine_declares_its_metadata` fails if step 2 is skipped, so the
tables cannot silently drift from the enum.

### A new dimension

Add to `enums.py` (or `settings.py` if structured), add a field to `Spec`, add
rules to `rules.py`. `combos.py` and `sample.py` pick it up automatically —
they read axes generically rather than naming them.

## Conventions

- **Stdlib-only core.** Engines are optional extras, so `pip install
  browsergraph` is small and the suite runs with no browser and no network.
- **Lazy adapter imports.** `drivers/build()` imports inside the function so a
  missing engine raises `DriverUnavailable` with the pip command, not an
  `ImportError` traceback.
- **Enums are `str`-valued**, so a Spec round-trips through JSON, YAML and env
  vars with no custom codec.
- **`Spec` is frozen.** Vary it with `dataclasses.replace`, which is what makes
  combination enumeration safe.
- **Failures are explicit.** Nodes call `ctx.fail()` rather than raising; the
  run stops and the reason is in the log. LLM nodes fail rather than guess.
- **Every check carries a fix.** `doctor` and `lint` findings include the
  remedy — a report you cannot act on is noise.

## Testing

`MockBrowser` is the reference `BrowserPort`, so graphs, nodes, linting,
healing and combination sweeps are all testable with no browser. The default
suite remains fast enough to run on every change, including compiler admission,
search accounting, and schema-contract tests for the universal core.

The load-bearing test is
`test_one_graph_runs_across_every_valid_combination` — one graph, every
runnable combination, no per-combination code. If the seam ever breaks, that
fails first.
