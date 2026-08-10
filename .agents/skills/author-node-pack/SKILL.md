---
name: author-node-pack
description: Create, extend, validate, or publish a reusable Universal Node Graph node pack. Use when an agent must wrap code, APIs, datasets, tools, models, connectors, or binaries as strict content-addressed NodeSpecs with candidates, descriptors, optional search documents or embeddings, registry capabilities, manifests, tests, and compiler-admission evidence.
---

# Author a reusable node pack

Read `../../../NODE_REPOSITORY_PROTOCOL.md` and
`../model-solution-graph/references/node-authoring.md` before changing a node
contract. Read `../model-solution-graph/references/registry-discovery.md` when
adding registry or retrieval behavior.

## Workflow

1. Identify one atomic implementation family and the semantic capabilities it
   actually implements.
2. Define exact named input/output ports, nominal types, schemas, media types,
   units, and cardinalities.
3. Declare parameters, runtime, entrypoint, implementation digest,
   determinism, idempotency, effects, permissions, resources, failure modes,
   preconditions, postconditions, invariants, and verifier.
4. Expand every finite parameter choice that should be visible in experiments
   into an explicit `Candidate`.
5. Add sparse optional `NodeDescriptor` sidecars for discovery. Attach each to
   the exact `NodeSpec.digest`; never let metadata grant compatibility.
6. Declare embedding spaces exactly when embeddings exist. Do not fabricate
   vectors or silently compare incompatible spaces.
7. Build a content-addressed `NodePackManifest` and advertise only registry
   capabilities the implementation actually supports.
8. Freeze discovery to a receipt-backed snapshot and run full compiler
   admission against realistic template slots.

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
