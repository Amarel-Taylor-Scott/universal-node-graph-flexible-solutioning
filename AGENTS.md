# Universal Node Graph repository instructions

## Mission

Build and test a domain-neutral graph programming model. A task becomes a typed
semantic graph; every semantic slot exposes all admitted implementation
candidates; a compiler freezes one valid route; experiments and receipts teach
an optimizer which valid route to try next.

`browsergraph` is one adapter and stress test. New universal behavior belongs in
`solutiongraph` and MUST NOT depend on browsers, LLM vendors, or one workflow
engine.

## Read before architectural changes

1. `UNIVERSAL_NODE_GRAPH_SPEC.md` — normative model and invariants.
2. `NODE_REPOSITORY_PROTOCOL.md` — discovery sidecars, embeddings, handshake, snapshots.
3. `SOLUTION_TEMPLATE_PROTOCOL.md` — stages, atomic slots, and refinement loops.
4. `EXECUTION_PROTOCOL.md` — frozen plans, runtime adapters, artifacts, fallbacks, and receipts.
5. `RESEARCH_FOUNDATIONS.md` — source-backed design rationale.
6. `AUTORESEARCH_REVIEW.md` — generated-code campaigns, evaluator isolation, and numerical nodes.
7. `ARCHITECTURE.md` and `UNIVERSAL_GRAPH_SYSTEM.md` — existing runtime and viewer.

Use the narrowest matching workspace skill:

- `.agents/skills/create-solution-template/SKILL.md` for template authoring;
- `.agents/skills/author-node-pack/SKILL.md` for reusable node packs;
- `.agents/skills/benchmark-solution-graph/SKILL.md` for route experiments;
- `.agents/skills/execute-solution-graph/SKILL.md` for runtimes, artifacts, and executable examples;
- `.agents/skills/design-autoresearch-campaign/SKILL.md` for bounded LLM-generated improvement campaigns;
- `.agents/skills/model-solution-graph/SKILL.md` for end-to-end modeling.

## Non-negotiable ontology

- A task contract defines required outcome and independent acceptance.
- A semantic slot defines an obligation. It is not an implementation.
- A node definition is a reusable implementation ABI.
- A candidate is one exact node version/digest plus parameter binding.
- An admitted space records every slot/candidate admission or rejection.
- A belief model contains mutable learned priors. It is not program semantics.
- A frozen plan contains one exact candidate per slot and no mutable score.
- A receipt records observation. It never rewrites a definition or prior result.
- A campaign record preserves candidate ancestry and proposal identity. It does
  not grant admission or replace execution evidence.

Do not mix optimization, contracts, feedback, or evidence into the ordered task
steps as if they were more steps.

## Compiler invariants

- Validate before execution: IDs, topology, producer counts, port types,
  cardinality, capabilities, effects, permissions, parameters, constraints.
- Never perform an implicit type conversion. Add an explicit typed adapter node.
- Keep loops/branches as structured or composite nodes with nested graphs; do
  not add informal backward edges to a semantic DAG.
- Optimizer scores can order only compiler-valid routes. A score cannot grant
  authority or repair an invalid route.
- Examine the full registry during admission. Do not hide compatible candidates
  behind a top-k. Search budgets limit evaluation, not visibility.
- Every exclusion needs a stable diagnostic or explicit policy reason.
- Pass-through behavior is valid only when semantics, types, effects, and the
  optionality contract make it an actual identity operation.
- Content-address executable code, program definitions, registries, plans,
  environments, inputs, and output artifacts separately.
- Treat descriptors, documents, and embeddings as optional discovery sidecars;
  none can grant a capability, change a type, or repair an invalid `NodeSpec`.
- Negotiate registry/search capabilities, preserve a discovery receipt, and
  compile a closed-world snapshot. Do not claim global completeness.

## Node ABI changes

Any new field or behavior must answer how it affects:

- input/output type, version, schema, units, and cardinality;
- determinism, seeds, recording, retry, and idempotency;
- effects and required permissions;
- preconditions, postconditions, invariants, and failure taxonomy;
- implementation digest and runtime entrypoint;
- independent verification and receipt provenance;
- backward compatibility and schema versioning.

Empirical quality, latency, cost, or success rates belong in evidence/belief
objects, not in `NodeSpec`.

## Search and experiment rules

- Preserve a fast prior route, bounded beam and seeded-sprout modes, adaptive
  resource promotion, and an explicit exhaustive mode with no hidden cap.
- Every search report must disclose total Cartesian upper bound, evaluated,
  constraint-eliminated, heuristic-skipped, and unvisited routes, plus the
  belief revision and budget.
- Prefer Pareto comparison across quality, cost, latency, reliability, and
  policy over an unexplained scalar score.
- Use baselines, repeated seeds, holdout cases, independent verification, and
  best-so-far-vs-budget curves for claims about optimization.
- Call receipt-derived node effects observational unless assignment supports a
  causal claim.
- Select fallbacks for failure diversity as well as rank.
- Preserve multiple candidate lineages during generated-code campaigns; do not
  collapse all evidence into one greedy incumbent.
- Candidate code must not write its evaluator. Hidden cases require a
  candidate-unreadable evaluator, and untrusted generated code requires a real
  container, microVM, or remote trust boundary.

## LLM rules

- Treat an LLM as an ordinary nondeterministic or recorded node.
- Declare model/provider, prompt digest, tools/authority, sampling, structured
  output type, context inputs, and failure modes.
- Treat model output as untrusted until schema and independent success checks pass.
- Do not invent node capabilities, compatibility, benchmark results, or source
  claims. Inspect code and use primary documentation.

## Repository map

- `solutiongraph/` — domain-neutral semantic model, compiler, search, evidence.
- `solutiongraph/template_authoring.py` — strict linear blueprint compiler.
- `solutiongraph/executor.py` — strict reference frozen-plan executor and runtime seam.
- `solutiongraph/artifacts.py` — content-addressed value/artifact store protocol.
- `solutiongraph/experiments.py` — receipt-producing experiment allocation.
- `solutiongraph/campaign.py` — population ancestry, budgets, decisions, and evaluator boundaries.
- `solutiongraph/examples/` — six dependency-free executable domain examples.
- `solutiongraph/schemas/` — strict portable wire schemas.
- `catalog/` — generated semantic templates and reference node pack.
- `browsergraph/` — browser runtime adapter and original proof of concept.
- `examples/` — generated viewers, canonical data, and executable examples.
- `tests/test_solutiongraph.py` — universal conformance tests.
- `tests/test_workbench.py` — hierarchical viewer/workbench tests.

## Validation

Core changes:

```bash
solutiongraph doctor
pytest tests/test_solutiongraph*.py tests/test_workbench.py -q
ruff check solutiongraph browsergraph tests/test_solutiongraph*.py
```

Full deterministic suite:

```bash
pytest -q
```

Do not require optional browsers, model providers, or network access for the
universal core tests. Preserve user changes and avoid unrelated rewrites.
