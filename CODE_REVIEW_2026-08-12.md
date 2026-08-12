# Repository-wide code review — 2026-08-12

## Outcome

The repository is a coherent developer-preview compiler and experiment system,
not merely a graph viewer. The strict separation among task meaning, semantic
graphs, executable nodes, compiler admission, search beliefs, frozen plans, and
receipts is its strongest design decision. The deterministic baseline passed
before review: full tests, the exact CI Ruff target, and whitespace checks.

This review inspected the domain-neutral `solutiongraph` core, the BrowserGraph
adapter, executable examples, schemas, tests, generated-catalog path, packaging,
CI entry points, and onboarding documentation. Passing fixture tests establish
mechanism conformance; they do not establish model efficacy or production
fitness.

## Findings and disposition

| Priority | Finding | Disposition |
|---|---|---|
| P1 | A `TopologyFamily` required equal task text and success contract but did not require equal external input/output contracts. Incomparable graphs could therefore enter one family. | **IMPLEMENTED:** exact endpoint-independent external port comparison; mismatches fail before admission/search. |
| P1 | Topology search could nominate and compile graph variants, but there was no single control-versus-mutation runtime experiment API. | **IMPLEMENTED:** `GraphExperimentSpec`, `GraphControl`, `GraphExperimentRunner`, cross-topology receipts, Pareto/ranking, control deltas, complete-grid proof, and a six-route example. |
| P1 | Topology ancestry accepted self-parenting or longer parent cycles. | **IMPLEMENTED:** self-parent and cycle validation with regression tests. |
| P2 | High-level experiment orchestration required repeated long parameter lists. | **IMPLEMENTED:** frozen `ExperimentBundle` and `GraphExperimentSpec` dataclasses preserve explicit identities while reducing pass-through arguments. |
| P2 | Evidence ranking was private logic embedded in the 1,000-line solver, preventing exact reuse by other experiment harnesses. | **IMPLEMENTED:** `solutiongraph.ranking` is a small evidence-only module used by the solver and graph experiments. |
| P2 | The shortest runnable experiment was buried in a long README; there was no role-based documentation map or examples index. | **IMPLEMENTED:** README five-minute paths, `DOCUMENTATION.md`, `examples/README.md`, and `GRAPH_EXPERIMENTS.md`. |
| P2 | `GETTING_STARTED.md` still described 54 routes and 21 controls after the repository had reached 120 routes and 44 controls. | **IMPLEMENTED:** corrected counts and added a documentation consistency test for release-facing numbers. |
| P2 | Topology search selects among explicit, fully declared graph variants; it does not synthesize arbitrary DAG structures from every node permutation. | **RECOMMENDED:** retain that safe boundary and add a typed mutation grammar incrementally (`insert-slot`, `remove-optional-slot`, `replace-subgraph`, `branch`, `join`) whose outputs must pass the ordinary compiler. Never imply that an unbounded DAG universe was searched. |
| P2 | Several modules are large enough that unrelated changes collide: `intelligence.py` (~2,700 lines), base/showcase example registries (~2,300 each), data-science fixtures (~1,600), `arena.py` (~1,300), and solver/executor/CLI/discovery (~1,000 each). | **RECOMMENDED:** staged concern-based extraction below; do not perform a wholesale rewrite while wire contracts are pre-1.0. |
| P3 | The distribution remains named `browsergraph` while the primary import is `solutiongraph`. | **DOCUMENTED:** retain compatibility until an announced pre-1.0 migration window. |
| P3 | In-process and subprocess runtimes are useful local mechanism adapters but are not hostile-code sandboxes or multi-tenant enforcement boundaries. | **DOCUMENTED / EXTERNAL GATE:** keep generated code and hidden evaluators in separate microVM or remote trust domains. |
| P3 | Broad fixtures demonstrate representational coverage, but they are not production connectors for every database, GIS authority, model provider, browser, or deployment platform. | **DOCUMENTED:** universality here means stable typed composition and extension seams; production adapters still require owner-specific integration and evidence. |

## Maintainability assessment

Dataclasses are already used extensively and appropriately for immutable wire
and control-plane values. The useful improvement is not “replace every function
argument with a bag.” It is to introduce cohesive configuration objects at
orchestration boundaries while leaving node ports explicit and typed. The new
`ExperimentBundle` and `GraphExperimentSpec` follow that rule.

Module size alone is not a defect. Large literal fixture catalogs are mostly a
navigation and merge-conflict problem; large files that mix policy, validation,
serialization, orchestration, and ranking are a coupling problem. The ranking
extraction addresses the latter immediately. The new control/mutation example
keeps node implementations, graph declarations, and the executable entry point
in separate files so future examples have a clean pattern to copy.

## Recommended staged splits

These are intentionally forward-compatible recommendations, not claims of
completed work:

1. Split `intelligence.py` behind its existing public re-exports into
   `fingerprints`, `history`, `similarity`, `retrieval`, `planning`, and
   `transfer` modules. Move no wire field during the split.
2. Move example fixture payloads into domain data modules and group executable
   functions by capability family. Preserve current import aliases and content
   digests deliberately; a source move changes implementation identity.
3. Split `cli.py` by command family while keeping one parser assembly module.
4. Extract executor validation, invocation, and receipt assembly only after
   characterization tests pin every failure code and checkpoint behavior.
5. Split Arena contract data from selection/query behavior.
6. Add a schema-version migration policy before any broad package layout or
   distribution-name change.

One file per tiny function would be over-fragmentation. Prefer one module per
stable capability or responsibility, typically with related candidate
implementations together.

## Experiment quality recommendations

The new API closes the mechanism gap for graph controls and mutations. Stronger
claims still require:

- multiple representative development/validation cases;
- candidate-inaccessible holdouts;
- repeated stochastic seeds and environment identity;
- paired/interleaved runtime measurements;
- fixed controls and equal resource accounting;
- failed and rejected receipts;
- best-so-far versus budget curves;
- real external datasets and independently owned evaluators;
- negative-transfer checks before history-informed starts become defaults.

The next graph-generation milestone should therefore be a small, versioned set
of typed mutation operators, not a free-form edge generator. Each generated
variant should record its parent, operator, parameters, derivation seed, and
rejection reason; compiler admission remains the sole compatibility authority.
That creates a reproducible "reasonable combinations" grid while keeping the
searched universe and every omission inspectable.

Use `IMPLEMENTED`, `MEASURED`, `PARTIAL`, `PLANNED`, `BLOCKED`, and
`RECOMMENDED` consistently. A green mechanism fixture is `IMPLEMENTED`; it is
not automatically `MEASURED` on a real population.
