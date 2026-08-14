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
2. `TASK_AND_SOLUTION_PACK_PROTOCOL.md` — stable task meaning, cases, oracle, and exact closure.
3. `NODE_REPOSITORY_PROTOCOL.md` and `NODE_AUTHORING_GUIDE.md` — executable ABI, discovery sidecars, embeddings, handshake, snapshots.
4. `SOLUTION_TEMPLATE_PROTOCOL.md` — stages, atomic slots, and refinement loops.
5. `BENCHMARK_PROTOCOL.md` — controlled arms, holdouts, claim scopes, and evidence.
6. `EXECUTION_PROTOCOL.md` — frozen plans, runtime adapters, artifacts, fallbacks, and receipts.
7. `STRUCTURED_CONTROL_PROTOCOL.md` and `TOPOLOGY_SEARCH_PROTOCOL.md` — control flow and graph-shape search.
8. `STREAMING_PROTOCOL.md` and `PROVENANCE_AND_RESUME.md` — event time, recovery, and lineage boundaries.
9. `RESEARCH_FOUNDATIONS.md` and `AUTORESEARCH_REVIEW.md` — source-backed tradeoffs, campaigns, evaluator isolation, and numerical nodes.
10. `ARCHITECTURE.md` and `UNIVERSAL_GRAPH_SYSTEM.md` — existing runtime and viewer.

Use the narrowest matching workspace skill:

- `.agents/skills/create-solution-template/SKILL.md` for template authoring;
- `.agents/skills/author-node-pack/SKILL.md` for reusable node packs;
- `.agents/skills/benchmark-solution-graph/SKILL.md` for route experiments;
- `.agents/skills/execute-solution-graph/SKILL.md` for runtimes, artifacts, and executable examples;
- `.agents/skills/design-autoresearch-campaign/SKILL.md` for bounded LLM-generated improvement campaigns;
- `.agents/skills/design-topology-family/SKILL.md` for explicit graph-shape alternatives;
- `.agents/skills/author-structured-workflow/SKILL.md` for branches, composites, loops, and compensation;
- `.agents/skills/solve-universal-dag/SKILL.md` for UniversalSolver and Arena task implementation;
- `.agents/skills/package-solution-graph/SKILL.md` for task/asset closure;
- `.agents/skills/run-benchmark-arena/SKILL.md` for controlled solution-space experiments;
- `.agents/skills/expand-node-library/SKILL.md` for reusable source-bound primitives;
- `.agents/skills/model-solution-graph/SKILL.md` for end-to-end modeling.

## Non-negotiable ontology

- A task contract defines required outcome and independent acceptance.
- A task case fixes one input identity and evaluation split; it is not a mutable fixture path.
- A solution pack fixes the exact task/program/registry/node-pack/case/oracle closure.
- A semantic slot defines an obligation. It is not an implementation.
- A node definition is a reusable implementation ABI.
- A candidate is one exact node version/digest plus parameter binding.
- An admitted space records every slot/candidate admission or rejection.
- A belief model contains mutable learned priors. It is not program semantics.
- A frozen plan contains one exact candidate per slot and no mutable score.
- A receipt records observation. It never rewrites a definition or prior result.
- A benchmark suite fixes arms, cases, seeds, holdouts, and claim scope. A report
  records completion; `ok` does not mean every arm found an accepted route.
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
- Conditional outputs feed compatible guarded consumers or optional ports on
  an explicit merge; they never directly promise a required graph output.
- Lower composites and bounded loops before admission and retain the lowering
  receipt. Search graph-shape alternatives only as explicit `TopologyVariant`s.
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
- Compare fixed-route and solver arms against the identical task, cases, seeds,
  repetitions, oracle, and runtime class. Do not leak runtime state across arms.
- Treat `completed-no-accepted-route` as a valid bounded-search result. Only a
  complete exhaustive arm may claim optimality over its declared snapshot.
- Call receipt-derived node effects observational unless assignment supports a
  causal claim.
- Select fallbacks for failure diversity as well as rank.
- Execute multi-fidelity rungs through a fixed evaluator and retain every
  promotion plus resource unit; a planned allocation is not measured evidence.
- Preserve multiple candidate lineages during generated-code campaigns; do not
  collapse all evidence into one greedy incumbent.
- Candidate code must not write its evaluator. Hidden cases require a
  candidate-unreadable evaluator, and untrusted generated code requires a
  microVM or remote trust boundary. A plain container is lifecycle isolation,
  not an adversarial boundary.

## LLM rules

- Treat an LLM as an ordinary nondeterministic or recorded node.
- Declare model/provider, prompt digest, tools/authority, sampling, structured
  output type, context inputs, and failure modes.
- Treat model output as untrusted until schema and independent success checks pass.
- Do not invent node capabilities, compatibility, benchmark results, or source
  claims. Inspect code and use primary documentation.

## Repository map

- `solutiongraph/` — domain-neutral semantic model, compiler, search, solver, evidence.
- `solutiongraph/specialized/` — extraction-ready vertical authoring packages,
  typed recipes, profiler features, metrics, gates, transparent recommendation,
  artifact-kind composition, exact asset validation, and declare-before-load
  entry-point discovery. A specialized package is not a node pack or executable
  solution-pack closure.
- `solutiongraph/interrogation/` — aggregate profiling, all-visible question
  planning, deterministic check adapters, reversible shadow repair, and
  independent verification. Keep question definitions in `question_packs/`
  separate from executable node definitions in `interrogation/nodes/`.
- `solutiongraph/design_atlas/` — 618 C1-only technique records, task
  archetypes, modular evidence-seeking design packs, all-visible E1–E10
  planning, decision dossiers, reports, and evidence-derived C0–C7 maturity.
  Executable atlas stages live one-per-file in `design_atlas/nodes/`; human and
  model planners share typed ports but retain distinct permission contracts.
  Keep technique/catalog truth, design decisions, executable nodes, and
  benchmark evidence separate.
- `solutiongraph/solver.py` — guarded multi-round search, experiment, ranking, champion, and route-fallback orchestration.
- `solutiongraph/structured.py` — deterministic composite and bounded-loop lowering.
- `solutiongraph/topology.py` — alternative graph families and route accounting.
- `solutiongraph/durable.py` — exact local completed-prefix checkpoints and resume.
- `solutiongraph/streaming.py` — finite event-time conformance adapter.
- `solutiongraph/saga.py` — reference compensation runner for effectful nodes.
- `solutiongraph/compatibility.py` — optional operational compatibility sidecars.
- `solutiongraph/provenance.py` — W3C PROV, OpenLineage, and SLSA projections.
- `solutiongraph/conformance.py` — installed-wheel advanced mechanism gate.
- `solutiongraph/arena.py` — cross-domain task contracts, readiness, and executable suite harness.
- `solutiongraph/template_authoring.py` — strict linear blueprint compiler.
- `solutiongraph/executor.py` — strict reference frozen-plan executor and runtime seam.
- `solutiongraph/subprocess_runtime.py` — bounded lifecycle process adapter; never call it a hostile-code sandbox.
- `solutiongraph/artifacts.py` — content-addressed value/artifact store protocol.
- `solutiongraph/ledger.py` — fsync-backed content-chained local receipt journal.
- `solutiongraph/experiments.py` — receipt-producing experiment allocation.
- `solutiongraph/scaffold.py` — non-destructive starter workspaces for coding harnesses.
- `solutiongraph/campaign.py` — population ancestry, budgets, decisions, and evaluator boundaries.
- `solutiongraph/tasking.py` — portable task contracts, cases, oracles, and exact solution-pack closure.
- `solutiongraph/authoring.py` — source-bound Python node authoring and exact candidate expansion.
- `solutiongraph/benchmarking.py` — controlled benchmark arms and offline evidence reports.
- `solutiongraph/benchmark_adapters.py` — side-effect-free external source-manifest normalization.
- `solutiongraph/agent_bench/` — ten coding-agent tasks, paired workspaces,
  compatible harness/model allocation, sealed scoring, journals, analysis, and reports.
- `solutiongraph/graph_experiments.py` — exact controls, topology mutations, common trials, and cross-graph evidence.
- `solutiongraph/mutations.py` — deterministic typed topology authoring with compiler gating.
- `solutiongraph/studies.py` — paired uncertainty analysis over immutable receipts.
- `solutiongraph/solutioning.py` — staged task recognition, routing, execution, and history closure.
- `solutiongraph/ranking.py` — reusable receipt-derived gates, Pareto flags, and weighted projections.
- `solutiongraph/stdlib_pack.py` — 19 dependency-free reusable nodes and 32 bindings.
- `solutiongraph/examples/` — 54 dependency-free executable domain examples,
  including ten three-strategy data-science lifecycle graphs.
- `solutiongraph/schemas/` — strict portable wire schemas.
- `catalog/` — generated templates, node packs, Arena tasks, solution packs, and benchmarks.
- `browsergraph/` — browser runtime adapter and original proof of concept.
- `examples/` — generated viewers, canonical data, and executable examples.
- `tests/test_solutiongraph.py` — universal conformance tests.
- `tests/test_workbench.py` — hierarchical viewer/workbench tests.

## Validation

Core changes:

```bash
solutiongraph doctor
solutiongraph conformance
solutiongraph verify --catalog-root catalog
solutiongraph verify --catalog-root catalog --runtime subprocess
solutiongraph agent-bench smoke --output /tmp/solutiongraph-agent-smoke
pytest tests/test_solutiongraph*.py tests/test_workbench.py -q
ruff check solutiongraph browsergraph tests/test_solutiongraph*.py
```

Full deterministic suite:

```bash
pytest -q
```

Do not require optional browsers, model providers, or network access for the
universal core tests. Preserve user changes and avoid unrelated rewrites.
