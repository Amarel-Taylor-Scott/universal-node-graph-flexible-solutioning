# Control graphs, mutations, and route-grid experiments

`solutiongraph.graph_experiments` is the high-level experiment API for a common
engineering question:

> Given one fixed control graph and one or more explicit graph mutations, which
> compiler-valid graph-and-node route performs best under the same cases,
> seeds, verifier, runtime policy, and objectives?

It composes existing strict layers; it does not create a second compiler:

```text
TopologyFamily
  → validate identical task, success contract, and external port interface
  → admit every candidate against every slot in every graph
  → search each admitted route grid under an explicit budget
  → always include one exact fixed control plan
  → execute selected plans on identical cases × seeds × repetitions
  → preserve every receipt, rejection, metric, and failure
  → compare hard gates, Pareto membership, and an explicit weighted projection
```

The topology universe is explicit: the runner searches the variants declared in
one `TopologyFamily`. It does not claim to generate every possible DAG. A future
typed mutation generator can produce additional variants, but those variants
must retain their derivation metadata and pass the same family validation and
ordinary compiler admission before this runner will execute them.

## Run the six-route quickstart

From a fresh editable install:

```bash
python examples/control_vs_mutated_graph_experiment.py
```

The example is intentionally small and dependency-free:

- control topology: one estimation slot × two estimators = two routes;
- mutation topology: two cleaners × two estimators = four routes;
- complete declared grid: six routes;
- fixed control: direct arithmetic mean;
- mutation operator: `operator.insert-slot`;
- metrics: verifier quality and measured latency;
- outcome: all six plans execute, negative evidence is retained, and the
  outlier-clipping/mean mutation wins the declared weighted projection.

Its implementations and configuration are separated by concern:

- `solutiongraph/examples/control_mutation_cleaning_nodes.py`;
- `solutiongraph/examples/control_mutation_estimation_nodes.py`;
- `solutiongraph/examples/control_mutation_experiment.py`;
- `examples/control_vs_mutated_graph_experiment.py`.

That structure is the recommended pattern for new examples: implementation
functions do not own graph topology, experiment allocation, or acceptance.

## The dataclass API

```python
from solutiongraph import GraphExperimentRunner
from solutiongraph.examples.control_mutation_experiment import (
    control_mutation_experiment_spec,
)

spec = control_mutation_experiment_spec()
report = GraphExperimentRunner().run(spec)

print(report.complete_grid_evaluated)       # True
print(report.champion_plan_digest)
print(report.pareto_plan_digests)
for route in report.comparisons:
    print(route.role, route.acceptance_rate, route.objective_means)
```

`GraphExperimentSpec` carries the family, registry, cases, objectives, exact
control, topology/route search budget, execution policy, beliefs, seeds,
repetitions, holdouts, and acceptance gate as one frozen dataclass. It reduces
pass-through argument lists while retaining every underlying content identity.

`ExperimentBundle` provides the same quality-of-life improvement one layer
down for an already compiled plan/case experiment.

## Complete grid versus reasonable combinations

Use the search mode that matches the available budget:

| Mode | Use | Evidence boundary |
|---|---|---|
| prior | Fastest cold or learned starting route | One belief-ordered route per searched topology |
| beam | Bounded exploitation | Width, evaluations, skips, and unvisited routes are reported |
| sprout | Randomized exploration around anchors | Seed, attempts, duplicates, invalid samples, and mutation probability are reported |
| exhaustive | Every feasible route in the declared family | No hidden evaluation cap; result limits must still expose every plan that should execute |

Set `require_complete_grid=True` only with uncapped exhaustive topology and
route search. The runner fails if a `result_limit` would enumerate the grid but
hide plans from execution. `complete_grid_evaluated` becomes true only when the
search is complete and every selected plan completed its entire case/seed/
repetition allocation.

For a large grid, leave `require_complete_grid=False` and use beam, sprouts,
history-informed beliefs, or an adaptive supervisor. The report keeps exact
Cartesian, constrained, skipped, selected, executed, and unvisited counts.

## Comparability and mutation rules

Every `TopologyVariant` must preserve:

- the exact task and success contract;
- the same named external input and output value contracts;
- an acyclic parent lineage;
- a complete compiler-valid `ProgramGraph`;
- explicit mutation operators and a content-distinct program digest.

Variants may have different internal slots and implementations. They may not
silently rename an output, change its type, expose a different task, or form a
cyclic ancestry graph. Those conditions now fail before search.

The exact control is a `GraphControl(variant_id, selection)`. It always runs,
even if a bounded search would not have proposed it. Other routes in the same
topology are labeled `control-topology-alternative`; routes from other variants
are labeled `mutation`.

## Metrics and “best”

Acceptance and objective hard limits are eligibility gates. Eligible routes
receive:

- raw means and variances;
- deltas from the exact control;
- Pareto membership;
- a transparent weighted score over min/max-normalized eligible observations.

The weighted score is explicitly a user-selected projection, not objective
truth. `rank_route_aggregates()` is the reusable evidence-only implementation
used by both `UniversalSolver` and graph experiments.

`declared_grid_optimality_proven=True` means every feasible route in the exact
declared family and registry snapshot was executed and an eligible champion was
selected under those declared objectives. It is not a claim about unpublished
nodes, other topology families, future data, or production performance.

## Production boundaries

The quickstart is a transparent mechanism fixture. For consequential use:

- freeze a real `TaskContract`, immutable cases, and independent oracle;
- keep holdouts candidate-inaccessible and outside generated-code trust domains;
- use paired seeds/repetitions and controlled environments;
- replace the trusted local runtime with an enforcing adapter;
- publish the machine-readable graph experiment report and raw receipts;
- preserve failed mutations and negative transfer instead of deleting them.

See `TOPOLOGY_SEARCH_PROTOCOL.md`, `BENCHMARK_PROTOCOL.md`,
`EXECUTION_PROTOCOL.md`, and `READINESS.md` for the normative boundaries.
