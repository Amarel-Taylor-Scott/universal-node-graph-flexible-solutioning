---
name: execute-solution-graph
description: Implement, extend, run, or audit Universal Node Graph frozen-plan execution. Use when an agent must add a runtime adapter, artifact codec/store, retries, frozen fallbacks, circuit breaking, independent verifier, executable domain example, notebook, or receipt-producing experiment without weakening compiler validity or authority boundaries.
---

# Execute a frozen solution graph

Read `../../../EXECUTION_PROTOCOL.md` before changing runtime behavior. Read
`../author-node-pack/SKILL.md` before adding implementations and
`../benchmark-solution-graph/SKILL.md` before comparing routes.

## Establish the immutable boundary

1. Compile the complete registry snapshot and preserve `AdmittedSpace.digest`.
2. Freeze primary candidates and ordered same-slot fallbacks with exact versions,
   implementation digests, parameters, edges, and admission identity.
3. Reconstruct and compare the plan before invoking any entrypoint.
4. Keep runtime policy separate from the semantic program and require both to
   authorize every runtime, effect, and permission.

## Add a runtime or codec

1. Implement the narrow `RuntimeAdapter` or `ArtifactStore` protocol.
2. Declare actual isolation; never call in-process execution a sandbox.
3. Verify executable content identity using the runtime's native artifact form.
4. Accept and return only declared named ports and parameters.
5. Classify stable failures and retry only explicit retryable, idempotent work.
6. Content-address successful outputs and retain attempt receipts.
7. Add tamper, authority, failure, retry, fallback, and cleanup tests.

## Add an executable domain example

1. Start from a task contract and independent oracle.
2. Refine a catalog template into exact domain value types.
3. Add at least two genuine candidates to multiple slots where useful.
4. Use real importable entrypoints and inspected implementation digests.
5. Compile every route before execution; never assemble it dynamically in a node.
6. Execute a fixed control and alternatives with real fixture outcomes.
7. Preserve rejected and failed runs alongside accepted runs.
8. Add a runnable notebook that calls the public executor/example API.

## Verify

```bash
solutiongraph doctor
solutiongraph examples list
pytest tests/test_solutiongraph_execution.py -q
pytest tests/test_solutiongraph*.py -q
ruff check solutiongraph tests/test_solutiongraph*.py
```

Reject the change if it performs search inside execution, activates an unfrozen
fallback, retries a non-idempotent node, infers authority, silently serializes
arbitrary objects, lets a producer self-accept consequential output, discards a
negative receipt, or presents a mechanism fixture as production evidence.
