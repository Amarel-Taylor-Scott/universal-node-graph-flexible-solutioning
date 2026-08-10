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

## Phase 1 — compiler and registry handshake

- Add explicit `TaskSpec`, `MacroStageSpec`, `SubstepSpec`, `RoutePlan`, and
  frozen `ExecutionPlan` intermediate representations.
- Add version- and capability-aware registry negotiation.
- Record discovery coverage and unexplored candidate regions.
- Materialize large parameter spaces lazily while preserving exact counts and
  deterministic generation rules.

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

## Phase 3 — search and learning

- Add uncertainty-aware Bayesian, bandit, evolutionary, Pareto, stability, and
  interaction-aware route search.
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
