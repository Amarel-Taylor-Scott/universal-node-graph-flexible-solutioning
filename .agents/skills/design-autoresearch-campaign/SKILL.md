---
name: design-autoresearch-campaign
description: Design, implement, or operate a bounded LLM-generated Universal Node Graph improvement campaign. Use when a coding harness must propose or mutate nodes, routes, graph structures, prompts, parameters, or code over repeated experiments; preserve a population and ancestry; retrieve prior outcomes; isolate generated code; freeze an independent evaluator; allocate multi-fidelity compute; or promote candidates without letting the agent grade its own work.
---

# Design an AutoResearch campaign

Read `../../../AUTORESEARCH_REVIEW.md`, `../../../EXECUTION_PROTOCOL.md`, and
`../model-solution-graph/references/experiments.md`. This skill governs the
proposal/evaluation loop; it does not weaken node, graph, or compiler rules.

## Freeze the boundary

1. Define the task, typed outputs, development cases, untouched holdout cases,
   objectives, hard constraints, and minimum meaningful effect.
2. Freeze evaluator, dataset/split, environment, registry snapshot, program,
   and admitted-space digests before evaluating generated candidates.
3. Create an `EvaluationBoundary`. Candidate code never writes the evaluator.
   Hidden cases require a candidate-unreadable evaluator. Untrusted generated
   code requires microVM or remote isolation; a subprocess or plain container
   alone is not an adversarial security boundary.
4. Create a `CampaignBudget` covering candidates, trials, failures, wall time,
   cost, concurrency, fidelity rungs, and seed. No loop is unbounded.

## Build a population DAG

- Represent each compiled seed or generated plan as a `CandidateRecord`.
- Preserve all parents, proposal operator, hypothesis, proposer/model identity,
  proposal artifact digest, belief revision, and generation.
- Keep multiple strong or novel lineages. Do not reduce the campaign to a
  single greedy incumbent.
- Retrieve similar prior attempts and their outcomes to inform proposals, but
  never substitute retrieval or an LLM prediction for execution evidence.
- Treat merge/crossover as a new child. Recompile the complete child graph;
  compatibility is not inherited from either parent.

## Generate safely

1. Generate one focused change or an explicitly described crossover.
2. Store generated code and manifests in quarantine with immutable digests.
3. Run schema, type, graph, authority, effect, license, provenance, fixture,
   and static safety gates before execution.
4. Compile only against the stated closed-world registry snapshot. An optimizer
   cannot admit a node or legalize an invalid route.
5. Record invalid, duplicate, rejected, crashed, timed-out, and policy-blocked
   proposals; failures are searchable evidence.

## Allocate experiments

- Use priors, seeded sprouts, beam search, or diverse population sampling for a
  quick first solution. Reserve exhaustive mode for explicit feasible sweeps.
- Screen broadly at low fidelity and use successive halving or another declared
  scheduler to promote survivors.
- Use parallel waves to learn interactions, while recording queue order,
  hardware class, load context, and environment digest.
- Confirm finalists with paired or interleaved repetitions on the reference
  hardware/fidelity. Keep development results separate from clean holdouts.
- Preserve raw metrics and uncertainty across quality, cost, latency,
  reliability, policy, and resource objectives. Maintain the Pareto frontier.

## Decide independently

The evaluator emits immutable `RunReceipt` records. Append a
`CampaignDecision` only with an explicit reason and receipt IDs. Promote only
after correctness and policy gates pass, repetitions meet the declared
confidence/effect contract, and holdouts remain clean. Select fallbacks for
failure-mode and dependency diversity, not merely second-best average score.

Never let candidate code change the metric, test data, reference outputs,
timers, resource accounting, or promotion rule. Never claim self-optimization
from the synthetic fixtures in this repository; they demonstrate mechanisms.

## Deliver

Return the frozen winning plan, diverse fallback plans, campaign ledger,
complete evidence ledger, search accounting, Pareto comparison, environment
and hardware identities, retained negative evidence, and a replay command.
State what remains unvisited and which conclusions are observational.

For numerical solver campaigns, use `template.numerical-linear-system` and keep
SPD checks, conditioning, factorization, solve, residual verification,
precision escalation, and QR/SVD/LDL fallbacks as separate atomic obligations.
