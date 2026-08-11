---
name: benchmark-solution-graph
description: Design, run, audit, or report a Universal Node Graph route experiment. Use when an agent must compare valid graph configurations, select priors or random sprouts, allocate successive-halving budgets, stop weak routes early, run an explicit exhaustive sweep, preserve immutable receipts, choose Pareto-optimal primary and fallback routes, or make evidence-backed optimization claims.
---

# Benchmark a solution graph

Read `../../../BENCHMARK_PROTOCOL.md`,
`../../../TASK_AND_SOLUTION_PACK_PROTOCOL.md`,
`../model-solution-graph/references/experiments.md`, and
`../../../AGENT_PLAYBOOK.md` before designing the experiment.

## Establish the experiment

1. Freeze a validated `TaskContract`, independently identified `TaskOracle`,
   exact `TaskCaseSpec` splits, program digest, registry snapshot, node digests,
   environment, and budget.
2. Compile the admitted space before proposing routes. Invalid configurations
   are compiler rejections, not poor-scoring trials.
3. Select fixed control and fixed candidate arms plus bounded solver arms.
   Give every arm identical cases, seeds, repetitions, oracle, and runtime
   class. Reserve holdouts that cannot update the search policy.
4. Record quality, acceptance, cost, latency, reliability, policy, and resource
   objectives without hiding tradeoffs in an unexplained scalar.

## Allocate search

- Start with prior routes and seeded sprouts when the space is large.
- Use anchored mutation to explore around strong or diverse configurations.
- Use successive halving only on comparable completed observations and promote
  by an explicit metric and resource rung.
- Apply early stopping only with a declared direction, patience, minimum
  observations, and threshold or best-so-far reference.
- Use exhaustive mode only when explicitly requested and computationally
  feasible; never claim exhaustive coverage from a bounded sample.

## Report

Preserve immutable run receipts, seeds, failures, rejected routes, evaluated
routes, duplicates, heuristic skips, unvisited count, belief revision, and
best-so-far versus budget. Compare Pareto fronts and choose fallbacks for
dependency and failure-mode diversity as well as rank.

Call learned candidate effects observational unless randomized assignment or a
valid identification strategy supports a causal claim. Never call
self-optimization proven from synthetic fixtures or one benchmark task.
Treat `completed-no-accepted-route` as a valid outcome. Report per-arm
acceptance separately from report protocol completion. Claim optimality only
when exhaustive evidence covers the complete declared admitted space.

Before publication, validate a `SolutionPackManifest` whose closure exactly
matches the task, program, registry, node pack, cases, evaluator, baselines, and
benchmark suite used by the run. Publish JSON as the evidence authority and
HTML only as its human-readable projection.
