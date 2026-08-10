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
├── template_library.py   six cross-domain reference decompositions
├── search.py             prior, beam, sprout, exhaustive search + honest accounting
├── adaptive.py           successive promotion and explicit early stopping
├── evidence.py           receipts, experiments, Pareto fronts, learned priors
├── reference_nodes.py    small executable node-pack demonstration
├── catalog.py            deterministic catalogue projection
└── schemas/              strict portable JSON Schema 2020-12 wire contracts

catalog/
├── index.json            content-addressed template/node-pack index
├── templates/            98 atomic obligations across six unrelated domains
└── nodepacks/            portable reference registry and discovery sidecars

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
  → semantic template + task-specific ProgramGraph
  → registry capability negotiation + DiscoveryQuery
  → DiscoveryReceipt + closed-world RegistrySnapshot
  → AdmittedSpace + rejection reasons
  → BeliefModel-guided prior / beam / seeded sprouts / adaptive allocation
  → content-addressed FrozenPlan
  → executor adapter
  → immutable RunReceipt
  → new BeliefModel revision
```

Only the compiler crosses the definition-to-plan boundaries. Beliefs cannot
weaken contracts, and receipts cannot mutate history. See
`UNIVERSAL_NODE_GRAPH_SPEC.md` for the normative rules.

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
