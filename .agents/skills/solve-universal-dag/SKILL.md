---
name: solve-universal-dag
description: Model and solve a real task with the UniversalSolver or extend the Universal DAG Arena. Use when a coding harness must turn a ticket, dataset, workflow, API process, Kaggle problem, data-quality job, browser task, entity-resolution task, numerical problem, or other DAG-solvable system into typed semantic slots; enumerate interchangeable nodes; run bounded route search; benchmark independent receipts; select a champion and diverse fallbacks; or add an honestly labeled executable fixture, template, or credentialed connector.
---

# Solve a universal DAG

Read `../../../UNIVERSAL_NODE_GRAPH_SPEC.md`,
`../../../TASK_AND_SOLUTION_PACK_PROTOCOL.md`,
`../../../EXECUTION_PROTOCOL.md`,
`../../../STRUCTURED_CONTROL_PROTOCOL.md`,
`../../../TOPOLOGY_SEARCH_PROTOCOL.md`, and
`../../../REAL_WORLD_EXAMPLES.md`. For generated-node campaigns, also use
`../design-autoresearch-campaign/SKILL.md`.

## Establish the task boundary

1. Write the input contract, output contract, independent acceptance oracle,
   exact case splits, hard constraints, objectives, budget, and authority policy
   before nodes.
2. Select an Arena task or semantic template with `solutiongraph arena list`
   and `solutiongraph templates list`. A template is a starting decomposition,
   not proof that a task is solved.
3. Label the implementation honestly:
   - `executable_fixture` for deterministic local evidence;
   - `template` when only reusable structure exists;
   - `credentialed_connector` when real execution needs an external system.
4. Never relabel a fixture lookup as USPS, Census, payment-provider, carrier,
   browser, cloud, or other authoritative production evidence.

## Build the semantic graph

1. Decompose the task into the smallest independently substitutable semantic
   obligations. Split macro steps into atomic slots until each slot has one
   testable purpose and one explicit success contract.
2. Declare nominal, versioned input/output types. Insert adapter nodes for
   conversions; never depend on implicit coercion.
3. Decide explicitly whether the task has one fixed topology or a closed
   `TopologyFamily`. Graph-shape alternatives are programs, not candidates.
4. Use activation rules plus optional-port merge nodes for conditionals. Use a
   child graph and finite `LoopPolicy` for iteration. Retain the lowering
   receipt before ordinary admission.
5. Keep task, slots, nodes, admission, search beliefs, frozen plans, runtime
   policy, verification, and evidence as separate layers.
6. Author at least two genuine implementation candidates for important slots
   when alternatives exist. Identity/pass-through candidates are legal only
   when skipping the obligation preserves its contract.
7. Add compatibility sidecars when ordering, event time, nullability, data
   classification, state, secrets, hardware, residency, or compensation matter.
8. Admit against a closed registry snapshot and resolve every compiler error.
   Search scores cannot admit a node or legalize an invalid route.

## Solve and learn

Run a bounded profile first:

```bash
solutiongraph solve <example-id> --profile quick
solutiongraph solve <example-id> --profile balanced --runtime subprocess
```

- `quick` tests the declared baseline and highest-prior suggestion.
- `balanced` learns from a prior round and allocates a bounded beam.
- `broad` adds seeded sprouts and repeated seeds.
- `exhaustive` has no implicit route cap and requires
  `--allow-exhaustive`; use it only after inspecting the admitted route count.

Treat learned weights as observational route-ordering evidence. Never put them
inside a program, node manifest, or frozen plan. Require independent verifier
acceptance and objective constraints before selecting a champion. Keep each
fallback as a separately benchmarked frozen route; do not splice untested
per-slot choices into a new fallback route.

For long local runs, use an exact checkpoint store and shared artifact store;
resume only the identity-matching prefix. For event-time tasks, test late and
too-late events plus retractions. For external effects, declare compensation
nodes and idempotency keys. Export standard provenance from the final receipt.

## Extend the Arena

When adding a local fixture:

1. Add ordinary deterministic functions to
   `solutiongraph/examples/arena_nodes.py`.
2. Wrap them with exact `NodeSpec` contracts in
   `solutiongraph/examples/tasks.py` and add candidates to the shared registry.
3. Define a typed `ProgramGraph`, at least one negative or baseline route when
   useful, at least one accepted route, and an independent verifier.
4. Add an `ArenaTask` in `solutiongraph/arena.py`, including stage families,
   acceptance signals, template, readiness, external requirements, and tags.
5. If a real authority is unavailable, test the connector seam with a fixture
   and state the missing production requirement in code, docs, and receipts.

## Gate the result

```bash
solutiongraph doctor
solutiongraph conformance
solutiongraph verify --catalog-root catalog
solutiongraph verify --runtime subprocess
solutiongraph arena run --profile quick
pytest -q
```

Regenerate `catalog/` after changing templates, registries, nodes, or Arena
entries. Report evaluated and total routes, unvisited space, search budgets,
accepted/rejected/failed receipts, Pareto routes, champion, fallback diversity,
lowering/topology/checkpoint identities, exact solution-pack closure, benchmark
claim scope, and remaining external or production gates. Synthetic fixture
success proves the framework mechanism only; it is not domain-level production
validation.
