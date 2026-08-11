---
name: run-benchmark-arena
description: Run, extend, verify, or report the SolutionGraph benchmark arena. Use when an agent must compare fixed controls with bounded solver policies on identical task cases, seeds, repetitions, oracle, and runtime; preserve negative evidence; confirm holdouts; disclose route coverage; or generate JSON and self-contained HTML reports with an honest claim scope.
---

# Run the benchmark arena

Read `../../../BENCHMARK_PROTOCOL.md`,
`../../../TASK_AND_SOLUTION_PACK_PROTOCOL.md`, and
`../../../READINESS.md` before interpreting results.

## Inspect before allocating compute

1. Run `solutiongraph benchmarks show <benchmark-id>` and validate its linked
   solution pack.
2. Confirm task, program, registry, node-pack, cases, evaluator, seeds,
   repetitions, holdouts, source, license, and claim scope.
3. Inspect the exact route-count upper bound and every arm. Suggested anchors
   are priors, not evidence.
4. Use a candidate-inaccessible evaluator trust domain for genuine hidden data.
   Transparent repository fixtures are `mechanism-fixture` evidence.

## Execute

```bash
solutiongraph benchmarks run <benchmark-id> \
  --runtime subprocess \
  --artifact-dir .artifacts/<benchmark-id> \
  --receipt-journal .artifacts/<benchmark-id>.jsonl \
  --report-json .artifacts/<benchmark-id>.json \
  --report-html .artifacts/<benchmark-id>.html
```

Give every arm a fresh runtime state. Keep task cases, seeds, repetitions,
oracle, objectives, and runtime class identical. Preserve every accepted,
rejected, and failed receipt.

## Interpret

- Report protocol completion separately from per-arm route acceptance.
- Treat `completed-no-accepted-route` as valid bounded-search evidence.
- Check holdout confirmation only for routes selected without holdout learning.
- Disclose evaluated plans, total route upper bound, duplicates, constraints,
  heuristic skips, and unvisited space.
- Claim optimality only after complete exhaustive evaluation of the declared
  admitted snapshot.
- Call learned weights observational unless assignment identifies causality.
- Keep the JSON report authoritative; treat HTML as a projection.

Before broader claims, replace synthetic fixtures with representative licensed
data, multiple seeds/repetitions, isolated holdouts, controlled environments,
statistical uncertainty, and external confirmation.
