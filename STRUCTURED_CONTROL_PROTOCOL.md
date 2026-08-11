# Structured Control Protocol

Status: reference protocol 0.1
Implementations: `solutiongraph.model`, `solutiongraph.compiler`,
`solutiongraph.structured`, `solutiongraph.executor`

SolutionGraph keeps the executable graph acyclic while representing control
flow explicitly. Control is part of the semantic program, never an optimizer
side effect or an invisible behavior inside a provider node.

## Control constructs

| Construct | Representation | Reference behavior |
|---|---|---|
| Conditional | `branch` decision slot plus activated arm slots | The decision output enables matching arms; inactive arms emit `skipped` receipts |
| Merge | Ordinary node with optional arm inputs | Re-establishes one required value after conditional execution |
| Composite | Slot with `subgraph_ref` | Child graph is deterministically inlined with namespaced slot IDs |
| Bounded loop | Slot with `subgraph_ref` plus `LoopPolicy` | Child graph is unrolled into a finite DAG with explicit feedback edges |
| Map | Semantic `map` slot | An admitted runtime node owns element scheduling and output ordering |
| Reduce | Semantic `reduce` slot | An admitted runtime node owns aggregation semantics |
| Barrier | Semantic `barrier` slot | An admitted runtime node owns synchronization semantics |

Map, reduce, and barrier are ordinary typed obligations in this release. They
are not silently expanded by `StructuredCompiler`; a future lowering protocol
must be versioned separately.

## Conditional invariants

An activated slot declares `activation_slot`, `activation_port`, and
`activation_values` together. The source must exist, the port must be a real
output, and the activation dependency participates in topological ordering.

The compiler rejects two unsafe shapes:

- a conditional producer feeding an unconditional required input;
- a conditional producer directly supplying a required graph output.

A required consumer is legal when its guard implies the producer's guard. A
normal branch join uses optional ports on an explicit merge node. This makes
the absence of an inactive arm a typed fact instead of a runtime surprise.

## Composite lowering

The parent slot and child graph must expose exactly matching port names and
compatible nominal types. The child cannot claim effects that the parent slot
did not allow. Lowering rewrites external edges and graph boundaries to the
child's declared input/output bindings, prefixes every child slot, preserves
groups, and validates the resulting graph with the ordinary compiler.

## Bounded-loop lowering

Every loop requires a positive `max_iterations` and a one-to-one feedback map
from child graph outputs to every child graph input. Each iteration becomes a
namespaced copy. The first copy receives parent inputs; later copies receive
the previous copy's mapped outputs. Parent outputs come from the last copy.

There is no hidden loop-invariant capture. Carry invariant values in the state
envelope. Early convergence is modeled by an explicit active flag and safe
pass-through behavior inside the body, so later unrolled copies do not perform
effects after convergence.

## Receipt and replay boundary

`LoweringReceipt` binds the source program, lowered program, subgraph catalog,
every expansion, child digest, expanded slot IDs, and iteration count. Search,
compilation, and execution operate on the lowered program. A harness should
retain both source and lowered digests so a result remains understandable at
the authoring and execution levels.

## Minimal gate

```bash
solutiongraph conformance
pytest -q tests/test_solutiongraph_universal_control.py
```

Conformance requires one conditional arm to run, the other to be receipted as
skipped, and a three-iteration loop to lower into three ordinary executable
slots. Production orchestrators still need cancellation, distributed state,
leases, and effect fencing around these semantics.
