# Contributing

Contributions should increase capability, correctness, evidence, or clarity
without imposing arbitrary limits on node diversity or graph scale.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
ruff check browsergraph
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
