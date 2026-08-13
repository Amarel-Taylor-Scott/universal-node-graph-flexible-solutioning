# Roadmap

The project advances only when evidence supports the next layer. A larger
diagram or candidate count is not, by itself, progress.

## Implemented proof of concept

- Versioned node manifests with ports, parameters, capabilities, permissions,
  effects, dependencies, runtimes, resources, provenance, and metrics.
- Hierarchy of task → macro-stage submatrix → atomic substep → candidate.
- Validation of hierarchy ownership, contiguous order, complete candidate
  discovery, parameter bindings, pass-through eligibility, route completeness,
  adjacent ports, fallbacks, feedback channels, and optimization profiles.
- Five synchronized offline viewer projections.
- Substep-local, macro-local, and complete-route proposals with inspectable
  objective contributions.
- Durable execution receipts and optimization-decision traces.
- BrowserGraph runtime demonstrating multiple interchangeable execution
  engines behind a stable port.
- Domain-neutral `solutiongraph` package with separate semantic-program,
  registry, admitted-space, belief, frozen-plan, and evidence representations.
- Strict nominal node ABI and bundled JSON Schemas for types, cardinalities,
  effects, permissions, determinism, resources, failure modes, and provenance.
- Compiler-checked conditional activation with explicit skipped receipts and
  invalid conditional-edge/graph-output diagnostics.
- Deterministic composite and bounded-loop lowering into namespaced atomic DAGs
  with content-addressed expansion receipts.
- Explicit topology families and search over alternative compiler-valid graph
  shapes in addition to node bindings, with independent budget accounting.
- Five deterministic typed mutation operators that construct complete child
  graphs, preserve public interfaces, record ancestry/hypotheses, and require
  ordinary compiler validation before entering a topology family.
- Full registry-to-slot admission handshake with an inspectable decision for
  every candidate/slot pair and n-ary configuration constraints.
- Negotiated registry discovery with sparse descriptors, exact named embedding
  spaces, graceful query fallback, coverage receipts, and closed-world snapshots.
- Portable node packs and a deterministic reference catalogue containing a
  five-node core pack, a 19-node/32-binding standard-library pack, two Arena
  packs, and 31 cross-domain templates with 544 atomic obligations.
- Dependency-free template authoring CLI, strict linear-blueprint schema, and
  focused workspace skills for templates, node packs, and benchmarking.
- Prior-guided, beam, seeded-sprout, and uncapped exhaustive route search with explicit
  accounting for evaluated, rejected, skipped, and unvisited configurations.
- Successive-halving promotion and patience-based early stopping primitives.
- Executed successive-halving rungs with caller evaluators, exact promotion
  decisions, and total resource accounting.
- Immutable run receipts, Pareto comparison, observational belief fitting, and
  repository instructions for Codex, Claude, Gemini, Copilot, and other agents.
- Paired control/candidate study reports with deterministic bootstrap intervals,
  practical-effect thresholds, acceptance and hard-objective gates, unmatched
  evidence accounting, and promote/reject/continue recommendations.
- A trusted-local reference executor that reconstructs frozen plans, verifies
  implementation digests, content-addresses outputs, applies bounded retries
  and frozen fallbacks, invokes an independent verifier, and emits receipts.
- A strict subprocess lifecycle adapter with a portable JSON/bytes ABI,
  wall-clock termination, reduced environment, optional POSIX CPU/memory
  limits, and explicit adapter/isolation receipt identity.
- An fsync-backed local JSONL receipt journal with duplicate protection,
  monotonic sequence, hash chaining, tamper/truncation verification, and an
  immediate experiment receipt sink.
- Exact local completed-prefix checkpoints with content-addressed output
  rehydration and identity-bound resume after interruption.
- A finite event-time reference adapter with windows, watermarks, allowed
  lateness, retractions, and explicit too-late drops.
- Reverse-order saga compensation over ordinary effectful nodes, with visible
  idempotency keys, attempts, and uncompensated failures.
- Compatibility sidecars for optional ordering, time, nullability, data
  classification, state, cache, secret, hardware, residency, and compensation
  constraints while preserving a stable executable ABI.
- W3C PROV, OpenLineage, and in-toto/SLSA projections from run receipts plus an
  installed-wheel advanced conformance suite.
- Transactional `solutiongraph init` starter workspaces that bind a selected
  semantic template, task intake, and coding-agent instructions without
  inventing nodes or evidence.
- Twenty-four dependency-free executable programs spanning 20 Arena task
  families, including data, identity, privacy, operations, security, science,
  recommendation, and numerical workflows in addition to the six numbered notebooks.
- Campaign contracts for bounded generated candidates/trials, immutable
  proposal ancestry, append-only evidence decisions, and explicit evaluator
  trust boundaries, plus a harness skill for population-based campaigns.
- Versioned task contracts, task cases, evaluator identity, exact solution-pack
  closure, and five strict JSON Schemas for portable task/benchmark evidence.
- A source-bound Python node-authoring SDK plus 19 dependency-free reusable
  primitives wrapped through that same public API.
- Six executable benchmark packs containing 24 cases, fixed controls, bounded
  solver policies, clean holdout reporting, complete search accounting, and
  self-contained HTML/JSON evidence reports.
- Twelve additional semantic templates for knowledge, claims, fraud,
  cybersecurity, compliance, geospatial, audio, supply chain, scheduling,
  database migration, SRE, and content moderation.
- A staged `TaskSolutionEngine` that composes validation, task recognition,
  historical retrieval, diverse effort portfolios, compilation, execution,
  evidence access, negative-transfer assessment, and immutable history closure.
- Claim-safe manifest adapters for Kaggle, MLE-bench, SkillsBench, SWE-bench,
  BrowserGym, and DueCare-style evaluations without external side effects or
  score claims.
- A ten-task coding-agent control/treatment arena with compatible harness/model
  matrices, sealed lifecycle evaluators, counterbalanced pairs, strict budgets,
  hash-chained receipts, uncertainty analysis, diagrams, a notebook, and a
  deterministic model-free transport smoke.
- A semantic interrogation and reversible-repair reference layer with 46
  concepts, 11 question packs, 86 all-visible questions, aggregate profiling,
  conservative field mapping, effort/capability/permission planning, 43
  deterministic checks, redacted reports, append-only utility memory, eight
  typed nodes, and an independently verified shadow feedback loop.
- A data-science design atlas with 618 provenance-preserving technique entries,
  31 common task archetypes, 28 modular packs, 112 evidence-seeking questions,
  all-visible E1–E10 planning, explicit LLM/human/external authority, portable
  reports, C0–C7 maturity derived from contiguous evidence gates, and a
  five-node/34-binding graph-native planning and dossier pack.
- A universal engineering decision layer with 14 obligation families, 13
  domain packs, 42 all-visible questions, ten task-context channels, explicit
  response authority, and capability coverage derived from exact repository
  assets through contiguous C0–C7 gates.
- Side-effect-free OpenAPI, CloudEvents, and structural BPMN authoring
  projections plus portable frozen-plan exports for Airflow, Dagster, Temporal,
  and Kubernetes adapter implementations.
- Opt-in exact runtime payload validation at graph and node boundaries, plus
  bounded local parallel experiment allocation with fresh execution state and
  deterministic evidence order.

## Phase 1 — compiler and registry discovery (foundation implemented)

- Stabilize and version the semantic program, node registry, admitted space,
  search report, frozen plan, and run receipt representations.
- Exercise version-, type-, capability-, effect-, permission-, deployment-, and
  search-capability negotiation across language runtimes and independent registries.
- Persist admission coverage and all rejection reasons as portable artifacts.
- Materialize large parameter spaces lazily while preserving exact counts and
  deterministic generation rules.
- Add explicit schema migration rules before advancing the model version.

**Release gate:** an intent can compile into a validated, reproducible route
without viewer-specific logic.

## Phase 2 — isolated execution and receipts

**Reference bootstrap implemented:** the in-process Python adapter, bounded
subprocess lifecycle adapter, runtime and artifact protocols, memory/file
content stores, content-chained local receipt journal, admitted-space-bound
plans, ordered frozen fallbacks, bounded retry, candidate circuit breaking,
independent task verification, experiment execution, and receipt-producing
domain examples are now executable. This proves the seam but is not an
adversarial-isolation or production-durability claim.

**Still required for the phase gate:**

- Execute heterogeneous and untrusted node runtimes in enforcing least-
  privilege sandboxes or separate trust domains.
- Harden the implemented local checkpoints and finite stream adapter into
  distributed leases, fencing, exactly-once/idempotent sinks, backpressure,
  state snapshots, plan amendments, and resume across worker/host failures.
- Apply independent task, macro-stage, and substep verification oracles.
- Store immutable attempts and receipts in an authenticated remote append-only
  evidence service or WORM backend; the local hash-chained journal is the
  replaceable reference protocol.

**Release gate:** a real task can be executed and replayed from a frozen plan
and receipt set.

## Phase 3 — search and learning (baseline implemented)

- Extend the current prior, interaction-weighted beam, exhaustive, and Pareto
  baseline with uncertainty-aware Bayesian, bandit, evolutionary, stability,
  and multi-fidelity route search.
- Learn contextual evidence without promoting one candidate to a universal
  winner.
- Preserve negative evidence, rejected routes, evidence freshness, and drift
  invalidation.
- Extend the campaign-ledger skeleton with diverse frontier selection,
  interleaved sequential promotion, focused outcome retrieval, and hardware-
  aware confirmation runs. The local paired-receipt bootstrap study is the
  reference fixed-allocation foundation, not a sequential causal engine.
- Support generated-node proposals only through quarantine, fixtures,
  sandboxing, and independent admission.

**Release gate:** real outcome evidence selects a measurably better valid route
without weakening contracts or authority.

## Phase 4 — federated universal scale

- Federate registries across languages, runtimes, tenants, and environments.
- Extend the implemented local composite/loop lowering with remote child-graph
  resolution, signed subgraph packs, and branch/join/subgraph topology mutations
  generated under explicit operator contracts. Linear typed mutation authoring
  is implemented locally.
- Add distributed scheduling, resource locality, effect-conflict controls,
  tenancy, authorization, usage accounting, and operational budgets.
- Benchmark across document extraction, web automation, image processing, data
  cleaning, ML pipelines, software engineering, and business workflows.
- Promote thin domain-pack cells one evidence gate at a time; prioritize human
  workflow recovery, enforcing security adapters, platform release examples,
  native integration adapters, and real operational evidence without treating
  catalog breadth as execution maturity.

**Release gate:** improvements reproduce across multiple real domains, task
classes, models, seeds, and environments.

## Non-negotiable invariants

- No architectural top-k candidate limit.
- No mixing of macro stages, atomic substeps, candidates, dimensions,
  contracts, policies, feedback, or optimization.
- No route edge moves backward or skips a required contract.
- No optimizer can legalize an ineligible candidate.
- No pass-through exists without an explicit compatibility certificate.
- No success claim relies only on the producing node's self-assessment.
- No benchmark claim substitutes fabricated or synthetic evidence for real
  execution when real execution is the stated target.
