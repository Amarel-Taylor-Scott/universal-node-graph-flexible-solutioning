---
name: author-structured-workflow
description: Author, validate, lower, execute, or repair SolutionGraph control flow using data-dependent branches, explicit merges, composite child graphs, bounded loops, maps, reductions, barriers, checkpoints, or saga compensation. Use when a coding harness must add nontrivial control/state semantics while keeping the executable layer a compiler-valid DAG with typed boundaries and inspectable receipts.
---

# Author a structured workflow

Read `../../../STRUCTURED_CONTROL_PROTOCOL.md`,
`../../../EXECUTION_PROTOCOL.md`, and
`../../../PROVENANCE_AND_RESUME.md`. For event-time work also read
`../../../STREAMING_PROTOCOL.md`.

## Choose one explicit construct

- Conditional: create a decision slot, activation rules on arms, and an
  explicit merge with optional arm inputs.
- Composite: place a child `ProgramGraph` in a closed `SubgraphCatalog`; make
  parent and child boundary names/types/effects match exactly.
- Loop: use a child graph, positive finite `LoopPolicy.max_iterations`, and a
  complete one-to-one output→input feedback map. Carry invariant values in the
  state envelope.
- Map/reduce/barrier: author an ordinary node contract whose runtime explicitly
  owns ordering, fan-out/fan-in, failure, and checkpoint behavior; this release
  does not lower these kinds automatically.
- External effects: provide idempotency keys and explicit compensation nodes;
  use `SagaRunner` only as the reference compensation adapter.

## Validate and lower

1. Run ordinary program validation before lowering.
2. Resolve child references by exact ID or digest in one catalog.
3. Call `StructuredCompiler.lower()` and retain `LoweringReceipt`.
4. Inspect namespaced slots and edges; then run ordinary full registry
   admission on the lowered program.
5. Reject conditional outputs that feed unguarded required inputs or required
   graph outputs. Do not fill absent values with executor guesses.

## Execute and recover

Freeze the exact lowered plan. Execute under explicit runtime/effect/permission
policy and an independent verifier. For local resume, share the artifact and
checkpoint stores and require identity equality; do not reuse a checkpoint
after any program, plan, environment, case, input, or seed change.

Test the inactive branch, maximum loop bound, early-inactive pass-through,
failure during an effect, reverse compensation, and resume without repeating
the completed prefix. Export provenance from the final receipt.

## Gate

```bash
solutiongraph conformance
pytest -q tests/test_solutiongraph_universal_control.py
ruff check solutiongraph tests/test_solutiongraph*.py
```

State whether evidence comes from the local conformance adapter or a production
orchestrator. Do not call local checkpointing distributed exactly-once behavior,
or reference compensation an atomic transaction.
