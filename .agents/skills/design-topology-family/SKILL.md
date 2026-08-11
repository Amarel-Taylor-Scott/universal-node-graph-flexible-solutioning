---
name: design-topology-family
description: Design, validate, search, benchmark, or extend explicit alternative DAG shapes for one task. Use when a coding harness must compare adding, removing, splitting, merging, or reordering semantic obligations; mutate graph structure; retain topology ancestry; or search node routes across multiple compiler-valid ProgramGraph variants without hiding graph rewrites inside candidates or optimizer state.
---

# Design a topology family

Read `../../../UNIVERSAL_NODE_GRAPH_SPEC.md`,
`../../../TOPOLOGY_SEARCH_PROTOCOL.md`, and
`../../../EXECUTION_PROTOCOL.md`. Use
`../author-structured-workflow/SKILL.md` when a variant contains branches,
composites, or bounded loops. Use `../design-autoresearch-campaign/SKILL.md`
when a model generates variants iteratively.

## Freeze the shared contract

1. Define one exact task, typed external inputs/outputs, success contract,
   independent verifier, authority, objective set, cases, seeds, and budget.
2. Reject variants that change this contract. A different output or oracle is a
   different family, not another topology.
3. Establish a compiler-valid baseline topology and retain its digest.

## Author variants

1. Represent every shape as a complete `ProgramGraph` in a `TopologyVariant`.
2. Record a useful rationale, optional parent variant, named operator(s), and
   tags. Keep the program content-distinct from every sibling.
3. Split or combine only semantic obligations. Provider/model/package choices
   remain registry candidates inside each slot.
4. Validate every variant, then run `TopologySearchEngine.admit_all()` against
   the same immutable registry snapshot.
5. Preserve invalid variants as rejected campaign evidence when they came from
   a generated search; do not silently repair history.

## Search and compare

Use a `TopologySearchBudget` with explicit per-DAG route policy, topology limit,
global evaluation limit, and result limit. Start bounded. Use exhaustive only
when the complete summed route count is feasible and intentionally requested.

Compile each proposal through `TopologySearchEngine.compile()`. Evaluate all
surviving shapes with the same cases, runtime boundary, resources, verifier,
and metric definitions. Report total/searched topologies and evaluated,
constrained, heuristic-skipped, topology-skipped, and unvisited routes. Never
claim completeness unless the report proves it.

## Gate

```bash
solutiongraph conformance
pytest -q tests/test_solutiongraph_universal_control.py
solutiongraph verify --catalog-root catalog
```

Deliver the family and variant digests, parent/operator lineage, full admission
coverage, topology-search report, frozen evaluated plans, receipts, Pareto
front, remaining space, and production limitations.
