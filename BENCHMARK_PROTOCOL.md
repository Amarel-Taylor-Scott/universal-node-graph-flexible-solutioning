# Benchmark protocol

Status: normative for SolutionGraph benchmark model version `0.1`.

The benchmark protocol compares fixed routes and bounded search policies while
holding the task, cases, oracle, program, registry, seeds, repetitions, and
runtime class constant. Its purpose is to produce auditable evidence—not to
turn one successful run into a universal optimization claim.

## 1. Benchmark unit

A `BenchmarkDefinition` binds five layers:

1. `BenchmarkSuite`: portable allocation and claim contract;
2. `TaskContract`: stable definition of success;
3. `TaskCaseSpec[]`: immutable public or private case identities;
4. runtime `ExperimentCase[]`: inputs plus independently identified verifiers;
5. one executable example: program, registry, routes, policy, and objectives.

Validation requires exact task/program/registry/case/oracle identity. A benchmark
MUST fail before execution when any declared digest does not match the bound
object.

## 2. Claim scopes

Every suite declares exactly one scope:

| Scope | Permitted interpretation |
|---|---|
| `mechanism-fixture` | Demonstrates compilation, execution, search, verification, and reporting on transparent fixtures. |
| `internal-dataset` | Supports claims only for the identified internal sample and protocol. |
| `public-benchmark` | Supports claims only for the named public benchmark, version, split, and rules. |
| `production-shadow` | Supports claims for identified shadow traffic under its operational and statistical protocol. |

Moving to a stronger scope requires new data, evaluator, and suite identities.
It is not a metadata edit. The six bundled suites are `mechanism-fixture`
examples and explicitly do not prove domain superiority.

## 3. Arms

An arm is an allocation strategy, not a semantic step in the graph.

- `fixed-route` executes one named, pre-frozen control or candidate route.
- `solver-profile` runs one explicit bounded SolutionGraph policy.

Fixed controls establish whether search adds value. Solver arms disclose their
route-count upper bound, evaluated plan count, seeds, receipts, and unvisited
space. Suggested or anchor routes are recorded priors; they neither enter the
frozen plan nor count as learned evidence until executed.

All arms MUST receive the same declared case set, seeds, repetitions, task
oracle, and objective definitions. Runtime state such as circuit-breaker history
MUST NOT leak from one arm into another.

## 4. Cases and holdouts

Development observations may guide route proposals. Validation observations may
guide declared promotion rules. Holdout observations confirm only the selected
shortlist and MUST NOT update the policy that created that shortlist.

For stochastic work, use multiple recorded seeds and sufficient repetitions.
Use paired or interleaved execution when environment drift could dominate the
effect under study. Record environment and hardware identity. A latency result
from one machine is not a portable speed claim.

Transparent examples MAY expose their verifier and expected behavior, but MUST
set `candidate_readable=true`. Hidden evaluation requires inaccessible case and
oracle artifacts in a separate trust domain.

## 5. Result semantics

Each `BenchmarkArmResult` separates:

- `evaluated_plan_count`: distinct plans allocated by that arm;
- `receipt_count`: all execution observations retained;
- `champion_run_count`: runs supporting the selected aggregate;
- `accepted_runs`: accepted observations for that aggregate;
- objective means and variances;
- holdout confirmation;
- Pareto and fallback plan identities;
- whether exhaustive optimality was actually proven.

`completed-no-accepted-route` is a valid experimental outcome. It means the arm
finished its declared allocation without finding an eligible route. It is not a
framework crash and MUST NOT be rewritten as success.

`BenchmarkReport.ok` means every arm completed its protocol without structural
errors. It does not mean every arm found an accepted route.

## 6. Optimality and self-optimization claims

Only a complete exhaustive evaluation of the declared admitted space may claim
optimality over that space. The claim MUST still name the task, registry
snapshot, cases, oracle, objectives, environment, and time boundary.

A bounded solver may claim:

- it found an accepted route under a stated budget;
- its selected route outperformed a fixed control on stated observations;
- it improved best-so-far evidence over its allocation sequence;
- it left an exact number of routes unvisited.

It may not claim the globally best route. Learned node or interaction weights
are observational unless the experiment design supports causal attribution.

“Self-optimizing” therefore means a closed feedback loop that proposes only
valid routes, measures them with a fixed oracle, updates a new belief revision,
and preserves all evidence. It does not mean uncontrolled self-modification.

## 7. Minimum credible comparison

A publishable suite SHOULD contain:

- at least one fixed control;
- at least one stronger fixed candidate;
- at least one bounded solver arm;
- more than one representative case;
- a holdout or explicitly documented reason none exists;
- recorded seeds and repetitions;
- hard acceptance plus multiple objectives;
- negative and failed receipts, not only winners;
- exact task, program, registry, evaluator, environment, and dataset identities;
- a clear claim scope, license, source, and limitations.

Real external claims additionally need representative licensed data, a clean
holdout, statistical uncertainty, environment control, evaluator isolation,
and confirmation by someone or something outside the candidate-producing path.

## 8. Run the bundled arena

```bash
solutiongraph benchmarks list
solutiongraph benchmarks show benchmark.stdlib-data-quality
solutiongraph benchmarks run benchmark.stdlib-data-quality \
  --runtime subprocess \
  --artifact-dir .artifacts/stdlib-benchmark \
  --receipt-journal .artifacts/benchmark-receipts.jsonl \
  --report-html .artifacts/stdlib-benchmark.html \
  --report-json .artifacts/stdlib-benchmark.json
solutiongraph benchmarks run-all --report-dir .artifacts/benchmark-arena
```

The standard-library benchmark admits exactly 1,728 routes across seven atomic
columns. Its quick policy deliberately demonstrates that a very small budget
can miss every accepted route; its anchored balanced policy finds an accepted,
holdout-confirmed route without claiming exhaustive optimality. This is a
mechanism test of bounded search and honest failure reporting.

## 9. Report publication

Publish the machine-readable JSON report as the evidence authority. An HTML
viewer is a projection for humans. It MUST display:

- claim scope and explicit limitation;
- task, suite, report, program, and registry identities;
- each arm and its allocation;
- accepted/rejected/failed counts;
- selected route from left to right;
- route-space upper bound and evaluated fraction;
- holdout and optimality status;
- raw supporting evidence or a content-addressed reference.

Never omit an unsuccessful arm from the report. Never compare arms that used
different cases or oracles without labeling the comparison non-controlled.

## 10. Extending to Kaggle and other real tasks

For a Kaggle competition, freeze competition/data version, folds, target,
metric implementation, leakage rules, submission format, and a local holdout.
Model preprocessing, feature construction, model family, calibration,
ensembling, and output validation as separate atomic columns. Use the public
score only as an external observation; do not repeatedly tune on the public
leaderboard and call it a clean holdout.

The same protocol applies to scraping, address verification, document
extraction, data quality, image assurance, forecasting, entity resolution,
repository repair, scheduling, compliance, and service workflows. Only task
contracts, cases, nodes, and objectives change.

Reference models live in `solutiongraph/benchmarking.py`; bundled suites live in
`solutiongraph/benchmark_library.py`; strict schemas live in
`solutiongraph/schemas/benchmark-suite.schema.json` and
`benchmark-report.schema.json`.
