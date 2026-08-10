# Agent Playbook: Build Graph Solutions Without Guessing

This playbook is for coding agents and human reviewers applying Universal Node
Graph to a new task, ticket, competition, service, or workflow.

Instructions improve consistency; they are not the enforcement boundary. JSON
Schemas, compiler diagnostics, content digests, tests, independent verifiers,
and CI decide whether an artifact is acceptable.

## Required workflow

### 1. Restate the task contract

Record concrete inputs, required outputs, hard policy/resource constraints, and
an independent acceptance oracle. If the oracle is missing, stop and make that
gap explicit. Do not use “the node returned success” as sufficient evidence.

### 2. Select and critique a semantic template

Search `catalog/templates/` by domain and tags. A template is a hypothesis:
compare every obligation to the task. Explain removed and added slots. Split
any slot whose alternatives are not genuine substitutes.

### 3. Refine types before tools

Name each value, version, schema digest, media type, units, and cardinality.
Trace every required input to exactly one producer unless it is explicitly
many/stream. Add visible adapter, merge, branch, or structured loop slots.

### 4. Discover, do not invent, implementations

Negotiate registry capabilities. Query exact/typed metadata first, then
compatible lexical/vector channels. Preserve the query and coverage receipt.
If no node exists, say so; generated code enters as a new quarantined node with
tests and a content digest, never as an imaginary registry capability.

### 5. Author node contracts before runtime glue

For every new node, define the complete ABI, effect/permission boundary,
determinism, idempotency, failures, resources, verifier, fixtures, and artifact
identity. Keep optional descriptions and embeddings in sidecars.

### 6. Compile the complete snapshot

Run program and registry validation, then full slot×candidate admission. Fix
semantic and authority defects before search. Never delete a rejection merely
to make the matrix look cleaner.

### 7. Freeze a baseline

Select one compiler-valid route, freeze exact bindings and digests, and run a
small acceptance case. This distinguishes a viable architecture from a large
unexecutable search space.

### 8. Allocate experiments explicitly

Choose among prior, beam, seeded sprout, adaptive/multi-fidelity, or exhaustive
search. Record every budget and seed. Use holdouts, repeated seeds, independent
verification, and Pareto metrics. Promote only accepted plans.

### 9. Learn conservatively

Append receipts. Update a new belief revision with evidence counts and
uncertainty. Label observational attribution as correlation. Select fallbacks
for failure and dependency diversity, not merely second-place score.

### 10. Deliver evidence

Report the template revision, discovery receipt, registry snapshot, compiler
diagnostics, search coverage, frozen plan, receipts, tests, limitations, and
unvisited space. Avoid claims not supported by real execution.

## Patterns

- **Strict core, flexible sidecars:** types/authority stay stable while search
  vocabularies and vectors can evolve.
- **Open discovery, closed compilation:** query federated sources, then freeze
  the exact universe used to make a claim.
- **One column per obligation:** every admitted implementation is visible
  vertically; route lines connect exactly one choice per ordered slot.
- **Submatrix as navigation:** macro stages group slots without becoming nodes.
- **Explicit identity candidate:** a safe no-op competes like any other node.
- **Adapter as node:** conversions, provider bridges, and schema migrations are
  visible, typed, testable, and measurable.
- **Composite promotion:** a repeatedly successful child graph can become a
  versioned composite node while retaining its derivation.
- **Sprouts around anchors:** use prior routes and partial domain hints as
  starting points, with a recorded seed and mutation budget.
- **Multi-fidelity promotion:** spend small resources broadly, then promote
  accepted routes deterministically.
- **Independent failure fallback:** rank portfolios by shared dependencies and
  failure classes as well as mean performance.

## Anti-patterns and required response

| Anti-pattern | Why it fails | Agent response |
|---|---|---|
| Candidate named as a step | Confuses what with how | Rename slot semantically; move tool/provider into registry |
| Hidden model or parameter choices | Search space and evidence become dishonest | Expand finite choices into visible candidates |
| Embedding similarity used as type safety | Semantic proximity is not ABI compatibility | Nominate via search, then compile exact ports |
| Unversioned catch-all dictionary | Changes and incompatibilities become invisible | Introduce named versioned schemas |
| Optimizer grants an effect | Scores become an authority escalation | Reject before search; require explicit permission |
| LLM fills missing contract fields | Produces confident fictional compatibility | Inspect source or stop with a coverage gap |
| Top-k registry admission | Compatible nodes silently disappear | Freeze a snapshot and examine it completely |
| “All nodes” across the internet | Unfalsifiable completeness claim | State registry/query/snapshot boundary |
| Infinite repair loop | Unbounded cost and non-replayable behavior | Add stop contract, iteration/resource budget, receipts |
| Node self-verifies consequential output | Correlated failures pass unnoticed | Use a distinct oracle where feasible |
| Search winner reported from training cases | Overstates generalization | Reserve holdout cases and report best-so-far curves |
| Second-ranked route as fallback | Shared dependency may fail simultaneously | Optimize failure/dependency diversity |
| Synthetic benchmark presented as production proof | Confuses mechanism with evidence | Label fixture results and run real task cases |

## Minimum commands

```bash
python scripts/export_solutiongraph_catalog.py --output catalog
pytest tests/test_solutiongraph*.py -q
ruff check solutiongraph tests/test_solutiongraph*.py
```

For a new domain, add at least:

- one semantic template or documented template delta;
- two interchangeable candidates in more than one slot;
- negative compiler tests for types/effects/permissions;
- one frozen baseline route;
- an independent acceptance fixture;
- one bounded search report;
- a receipt and replay/provenance assertion.
