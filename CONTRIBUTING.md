# Contributing

Contributions should increase capability, correctness, evidence, or clarity
without imposing arbitrary limits on node diversity or graph scale.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
solutiongraph doctor
pytest -q
ruff check browsergraph solutiongraph tests/test_solutiongraph*.py scripts
solutiongraph verify --catalog-root catalog --runtime in-process
solutiongraph verify --catalog-root catalog --runtime subprocess
```

The core suite must remain runnable without a browser or network connection.
Optional engine tests may skip when their runtimes are unavailable.

## Add a reusable node

1. Read `NODE_AUTHORING_GUIDE.md`; for Python, wrap one importable top-level
   function with `define_python_node` so signature and source identity cannot drift.
2. Define one implementation with a stable namespaced identity and typed ports.
3. Declare capabilities, parameter choices, dependencies, permissions,
   effects, runtime requirements, resources, and provenance.
4. Materialize selectable parameter bindings as distinct candidate IDs.
5. Add contract and behavior tests.
6. Add the node to a representative workbench only where its capabilities and
   ports satisfy the atomic substep.

Do not turn a model name, package, browser binary, policy, metric, optimizer,
or feedback signal into a task substep unless the task semantics genuinely
require it as an action.

## Refine a task hierarchy

A macro stage must split into atomic substeps whenever two operations can vary
independently, have a typed boundary, can fail separately, can be verified
separately, or deserve separate optimization. Macro stages group contiguous
substeps but are never selectable route nodes.

Every route must select one primary candidate per atomic substep. Optional
substeps use explicit pass-through candidates rather than missing route keys.

## Add a reusable solution template

1. Inspect related decompositions with `solutiongraph templates list` and
   `solutiongraph templates show <id>`.
2. Use `examples/custom-template-blueprint.json` for a linear stage/slot matrix,
   or the full Python model for non-linear topology.
3. Give every slot an independent success contract and semantic capability.
4. Validate with `solutiongraph templates validate <blueprint>`.
5. Compile the portable document with `solutiongraph templates create`.
6. Add a reference-library entry and tests when contributing it to the bundled
   catalog.
7. Regenerate with `solutiongraph catalog export --output catalog` and
   `python scripts/sync_catalog_explorer.py`.

Use `@create-solution-template` in a compatible agent harness for the complete
review checklist. Stages are navigation; tools and vendors remain candidate
nodes, and optimization remains outside the execution path.

## Add an executable domain or runtime

1. Read `EXECUTION_PROTOCOL.md` and use `@execute-solution-graph` when available.
2. Compile a closed-world `AdmittedSpace` and freeze exact primary/fallback bindings.
3. Implement the narrow runtime/artifact protocols without importing domain
   behavior into the compiler.
4. Declare real isolation and authority; an in-process adapter is not a sandbox.
5. Add independent task verification and retain failed/rejected receipts.
6. Add an executable example or notebook with at least two genuine choices in
   multiple slots.
7. Test tampering, permissions, effects, retries, fallbacks, artifacts, and
   verifier rejection.

## Add a solution pack or benchmark

1. Read `TASK_AND_SOLUTION_PACK_PROTOCOL.md` and `BENCHMARK_PROTOCOL.md`.
2. Freeze a task contract, exact case splits, and independently identified
   oracle before allocating route experiments.
3. Validate every program against the task and every registry/node pack by
   content digest.
4. Include fixed control/candidate arms and bounded solver arms under identical
   cases, seeds, repetitions, oracle, objectives, and runtime class.
5. Preserve unsuccessful arms, holdout state, unvisited routes, and claim scope.
6. Validate exact `SolutionPackManifest` closure and regenerate `catalog/`.
7. Add machine-readable JSON evidence; HTML is a human projection, not the
   authoritative record.

Use `@package-solution-graph` and `@run-benchmark-arena` in a compatible coding
harness for the full checklists.

Run `pytest tests/test_solutiongraph_execution.py -q` in addition to the core
suite. Mechanism fixtures are welcome when labeled; production claims require
held-out real tasks and enforcing runtimes.

## Add a control-versus-mutation graph experiment

1. Read `GRAPH_EXPERIMENTS.md` and declare a content-distinct `TopologyFamily`.
2. Keep task, success contract, and named external input/output value contracts
   identical across variants.
3. Record acyclic parent lineage and explicit mutation operators.
4. Freeze one exact `GraphControl`; never let search silently replace it.
5. Run every selected plan on identical cases, seeds, repetitions, verifier,
   objectives, and execution policy.
6. Use `require_complete_grid=True` only for uncapped exhaustive searches whose
   result limits expose every feasible plan.
7. Validate the report with `graph-experiment-report.schema.json` and retain
   rejected controls, failed mutations, raw receipts, Pareto flags, and budget
   accounting.

For generated topology proposals, contribute a typed, deterministic mutation
operator that emits ordinary `ProgramGraph` variants. The normal compiler must
remain the compatibility authority; do not bypass admission or claim that an
undeclared graph universe was searched.

Use `GraphMutationEngine` for input/edge/output insertion, linear ablation, or
slot-contract refinement. Add a narrower typed operator for any other rewrite,
test invalid type and interface cases, and validate its strict mutation receipt.
When comparing outcomes, pair exact control/candidate receipts with a frozen
`StudyDesign`; report unmatched observations and `study.continue` instead of
promoting under insufficient evidence.

External benchmark contributions must preserve the exact source, version,
license, evaluator/harness identity, leakage policy, claim scope, and known
limitations. A manifest adapter must not fetch data, use credentials, submit a
result, or present local fixtures as an externally certified score.

## Add an LLM-generated improvement campaign

1. Read `AUTORESEARCH_REVIEW.md` and use `@design-autoresearch-campaign`.
2. Freeze task, evaluator, split, environment, registry, program, and budget.
3. Preserve every compiled proposal and its parent IDs in a campaign ledger.
4. Quarantine generated nodes and re-run admission for every mutation or merge.
5. Keep hidden evaluators outside the candidate trust domain.
6. Preserve negative evidence and confirm promotion with repeated clean
   holdouts on a declared reference environment.

## Pull requests

- Keep unrelated changes separate.
- Explain the contract or behavior being changed.
- Include tests and the commands used to run them.
- Regenerate affected JSON and self-contained HTML artifacts.
- Preserve backward compatibility or document the migration explicitly.
- Never include credentials, private task data, generated caches, or local
  environment artifacts.

By contributing, you agree that your contribution is licensed under the MIT
License included in this repository.
