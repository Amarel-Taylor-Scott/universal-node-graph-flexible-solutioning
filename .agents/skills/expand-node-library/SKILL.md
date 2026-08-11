---
name: expand-node-library
description: Add, refine, validate, or publish reusable SolutionGraph primitives. Use when an agent must turn importable Python functions or external connectors into source-bound NodeSpecs, enumerate exact parameter candidates, add honest discovery sidecars, assemble a registry or node pack, prove compiler admission, or extend the dependency-free standard-library example.
---

# Expand the reusable node library

Read `../../../NODE_AUTHORING_GUIDE.md`,
`../../../NODE_REPOSITORY_PROTOCOL.md`, and
`../author-node-pack/SKILL.md` before editing implementations.

## Add one reusable primitive

1. Choose one atomic, implementation-neutral capability. Do not name the
   semantic capability after a package, provider, model, or binary.
2. Write a documented top-level importable function. Avoid lambdas, closures,
   nested functions, bound methods, undeclared host state, and implicit I/O.
3. Wrap it with `define_python_node`. Declare exact ports, parameters,
   capabilities, determinism, idempotency, effects, permissions, resources,
   contracts, failures, verifier, and source.
4. Run `PythonNodeDefinition.validate`; never hand-copy an implementation digest.
5. Expand finite experimental parameters through `enumerate_candidates` with
   an explicit maximum. Bind open-ended values deliberately.
6. Add sparse `NodeDescriptor` and `SearchDocument` sidecars. Do not fabricate
   embeddings or let discovery metadata grant compatibility.
7. Add the definition, candidates, sidecars, and exact digests to a registry and
   `NodePackManifest`.

## Prove reuse

1. Test success, boundary behavior, and every declared failure family.
2. Test signature/digest drift and stable candidate identity.
3. Admit the complete registry against at least one compatible and one
   incompatible semantic slot; assert diagnostics.
4. Execute through in-process and subprocess adapters when the ABI is portable.
5. Add the node to more than one task only when the same contract genuinely
   applies. Reuse is demonstrated by evidence, not a generic name.
6. Regenerate and validate the catalog after changing packs or descriptors.

```bash
solutiongraph doctor
solutiongraph catalog export --output catalog
solutiongraph verify --catalog-root catalog --runtime subprocess
pytest -q
ruff check browsergraph solutiongraph scripts
```

Use `solutiongraph/stdlib_nodes.py` and `solutiongraph/stdlib_pack.py` as the
reference implementation. Keep empirical quality, cost, and latency in receipts
or belief revisions—not the immutable node contract.
