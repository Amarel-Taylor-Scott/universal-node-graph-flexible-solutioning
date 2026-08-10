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
- Full registry-to-slot admission handshake with an inspectable decision for
  every candidate/slot pair and n-ary configuration constraints.
- Negotiated registry discovery with sparse descriptors, exact named embedding
  spaces, graceful query fallback, coverage receipts, and closed-world snapshots.
- Portable node packs and a deterministic reference catalogue containing five
  node contracts and 18 cross-domain templates with 317 atomic obligations.
- Dependency-free template authoring CLI, strict linear-blueprint schema, and
  focused workspace skills for templates, node packs, and benchmarking.
- Prior-guided, beam, seeded-sprout, and uncapped exhaustive route search with explicit
  accounting for evaluated, rejected, skipped, and unvisited configurations.
- Successive-halving promotion and patience-based early stopping primitives.
- Immutable run receipts, Pareto comparison, observational belief fitting, and
  repository instructions for Codex, Claude, Gemini, Copilot, and other agents.

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

- Execute heterogeneous node runtimes in least-privilege sandboxes.
- Add content-addressed artifacts, checkpoints, bounded retries, fallbacks,
  circuit breakers, and explicit plan amendments.
- Apply independent task, macro-stage, and substep verification oracles.
- Store immutable attempts and receipts in an append-only evidence ledger.

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
- Support generated-node proposals only through quarantine, fixtures,
  sandboxing, and independent admission.

**Release gate:** real outcome evidence selects a measurably better valid route
without weakening contracts or authority.

## Phase 4 — federated universal scale

- Federate registries across languages, runtimes, tenants, and environments.
- Expand composite nodes into validated child graphs on demand.
- Add distributed scheduling, resource locality, effect-conflict controls,
  tenancy, authorization, usage accounting, and operational budgets.
- Benchmark across document extraction, web automation, image processing, data
  cleaning, ML pipelines, software engineering, and business workflows.

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
