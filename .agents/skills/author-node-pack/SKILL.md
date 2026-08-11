---
name: author-node-pack
description: Create, extend, validate, or publish a reusable Universal Node Graph node pack. Use when an agent must wrap code, APIs, datasets, tools, models, connectors, or binaries as strict content-addressed NodeSpecs with candidates, descriptors, optional search documents or embeddings, registry capabilities, manifests, tests, and compiler-admission evidence.
---

# Author a reusable node pack

Read `../../../NODE_REPOSITORY_PROTOCOL.md`, `../../../NODE_AUTHORING_GUIDE.md`, and
`../model-solution-graph/references/node-authoring.md` before changing a node
contract. Read `../model-solution-graph/references/registry-discovery.md` when
adding registry or retrieval behavior.

## Workflow

1. Identify one atomic implementation family and the semantic capabilities it
   actually implements.
2. For Python, use `define_python_node` so callable signature, importable
   entrypoint, and source-derived implementation digest are checked together.
3. Define exact named input/output ports, nominal types, schemas, media types,
   units, and cardinalities.
4. Declare parameters, runtime, entrypoint, implementation digest,
   determinism, idempotency, effects, permissions, resources, failure modes,
   preconditions, postconditions, invariants, and verifier.
5. Expand every finite parameter choice that should be visible in experiments
   into an explicit `Candidate`. Use `enumerate_candidates` with an explicit
   maximum; never silently truncate a finite Cartesian space.
6. Add sparse optional `NodeDescriptor` sidecars for discovery. Attach each to
   the exact `NodeSpec.digest`; never let metadata grant compatibility.
7. Declare embedding spaces exactly when embeddings exist. Do not fabricate
   vectors or silently compare incompatible spaces.
8. Build a content-addressed `NodePackManifest` and advertise only registry
   capabilities the implementation actually supports.
9. Freeze discovery to a receipt-backed snapshot and run full compiler
   admission against realistic template slots.
10. Follow `solutiongraph/stdlib_pack.py` as the dependency-free reference:
    public authoring SDK, explicit identity candidate, sidecars, documents,
    exact bindings, pack manifest, executable graph, and oracle-backed tests.

## Verify

```bash
solutiongraph doctor
solutiongraph catalog export --output catalog
pytest tests/test_solutiongraph*.py -q
ruff check solutiongraph tests/test_solutiongraph*.py
```

Reject the node pack if executable truth appears only in prose, empirical
quality is embedded in `NodeSpec`, authority is inferred, code is not digest
bound, failure is collapsed into a generic exception, optional metadata is
required for execution, or registry search hides compatible nodes behind top-k.
