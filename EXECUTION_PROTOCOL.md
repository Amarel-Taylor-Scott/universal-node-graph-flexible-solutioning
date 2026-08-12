# Frozen-plan execution protocol

Status: research preview 0.2

Reference implementation: `solutiongraph.executor`

Artifact boundary: `solutiongraph.artifacts`
Lifecycle subprocess adapter: `solutiongraph.subprocess_runtime`
Durable local receipt journal: `solutiongraph.ledger`
Durable local checkpoint protocol: `solutiongraph.durable`
Structured lowering: `solutiongraph.structured`
Finite stream conformance adapter: `solutiongraph.streaming`
Compensation runner: `solutiongraph.saga`
Provenance projections: `solutiongraph.provenance`
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
→ data-dependent activation check for each slot
→ runtime invocation through named typed ports
→ exact completed-prefix checkpoint after each successful/skipped slot
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

`SubprocessPythonRuntime` is the bundled lifecycle-isolation adapter. It starts
one fresh Python child per invocation, uses an explicit collision-safe
JSON/bytes codec, captures child stdout/stderr away from the protocol stream,
enforces a parent wall-clock timeout, reduces inherited environment variables,
and can apply POSIX CPU/address-space limits. Its exact adapter/isolation
identity participates in the environment digest and node receipt. It does not
restrict filesystem, network, devices, system calls, or the current operating-
system user's authority, so it MUST NOT be labeled a hostile-code sandbox.

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
also not a sufficient security boundary, and neither is a plain container.
Hidden evaluator assets must not be candidate-readable, candidate code must
never write the evaluator, and the candidate and evaluator should execute in
separate microVM or remote trust domains. The reference executor does not
implement that isolation; it only exposes the replacement seam.

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

`ExecutionCheckpoint` turns that reconstruction seam into an exact local
resume protocol. The reference executor persists every successful or skipped
topological prefix with its node receipt and artifact-backed outputs. Resume is
allowed only when plan, program, registry, admitted-space, input, environment,
task-case, and seed identities all match. Completed slots must be an exact
prefix of the current topological order. Any mismatch or missing artifact fails
closed; completed work is never guessed.

`FileArtifactStore` verifies content digests on read and durably publishes new
blobs with atomic replace plus file/directory `fsync`. `FileCheckpointStore`
uses the same write discipline. A failed run retains
its checkpoint; a successful or verifier-rejected completion clears it by
default. This is local durability, not a distributed lease, fencing protocol,
or exactly-once sink guarantee.

`JsonlReceiptJournal` provides a separate durable local evidence boundary. It
validates every `RunReceipt`, rejects duplicate identities, assigns a monotonic
sequence, chains each record digest to its predecessor, appends under a file
lock, flushes, and calls `fsync` before acknowledging success. Every read and
append revalidates the complete chain. The journal detects mutation and
truncation; it does not prevent a filesystem-authorized actor from replacing
or deleting the entire file and is not an authenticated multi-tenant ledger.

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

Data-dependent slots are checked before invocation. Inactive slots emit
`outcome="skipped"`; they do not invoke a runtime or synthesize output. The
compiler requires conditional outputs to meet at optional merge ports before a
required consumer or graph output, preventing an inactive producer from
silently creating a missing required value.

For multi-step external effects, `SagaRunner` provides a reference
compensation protocol. Every action and compensation is an ordinary `NodeSpec`
whose digest, runtime, effects, permissions, and state ports are rechecked.
Completed actions are compensated in reverse order with explicit idempotency
keys and append-only attempt receipts. Effectful steps must use unique keys. If
an action declares an `idempotency_key` parameter, the runner supplies the
saga-owned key and rejects a caller override; compensation receives the same
key with a `:compensation` suffix. This lets an external adapter forward the
receipt identity to a provider's deduplication boundary. Compensation is not atomic rollback;
uncompensated steps remain visible in the result.

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

`solutiongraph provenance export` projects one `RunReceipt` into W3C PROV JSON,
an OpenLineage run event with custom facets, or an in-toto Statement carrying
SLSA provenance v1. These are interoperable projections of the receipt; they
do not replace the source receipt or claim that an external lineage backend
accepted the event.

## 8. Experiment execution

`ExperimentRunner` executes the Cartesian allocation declared by
`ExperimentDesign`: task cases × frozen plans × seeds × repetitions. It does not
change admission or select a winner while runs are underway. It returns an
immutable `EvidenceLedger`, per-plan aggregates, Pareto plan identities, and
explicit holdout receipt IDs.

`ExperimentBundle` carries the design, plans, cases, program, registry,
admitted space, execution policy, and belief revision as one frozen dataclass.
It is a quality-of-life boundary, not a merged identity: bundle validation still
checks every digest and exact mapping before execution.

`GraphExperimentRunner` composes topology search and ordinary experiment
execution. It always includes one exact `GraphControl`, groups plans by their
content-distinct program, executes common cases/seeds/repetitions, and compares
receipt-derived evidence across control-topology alternatives and mutations.
The runner never mutates a graph or searches inside node execution.

Use the existing successive-halving and early-stopping primitives only through
an explicit multi-fidelity supervisor. `run_successive_halving` invokes the
supplied evaluator at each resource rung and records every observation,
promotion, finalist, and consumed resource unit. Never compare incomplete resource rungs
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

The 47 bundled programs and six numbered notebooks demonstrate this sequence with
standard-library nodes. They are executable teaching fixtures, not production
benchmark claims for web scraping, OCR, imaging, entity resolution, or machine
learning.

## 10. Reference-release gate

The reference executor layer is conforming when:

- a tampered program, registry, admitted space, plan, binding, fallback, or
  implementation is rejected;
- undeclared runtime, permission, or effect authority is rejected;
- node outputs have content identities and can be recovered from the store;
- retries and fallbacks are bounded and visible;
- verification is independent and may reject a technically completed route;
- every attempt produces a valid receipt;
- all 47 examples compile against their declared cross-domain registries and execute
  without optional packages or network access.

The `solutiongraph conformance` gate additionally executes conditional control,
structured lowering, alternative-topology search, event-time streaming, exact
local resume, saga compensation, successive-halving evaluation, and provenance
export from an installed wheel.

Production readiness additionally requires an enforcing isolated runtime,
distributed crash-resumable scheduling with leases/fencing, authenticated remote evidence storage,
secrets and tenancy, operational monitoring, and held-out real-domain
benchmarks. The bundled subprocess adapter and local journal deliberately close
the lifecycle and evidence-format seams without claiming those stronger gates.
