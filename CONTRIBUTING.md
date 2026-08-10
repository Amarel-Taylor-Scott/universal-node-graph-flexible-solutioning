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
ruff check browsergraph solutiongraph tests/test_solutiongraph*.py
```

The core suite must remain runnable without a browser or network connection.
Optional engine tests may skip when their runtimes are unavailable.

## Add a reusable node

1. Define one implementation with a stable namespaced identity.
2. Declare typed input and output ports.
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
