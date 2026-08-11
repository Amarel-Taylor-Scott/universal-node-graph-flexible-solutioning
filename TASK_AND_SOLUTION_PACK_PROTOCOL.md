# Task and solution-pack protocol

Status: normative for SolutionGraph model version `0.1`.

This protocol separates the problem to solve from every proposed way of solving
it. A `TaskContract` fixes meaning and acceptance. A semantic `ProgramGraph`
decomposes that meaning into obligations. A `Registry` supplies implementations.
A `SolutionPackManifest` content-addresses the exact closure used to reproduce
or compare solutions.

The separation is deliberate:

```text
TaskContract (what success means)
        |
        +-- TaskCaseSpec[] (immutable inputs and split identities)
        +-- TaskOracle (who decides acceptance)
        +-- ProgramGraph[] (alternative semantic decompositions)
        +-- Registry[] / NodePackManifest[] (implementation universes)
        +-- FrozenPlan[] (declared controls or baselines)
        +-- BenchmarkSuite[] (experiment allocation)
        |
SolutionPackManifest (digest closure over all of the above)
```

A task can have many programs, registries, plans, and benchmark suites without
changing its required inputs, outputs, success contract, or oracle.

## 1. Task contract

Every executable or benchmarked solution MUST have one versioned
`TaskContract`. It contains:

- a stable namespaced identifier and version;
- human-readable title and implementation-neutral intent;
- exact named input and output `Port` contracts;
- one success contract;
- a content-addressed `TaskOracle`;
- one or more optimization objectives;
- explicit hard constraints;
- maximum effects and permissions the task may authorize;
- the exact set of task-case identifiers;
- external requirements and namespaced extensions.

The contract MUST NOT name a preferred provider, model, library, binary, route,
or topology unless that choice is itself part of the problem definition. Such
choices normally belong to candidates, deployment bindings, or evidence.

`TaskContract.validate_program(program)` requires exact input/output names,
assignable nominal types, an identical success contract, and no program effect
or permission beyond the task boundary. A program is an implementation
candidate for a task; it cannot silently widen the task.

## 2. Oracle boundary

`TaskOracle` records evaluator identity and trust properties separately from
the nodes that produce an answer:

- `kind`: exact, property, cross-implementation, statistical, human, or
  external-authority;
- `evaluator_digest`: digest of the evaluator implementation or protocol;
- `implementation_ref`: resolvable implementation location;
- `independence`: independent, separate implementation, or producer self-check;
- `candidate_readable`: whether candidate code can inspect the evaluator.

An evaluator that is merely mounted read-only beside candidate code is readable,
not hidden. A confidential holdout requires a separate trust domain. A producer
self-check MAY be recorded, but consequential acceptance SHOULD use an
independent or separately implemented oracle.

Changing evaluator code changes its digest and therefore changes the task and
solution-pack identities. Never update an evaluator in place to make a candidate
pass.

## 3. Task cases

`TaskCaseSpec` identifies an immutable case without requiring private data to be
embedded in a public repository. It records:

- `development`, `validation`, `holdout`, or `stress` split;
- input content digest and artifact/fixture reference;
- optional expected-output digest;
- description, tags, and namespaced extensions.

The case input loaded at execution MUST hash to `input_digest`. The exact case
IDs MUST equal `TaskContract.case_ids`. Holdout observations MUST NOT update the
search policy that selected the route they evaluate.

Use public fixture references for transparent mechanism tests. Use separately
authorized artifact references for confidential data. Never label a transparent
fixture as hidden evidence.

## 4. Hard constraints and objectives

Hard constraints determine eligibility. Objectives compare eligible outcomes.

Examples of hard constraints include verifier acceptance, maximum policy risk,
required residency, or a cost ceiling that cannot be exceeded. Examples of
objectives include quality, cost, latency, reliability, and resource use.

An optimizer MAY order only compiler-valid, policy-authorized routes. It MUST
NOT trade away a hard constraint, grant a permission, repair a type mismatch,
or convert an oracle rejection into success.

## 5. Solution-pack closure

`SolutionPackManifest` is the portable bill of materials for solving one task.
It lists only digests for:

- the task contract;
- all included semantic programs;
- all closed registry snapshots;
- all node packs;
- all task cases;
- all evaluators;
- optional fixed baseline plans;
- optional benchmark suites;
- optional external artifacts.

`validate_solution_pack_closure(...)` compares the manifest with the supplied
objects using exact set equality. Missing and undeclared assets both fail. This
prevents a common provenance error: describing one immutable experiment while
executing code, cases, or evaluators from a mutable workspace.

Readiness is explicit:

| Value | Meaning |
|---|---|
| `template` | Reusable semantics exist; executable cases or evaluators may not. |
| `executable-fixture` | The complete local mechanism runs against declared fixtures. |
| `credentialed-connector` | Real execution needs scoped external authority or current data. |
| `production-adapter` | The pack declares a production integration; operational certification remains external. |

Readiness is not a quality score. An `executable-fixture` proves the framework
path, not production accuracy. A `production-adapter` is not automatically
safe, approved, or superior.

## 6. Reproducible execution sequence

1. Validate the task contract and all case specifications.
2. Validate each program against the task contract.
3. Negotiate discovery and freeze a closed registry snapshot.
4. Validate node-pack and registry digests.
5. Run full slot-by-candidate admission and retain every decision.
6. Freeze fixed baseline plans before adaptive search begins.
7. Validate the exact solution-pack closure.
8. Run benchmark arms against the same cases, seeds, oracle, and runtime class.
9. Persist artifacts and immutable receipts.
10. Publish the pack, suite, report, remaining search space, and limitations.

## 7. Extension rules

Forward-compatible metadata belongs in namespaced `extensions` entries such as
`example.vendor-field`. Extensions MUST be JSON-serializable. An extension MUST
NOT change the interpretation of a core field, grant capability or authority,
or become required for validating the core model without a model-version bump.

Private artifact locations, credentials, and secrets MUST NOT be embedded in
portable manifests. Publish a reference and resolve it through an authorized
artifact adapter at execution time.

## 8. Required rejection cases

Implementations MUST reject at least:

- a program whose external ports differ from the task contract;
- a program that requests undeclared effects or permissions;
- a case whose loaded bytes do not match its digest;
- a case set that differs from the task contract;
- an evaluator whose implementation digest differs from the oracle;
- a fixed plan that is not bound to the declared program and registry;
- a manifest with missing or undeclared closure members;
- duplicate identifiers or digests where uniqueness is required;
- an executable pack without cases and evaluator identity.

## 9. Reference implementation

The Python models live in `solutiongraph/tasking.py`. Strict JSON Schemas live
in `solutiongraph/schemas/task-contract.schema.json`,
`task-case.schema.json`, and `solution-pack.schema.json`. Six complete examples
are exported in `catalog/benchmarks/` and can be inspected with:

```bash
solutiongraph packs list
solutiongraph packs show solution-pack.stdlib-data-quality --json
solutiongraph benchmarks show benchmark.stdlib-data-quality --json
```

This protocol defines portable identity and closure. Runtime isolation,
distributed scheduling, authorization enforcement, and confidential evaluator
hosting are adapter responsibilities covered by `EXECUTION_PROTOCOL.md` and
`READINESS.md`.
