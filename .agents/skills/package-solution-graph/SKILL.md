---
name: package-solution-graph
description: Package, validate, audit, or publish one portable SolutionGraph task universe. Use when an agent must freeze task meaning, case splits, oracle identity, programs, registries, node packs, baselines, benchmark suites, artifacts, licenses, and readiness into an exact content-addressed SolutionPackManifest closure.
---

# Package a solution graph

Read `../../../TASK_AND_SOLUTION_PACK_PROTOCOL.md`,
`../../../NODE_REPOSITORY_PROTOCOL.md`, and `../../../BENCHMARK_PROTOCOL.md`.

## Freeze the problem

1. Define one implementation-neutral `TaskContract` with exact ports, success
   contract, objectives, hard constraints, effects, permissions, and external
   requirements.
2. Identify the evaluator with a `TaskOracle`. Record implementation digest,
   independence, and whether candidates can read it.
3. Define every immutable `TaskCaseSpec` and split. Verify loaded input bytes
   against the declared digest. Make task `case_ids` exactly equal the case set.
4. Validate every proposed `ProgramGraph` against the task contract. A program
   may not change external ports, success meaning, effects, or authority.

## Freeze the solution universe

1. Negotiate discovery and freeze exact registry snapshots.
2. Include every required `NodePackManifest`; do not describe mutable source
   directories as content-addressed packs.
3. Compile declared control/baseline routes into exact `FrozenPlan`s.
4. Bind benchmark suites only after task, program, registry, case, evaluator,
   seeds, repetitions, holdouts, and claim scope are fixed.
5. Choose honest readiness: `template`, `executable-fixture`,
   `credentialed-connector`, or `production-adapter`.
6. Keep credentials and private bytes outside the manifest; include authorized
   content-addressed references.

## Validate closure

Construct `SolutionPackManifest` with exact digest sets, then call
`validate_solution_pack_closure`. Missing and undeclared objects both fail.
Do not publish if execution loaded a different program, registry, case,
evaluator, baseline, or benchmark than the manifest names.

```bash
solutiongraph packs list
solutiongraph packs show <solution-pack-id> --json
solutiongraph doctor
solutiongraph verify --catalog-root catalog --runtime subprocess
pytest -q
```

Publish the manifest, referenced schemas, license, source, and limitations.
Readiness and digest closure prove identity, not performance or operational
certification.
