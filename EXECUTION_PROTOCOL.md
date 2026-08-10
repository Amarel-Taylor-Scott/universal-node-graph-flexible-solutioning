# Frozen-plan execution protocol

Status: research preview 0.1

Reference implementation: `solutiongraph.executor`

Artifact boundary: `solutiongraph.artifacts`
Experiment boundary: `solutiongraph.experiments`
Campaign boundary: `solutiongraph.campaign`

This protocol defines the smallest honest bridge from a compiler-valid route to
runtime evidence. It is intentionally runtime-neutral. The bundled Python
adapter is a conformance implementation for trusted local examples; it is not a
security sandbox and does not make the repository production-ready by itself.

## 1. Required lifecycle

```text
ProgramGraph + RegistrySnapshot
→ full Compiler.admit()
→ AdmittedSpace digest
→ Compiler.compile(primary choices + ordered fallbacks)
→ FrozenPlan digest
→ executor policy recheck
→ runtime invocation through named typed ports
→ content-addressed output artifacts
→ independent verification
→ immutable RunReceipt
→ EvidenceLedger / experiment analysis
```

The executor MUST NOT search, infer a missing candidate, coerce a type, grant
authority, or mutate a frozen plan. Search and learning may propose a different
plan only after the current receipt exists.

## 2. Execution bundle and replay boundary

A reference execution receives all of these immutable objects:

- the exact `ProgramGraph`;
- the exact `Registry` or receipt-backed registry snapshot;
- the complete `AdmittedSpace` and its digest;
- the exact `FrozenPlan`, including primary and fallback bindings;
- named external inputs;
- a separate `ExecutionPolicy`;
- a task-case identity and independent `Verifier`;
- a runtime registry and artifact store supplied by the harness.

Before invoking a node, `ReferenceExecutor` reconstructs the plan with the
compiler and requires exact equality. A changed program, registry, admission
decision, candidate, parameter, implementation digest, fallback, priority, or
topology therefore fails before execution.

The verifier exposes its own implementation digest, recorded separately from
its human-readable identifier. A production runner must also bind dataset
split, evaluator environment, and hardware identities through an
`EvaluationBoundary`; a verifier name by itself is not a reproducibility or
trust boundary.

## 3. Callable ABI used by the reference Python adapter

For `runtime="python"`, an entrypoint uses `module:callable` syntax. Named node
input ports and resolved candidate parameters become keyword arguments:

```python
def normalize_records(records: list[dict], strategy: str) -> list[dict]:
    ...
```

- A node with one output returns that value directly.
- A node with multiple outputs returns a mapping containing exactly every
  declared output-port name.
- A node with no outputs returns `None` or an empty mapping.
- `many` and `stream` outputs are represented by lists or tuples in the
  reference adapter. A production streaming adapter should replace this codec.
- Portable reference values are JSON, text, or bytes. Runtime-specific objects
  require an explicit codec and nominal value type.

The adapter hashes inspected callable source and compares it with the frozen
implementation digest. Other runtimes may verify OCI manifests, binaries,
Wasm components, packages, model weights, prompts, or remote deployment
attestations through their own content-identity mechanism.

## 4. Authority and isolation

Compiler admission and executor policy are both mandatory. A selected node's
runtime, effects, and permissions must be allowed by the program and again by
the execution policy. The optimizer cannot weaken either boundary.

`PythonRuntime` advertises `isolation="in_process"`. It is appropriate only for
trusted fixtures and local development. A production harness should set
`allow_in_process_python=False` and register a subprocess, container, Wasm,
remote-job, browser, model, human, or other isolation adapter.

A production runtime adapter must additionally enforce:

- wall-clock and resource limits outside the node process;
- filesystem, network, secret, device, and model authority;
- dependency locks and environment identity;
- stdout/stderr and structured log capture;
- cancellation and cleanup;
- effect observation where feasible;
- tenant and data-retention policy;
- secret references without receipt disclosure.

Declared policy without an enforcing isolation mechanism is evidence about
intent, not proof of containment.

For LLM-generated or otherwise untrusted candidate code, a plain subprocess is
also not a sufficient security boundary. Hidden evaluator assets must not be
candidate-readable, candidate code must never write the evaluator, and the
candidate and evaluator should execute in separate container, microVM, or
remote trust domains as required by the threat model. The reference executor
does not implement that isolation; it only exposes the replacement seam.

## 5. Artifacts and checkpoints

Every successful node output is stored through `ArtifactStore`. The reference
stores provide:

- deterministic JSON serialization with non-finite values rejected;
- direct byte/text storage;
- SHA-256 content identity;
- deduplicated memory or atomic local-file writes;
- artifact digests on node and graph-output receipts.

`MemoryArtifactStore` is for tests and short notebooks.
`FileArtifactStore` is a local content-addressed checkpoint primitive. Object
stores, databases, OCI registries, and distributed caches should implement the
same four-method protocol.

Artifacts do not implicitly become node inputs. A later slot consumes a value
through a declared edge; a resume or distributed runtime may reconstruct that
value through an explicit codec using the recorded artifact.

## 6. Failure, retry, fallback, and circuit semantics

Nodes may raise `NodeExecutionFailure(code, message, retryable=...)`.

1. Every attempt emits a `NodeRunReceipt`.
2. Retry occurs only when the failure explicitly says it is retryable, the node
   is not non-idempotent, and the policy's attempt bound remains.
3. After attempts are exhausted, the executor may try the next same-slot
   fallback frozen into the plan.
4. A fallback is independently admitted, content-addressed, parameter-bound,
   ordered, and checked against n-ary route constraints at compile time.
5. The candidate-scoped circuit breaker can block repeatedly failing choices;
   its mutable state is outside the semantic program and plan.
6. A quality-oracle rejection does not silently activate a fallback inside the
   completed attempt. It becomes evidence for a newly proposed and compiled
   route unless the task contract explicitly defines a structured recovery
   graph.

Generic exceptions are recorded as `runtime.exception` and are not retried by
the reference adapter.

## 7. Verification and receipts

The task verifier receives exact inputs, outputs, output artifacts, plan,
program, node receipts, task-case ID, and seed. It returns:

- independent acceptance;
- an outcome label;
- measured objective values;
- structured explanatory details.

The final `RunReceipt` includes program, plan, admitted-space, input,
environment, implementation, artifact, verifier, route-assignment, attempt,
timing, fallback, retry, failure, and belief-revision evidence. Failed and
rejected runs remain append-only observations.

## 8. Experiment execution

`ExperimentRunner` executes the Cartesian allocation declared by
`ExperimentDesign`: task cases × frozen plans × seeds × repetitions. It does not
change admission or select a winner while runs are underway. It returns an
immutable `EvidenceLedger`, per-plan aggregates, Pareto plan identities, and
explicit holdout receipt IDs.

Use the existing successive-halving and early-stopping primitives only through
an explicit multi-fidelity supervisor. Never compare incomplete resource rungs
as equal or let a holdout result update the proposing belief model.

## 9. Harness extension sequence

An LLM coding harness adding a domain should:

1. instantiate and refine a semantic template;
2. author strict importable node contracts and real fixtures;
3. publish a registry/node pack with exact implementation digests;
4. run full admission and inspect every rejection;
5. compile primary and diverse fallback routes;
6. register only runtimes and authority actually available;
7. execute representative task cases with independent verifiers;
8. retain artifacts, failures, receipts, seeds, and environment identities;
9. compare baseline and alternatives under declared objectives;
10. add holdouts before making optimization claims.

The five notebooks in `notebooks/` demonstrate this sequence with standard-
library nodes. They are executable teaching fixtures, not production benchmark
claims for web scraping, OCR, imaging, entity resolution, or machine learning.

## 10. Reference-release gate

The reference executor layer is conforming when:

- a tampered program, registry, admitted space, plan, binding, fallback, or
  implementation is rejected;
- undeclared runtime, permission, or effect authority is rejected;
- node outputs have content identities and can be recovered from the store;
- retries and fallbacks are bounded and visible;
- verification is independent and may reject a technically completed route;
- every attempt produces a valid receipt;
- all six examples compile against the same cross-domain registry and execute
  without optional packages or network access.

Production readiness additionally requires an enforcing isolated runtime,
durable append-only ledger, robust codecs/checkpoint resume, secrets and
tenancy, operational monitoring, and held-out real-domain benchmarks.
