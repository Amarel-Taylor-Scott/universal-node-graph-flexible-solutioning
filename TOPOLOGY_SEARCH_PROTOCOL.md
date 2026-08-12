# Topology Search Protocol

Status: reference protocol 0.1
Implementation: `solutiongraph.topology`

Node-route search answers “which implementation should fill each obligation?”
Topology search answers the separate question “which explicit graph shape
should define the obligations?” SolutionGraph never hides the second question
inside the first.

## Closed topology family

A `TopologyFamily` contains content-distinct `TopologyVariant` objects that
share the exact task, success contract, and named external input/output value
contracts. Internal endpoint slots may differ, but a variant cannot silently
rename or retype the family interface. Every variant contains a complete
`ProgramGraph`, rationale, optional prior log weight, optional parent variant,
and explicit operator labels such as `operator.insert-slot` or
`operator.add-verifier`. Parent lineage must be acyclic.

Operators describe lineage; they do not grant validity. `admit_all()` validates
and fully admits every variant against the registry independently. A generated
variant is therefore a new quarantined semantic artifact, not an unreviewed
patch to a currently running plan.

## Search-space accounting

For variants \(t\), the total route space is:

```text
total_cartesian_routes = sum(route_count_upper_bound(t))
```

`TopologySearchReport` separately records:

- total and searched topologies;
- evaluated node routes;
- constraint-eliminated routes;
- heuristic-skipped routes within searched topologies;
- every route belonging to an unsearched topology;
- unvisited routes, coverage, completeness, and proven optimality;
- each per-variant `SearchReport` and the globally ranked proposals.

A topology prior changes proposal order only. It cannot make a graph compile,
change authority, or overwrite measured evidence.

## Budgets

`TopologySearchBudget` has three independent controls:

- `route_budget`: ordinary prior/beam/sprout/exhaustive policy inside each DAG;
- `topology_limit`: number of graph variants to search;
- `global_evaluation_limit`: route evaluations shared across variants.

All limits are visible in the report. Exhaustive search remains opt-in and has
no hidden architectural cap. When every topology and every feasible route is
enumerated, `complete` and `optimality_proven` may be true; otherwise they are
false even if a strong proposal was found quickly.

## Compile and evaluate

A `TopologyProposal` binds a variant ID, exact program digest, and complete
slot-to-candidate assignment. `TopologySearchEngine.compile()` resolves the
variant and invokes the ordinary compiler. The resulting `FrozenPlan` is then
evaluated under the same verifier, cases, seeds, and resources as competing
topologies.

`GraphExperimentRunner` performs that evaluation as one typed operation. A
`GraphExperimentSpec` freezes the family, registry, cases, objectives, exact
control selection, search budget, runtime policy, beliefs, seeds, repetitions,
holdouts, and acceptance gate. It always executes the exact `GraphControl`,
groups searched plans by program, and returns cross-topology receipt aggregates,
control deltas, Pareto membership, and a transparent weighted projection.

When `require_complete_grid=True`, the runner requires uncapped exhaustive
route and topology search and fails if a result limit would hide an enumerated
plan from execution. `complete_grid_evaluated` requires both complete search
accounting and completion of every case/seed/repetition allocation. See
`GRAPH_EXPERIMENTS.md` and
`examples/control_vs_mutated_graph_experiment.py`.

Do not compare shapes with different success contracts, hidden preprocessing,
or unequal evaluator access. Use paired/interleaved measurements where runtime
noise matters, reserve holdouts, and report graph complexity alongside quality,
latency, cost, reliability, and resource metrics.

## Safe generation workflow

1. Start from one compiler-valid parent variant.
2. Apply a named topology operator under an explicit budget.
3. Record parent, operator, hypothesis, proposer, and new program digest.
4. Validate the complete graph and all boundaries.
5. Admit the full registry snapshot.
6. Execute through the fixed evaluator trust boundary.
7. Retain failures and dead ends in the population DAG.

This protocol supports topology mutation, evolutionary search, beam search,
MCTS, or model-generated proposals without granting any of them a path around
the compiler.
