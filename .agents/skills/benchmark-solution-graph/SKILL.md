---
name: benchmark-solution-graph
description: Design, run, audit, or report a Universal Node Graph route experiment. Use when an agent must compare valid graph configurations, select priors or random sprouts, allocate successive-halving budgets, stop weak routes early, run an explicit exhaustive sweep, preserve immutable receipts, choose Pareto-optimal primary and fallback routes, or make evidence-backed optimization claims.
---

# Benchmark a solution graph

Read `../model-solution-graph/references/experiments.md` and
`../../../AGENT_PLAYBOOK.md` before designing the experiment.

## Establish the experiment

1. Freeze the task contract, independent oracle, program digest, registry
   snapshot, node digests, environment, dataset/case identities, and budget.
2. Compile the admitted space before proposing routes. Invalid configurations
   are compiler rejections, not poor-scoring trials.
3. Select a fixed baseline and representative development cases. Reserve
   holdout cases that cannot update the search policy.
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
