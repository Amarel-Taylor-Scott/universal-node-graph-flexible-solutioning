# Universal Node Graph Specification

Status: research preview 0.2
Normative core package: `solutiongraph`
Concrete adapter and stress test: `browsergraph`

This document defines a domain-neutral programming model in which a problem is
expressed as typed semantic obligations, each obligation admits multiple atomic
implementations, a compiler proves that a selected configuration is runnable,
and an optimizer learns which valid configuration to evaluate next.

The words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** indicate conformance
requirements.

## 1. The universality claim, stated precisely

Universal Node Graph is intended for any system that can be described as
components exchanging typed values under explicit control and state rules. That
includes ordinary DAGs, workflows, build systems, data and ML pipelines,
services, agents, browser automation, image processing, distributed jobs, and
structured control flow.

It does not claim that every program is a finite static DAG. Iteration,
branching, streaming, long-running services, and state machines are represented
as typed structured or composite nodes with nested graphs. The graph at each
compilation level remains analyzable; arbitrary backward edges are not used as
an informal substitute for loop semantics.

It also does not solve undecidable problems, automatically discover a perfect
decomposition, or prove arbitrary postconditions. “Universal” describes the
composition and experimentation model—not magical omniscience.

## 2. The non-negotiable separation of representations

An implementation is conforming only if it keeps these objects distinct:

| Representation | Question answered | May contain learned scores? |
|---|---|---:|
| Task contract | What outcome is required, under what constraints, and who verifies it? | No |
| Task cases and oracle identity | Which immutable inputs/splits are evaluated, and what exact evaluator decides acceptance? | No |
| Semantic program graph | What obligations and data/control dependencies define the solution? | No |
| Node registry | What exact implementations and parameter bindings exist? | No |
| Admitted candidate space | Which candidates satisfy each obligation, and why was each rejected or admitted? | No |
| Belief model | Which valid choices currently look promising, with what evidence and uncertainty? | Yes |
| Frozen execution plan | Which exact implementations, versions, digests, and parameters will execute? | No |
| Run receipt / evidence ledger | What actually ran and what was observed? | Observations only |
| Solution-pack manifest | Which exact task, programs, registries, node packs, cases, evaluator, baselines, and suites form the portable closure? | No |
| Benchmark suite/report | Which controlled arms were allocated, and what did each observe under the declared claim scope? | Allocation: no; report: observations only |

The optimizer MUST NOT change program meaning, grant authority, coerce a type,
or make an invalid configuration valid. It proposes configurations only inside
the space admitted by the compiler.

This is the architectural center of the project. Mixing any two rows above
creates hard-to-reproduce behavior and lets “optimization” silently rewrite the
program it is supposed to measure.

## 3. Core entities

### 3.1 Task contract

A task contract states:

- task identity and version;
- typed external inputs and outputs;
- a success contract and an independent acceptance oracle;
- permitted effects, granted permissions, and resource/policy limits;
- evaluation cases, including holdout cases when learning is involved;
- objectives and hard constraints.

A natural-language goal is documentation, not a verifier. Acceptance MUST be
recorded independently of a candidate's self-report whenever a meaningful
independent check is possible.

### 3.2 Semantic slot

A semantic slot is one obligation in the program. It defines purpose, typed
ports, success contract, required capabilities, allowed effects, and its place
in a group/submatrix. A slot is not an implementation.

Slot kinds in version 0.2 are `atomic`, `composite`, `branch`, `loop`, `map`,
`reduce`, and `barrier`. A composite slot references another semantic graph.

A data-dependent slot MAY declare an activation source output and a nonempty
set of string values. All three fields—source slot, source port, and values—are
atomic: a partial activation rule is invalid. An inactive slot emits a
`skipped` node receipt and no outputs. A conditional output MUST feed either a
consumer whose guard implies the producer's guard or an optional input on an
explicit merge. It MUST NOT directly provide a required graph output.

`composite` and `loop` slots MUST reference a child graph. Before ordinary
compilation, `StructuredCompiler` deterministically expands the child into
namespaced atomic slots. A loop additionally requires an explicit finite
iteration bound and feedback mapping for every child input. Loop-invariant
values are carried explicitly in the state envelope; hidden captures are not
allowed. `map`, `reduce`, and `barrier` remain semantic obligations whose
runtime behavior is supplied by admitted nodes unless a future version defines
a separate lowering protocol for them.

Slots SHOULD be atomic enough that two candidates in the same slot are genuine
substitutes. If candidates perform materially different sequences, permissions,
or success conditions, the slot is too large and SHOULD be decomposed into a
subgraph.

### 3.3 Node definition

A node definition is a versioned implementation contract. The required ABI is:

| Field | Meaning |
|---|---|
| Stable ID and version | Semantic implementation identity |
| Implementation digest | Content identity of executable code/artifact |
| Inputs and outputs | Named nominal types, versions, schemas, units, cardinality |
| Parameters | Valid bindings, defaults, enumerated choices when finite |
| Runtime and entrypoint | How an executor locates the implementation |
| Capabilities | What obligation the node can satisfy |
| Effects | Observable state it may read or change |
| Permissions | Authority required to perform those effects |
| Determinism | Deterministic, seeded, recorded, or nondeterministic |
| Idempotency | Retry semantics |
| Preconditions/postconditions/invariants | Behavioral contract |
| Failure modes | Stable taxonomy and retryability |
| Resource claims | Expected or hard resource envelope |
| Verifier reference | Optional node-level verifier |

Empirical quality, latency, or success scores MUST NOT live in the node ABI.
Those values change with workload and time and belong in a belief/evidence
overlay.

#### 3.3.1 Discovery sidecars and portable node packs

A node MAY have sparse, independently versioned `NodeDescriptor`,
`SearchDocument`, and `EmbeddingRecord` sidecars. They can describe purposes,
solutions, actions, domains, examples, and ABI-port meanings through any number
of search views. They MUST identify the exact `NodeSpec` digest and MUST NOT add
capabilities, types, effects, or permissions to it.

Every embedding declares an exact space identity including model/revision,
representation kind, dimensions, distance, normalization, and scalar type.
Equal dimensions alone are not compatibility. Missing discovery fields or
embeddings never make an otherwise valid node invalid.

A `NodePackManifest` is a content-addressed distribution record for node,
descriptor, embedding, artifact, and dependency digests. Core wire objects are
strict; forward-compatible metadata is confined to namespaced `extensions`.
See `NODE_REPOSITORY_PROTOCOL.md` for the normative discovery flow.

### 3.4 Candidate

A candidate is one concrete binding of one node version and implementation
digest. A model family with six model choices and three strategies is eighteen
visible candidates, not one card with hidden internal choices.

### 3.5 Edge and port

An edge connects one named output port to one named input port. Types are
nominal and versioned. Schema digests and units participate in compatibility.
The compiler performs no implicit coercion. A conversion is a visible adapter
node with its own contract, cost, effects, tests, and receipts.

Cardinality (`one`, `optional`, `many`, `stream`) is part of the ABI. Fan-in to a
single-value port is invalid unless an explicit merge node exists.

### 3.6 Topology family

A topology family is a versioned collection of complete `ProgramGraph`
alternatives that satisfy one task and success contract. Each variant declares
its rationale, prior weight, optional parent, and explicit topology operators.
Topology search MUST validate and admit every variant independently. Node-route
counts, topology exclusions, heuristic skips, and unvisited space MUST be
reported separately; an optimizer cannot smuggle an unvalidated graph rewrite
inside a node-selection proposal.

### 3.7 Task cases, oracle, and solution pack

A `TaskCaseSpec` content-addresses one immutable input and declares whether it
belongs to development, validation, holdout, or stress evaluation. Loaded input
bytes MUST match the declared digest. Holdout observations MUST NOT update the
proposal policy that selected the route being confirmed.

A `TaskOracle` identifies evaluator kind, implementation digest, implementation
reference, independence, and candidate readability. Read-only access is still
readability. A confidential holdout evaluator MUST live outside the candidate's
trust domain.

A `SolutionPackManifest` is an exact content-addressed closure over one task and
its programs, registry snapshots, node packs, task cases, evaluator, fixed
baseline plans, benchmark suites, and external artifact references. Closure
validation MUST reject both missing and undeclared assets. Readiness labels
describe implementation state; they do not imply performance or certification.
See `TASK_AND_SOLUTION_PACK_PROTOCOL.md`.

### 3.8 Benchmark suite and report

A benchmark suite defines fixed-route and bounded solver arms, exact task/case/
program/registry identities, common seeds and repetitions, holdout cases,
dataset source/license, and claim scope. Mutable runtime state MUST NOT leak
between arms. An arm that completes without an accepted route is valid negative
evidence.

A benchmark report distinguishes protocol completion, per-arm acceptance,
evaluated plans, total receipts, champion observations, route-space coverage,
holdout confirmation, Pareto/fallback identities, and exhaustive optimality.
Only complete evaluation of the declared admitted space may prove optimality
over that space. See `BENCHMARK_PROTOCOL.md`.

## 4. Compilation

A conforming compiler performs these passes in order:

1. Validate the task and semantic graph schemas.
2. Resolve all slots and ports and reject dangling references.
3. Check port producer counts and nominal type compatibility.
4. Check activation sources and reject conditional outputs that can be absent
   where a required value is promised.
5. Reject cycles at the current level; require structured control nodes.
6. Lower referenced composites and explicitly bounded loops when present.
7. Validate every node and candidate in the registry.
8. Consume an immutable discovery-receipt-backed registry snapshot.
9. Perform full admission for every slot and candidate in that snapshot.
10. Emit an admission decision for every examined pair, including rejection reasons.
11. Apply explicit n-ary configuration constraints.
12. Require exactly one admitted candidate per slot for a concrete route.
13. Freeze exact node versions, implementation digests, parameters, registry digest,
    program digest, topology, and edges into a content-addressed plan.

Compiler validity and optimizer profitability are separate functions. A route
that compiles with a low score is valid. A route with a high score that fails a
contract is invalid.

The current `solutiongraph.Compiler` and `StructuredCompiler` implement these
passes for the 0.2 semantic model.
Diagnostics use stable `UNG-*` codes and are collected before raising so humans
and coding agents can correct multiple defects in one pass.

## 5. Discovery coverage, candidate completeness, and exclusions

The global set of independently published nodes may be open, federated, and
unbounded. A harness first negotiates query and schema capabilities, records a
replayable discovery query and coverage receipt, and freezes the results into a
closed-world registry snapshot. An incomplete query preserves its continuation
token or explicit coverage note; it MUST NOT be called globally complete.

Within that immutable snapshot, compiler admission examines every registered
candidate for every slot. There is no architectural top-k. Each pair produces
an `AdmissionDecision`.

Search budgets may limit which admitted routes are evaluated, but they MUST NOT
make candidates disappear from the registry or viewer. Any policy exclusion
MUST be explicit, attributable, versioned, and distinguishable from a technical
contract rejection.

This distinction lets a user answer three different questions:

1. What implementations exist?
2. Which implementations are technically and legally runnable here?
3. Which runnable configurations did this experiment actually evaluate?

## 6. Search and self-optimization

The search problem starts only after admission. For a selection (r), the
initial factorized belief can be represented as:

```text
score(r | task, context) =
    sum candidate_prior(slot, candidate)
  + sum interaction_prior(candidate_i, candidate_j)
  + sum learned_subgraph_factors(r)
```

Hard constraints are not score penalties; they remove invalid configurations.
Scores MUST carry a belief revision and SHOULD carry evidence counts and
uncertainty.

Required search modes are:

- **Prior route:** fastest useful configuration; greedy width-one search.
- **Bounded anytime search:** beam/best-first search with an explicit budget.
- **Seeded sprout search:** unique random configurations, optionally mutated
  around full or partial starting routes, with explicit attempt/evaluation/
  mutation budgets.
- **Adaptive experiment search:** allocate partial budgets, stop poor trials,
  and update beliefs from receipts.
- **Exhaustive search:** enumerate every feasible configuration without a hidden
  cap when the user supplies sufficient compute.

The 0.2 implementation provides prior, beam, seeded sprout, executed
successive-halving, patience-based early stopping, alternative-topology search,
and exhaustive primitives. Exhaustive iteration
is streaming through `SearchEngine.iter_exhaustive`. `SearchReport`
records the Cartesian upper bound, evaluated routes, constraint-eliminated
routes, heuristic-skipped routes, unvisited routes, belief revision, budget,
sampling attempts/duplicates/invalid samples where applicable, and whether
optimality was actually proven.

“Best” SHOULD default to a Pareto set across quality, cost, latency,
reliability, policy, and resource objectives. A scalar weighted score is a
user-selected projection, not objective truth.

## 7. Evidence, learning, and experiments

Every execution emits an immutable receipt containing:

- frozen plan and semantic program digests;
- task case, input and environment digests;
- exact slot-to-candidate assignments;
- seed and determinism mode;
- start/end state, outcome, failure class, and node-level receipts;
- measured metrics and artifact digests;
- verifier identity and acceptance result;
- belief revision that proposed the route.

Receipts are append-only. Corrections create new provenance-linked records; they
do not rewrite history.

A credible benchmark includes:

- a fixed baseline/control route;
- representative train, validation, and holdout task cases;
- repeated seeds for stochastic nodes;
- equal resource accounting and explicit early-stopping rules;
- independent acceptance checks;
- best-so-far versus cost/time curves, not only final winners;
- failure taxonomy and fallback recovery rate;
- route-space coverage and optimizer regret when ground truth is available.

The current evidence module supplies immutable ledgers, experiment design,
aggregate means/variances, Pareto fronts, and smoothed success priors. Learned
candidate priors are explicitly named **observational**: correlated success is
not a causal estimate of the candidate's effect. Causal claims require controlled
assignment or another defensible identification strategy.

When an LLM harness generates or mutates nodes, bindings, or graph structure,
the experiment MUST additionally freeze a campaign budget and evaluator
boundary before the first proposal. Every compiled proposal MUST preserve its
parents, proposal operator, hypothesis, proposer identity, and proposal digest
in an append-only population DAG. Generated code MUST NOT write the evaluator;
hidden cases MUST be outside the candidate-readable trust domain. Retrieval of
similar past outcomes and model predictions MAY guide proposal order but MUST
NOT replace execution evidence, compiler admission, or independent acceptance.

## 8. Fallbacks

The second-highest score is not automatically the best fallback. A fallback
portfolio SHOULD balance:

- acceptance probability;
- transition cost and warm-up time;
- different failure classes and infrastructure dependencies;
- authority and policy compatibility;
- state/checkpoint compatibility;
- evidence quality and uncertainty.

Two routes that share the same brittle provider, parser, or deployment region
may fail together. Diversity must therefore be measured at node, dependency,
effect, and failure-class levels.

## 9. Determinism, replay, and effects

Pure deterministic nodes are easiest to cache and reproduce. Seeded nodes MUST
record the seed. Recorded nodes MUST capture the nondeterministic decision or
external response required for replay. Nondeterministic nodes MUST say so and
be evaluated statistically.

External calls, clocks, random values, human input, and model invocations are
effects. They MUST cross declared capability/permission boundaries and MUST be
visible in receipts. Content hashes identify code and declared inputs; they do
not by themselves guarantee reproducibility when undeclared state leaks in.

## 10. LLM nodes

LLMs are ordinary nondeterministic or recorded nodes, not privileged
orchestrators outside the graph. An LLM node MUST declare model/provider
identity, prompt/template digest, tool authority, structured output type,
sampling configuration, context inputs, and failure modes.

LLM output is untrusted data until schema validation and the relevant success
oracle accept it. A node MUST NOT grade its own consequential output when an
independent verifier can be used.

## 11. Conformance levels

- **Level 0 — Described:** strict node and program schemas.
- **Level 1 — Compilable:** full registry admission, typed edges, authority checks,
  structured diagnostics, and frozen plan digest.
- **Level 2 — Reproducible:** exact artifacts/environment, replay rules, and
  immutable receipts.
- **Level 3 — Experimental:** explicit search budgets, baselines, repeated cases,
  Pareto metrics, and coverage reporting.
- **Level 4 — Adaptive:** learned priors with uncertainty, safe rollout, drift
  detection, diverse fallbacks, reversible promotion, and preserved candidate
  lineages for generated-graph campaigns.

This repository implements Level 1 as a general Python core and now includes a
trusted-local Level 2 reference slice: admitted-space-bound frozen plans,
content-addressed memory/file artifacts, implementation-digest checks, bounded
retry, frozen fallbacks, independent verification, receipts, and five
notebook families within 24 executable domain programs. Version 0.6 also adds
portable task/solution-pack closure and controlled benchmark evidence. The
bundled Python adapter is in-process and is not
a least-privilege sandbox, durable crash-replay engine, or production Level 2
claim. Version 0.3 also includes a bounded subprocess lifecycle adapter and a
hash-chained local receipt journal; neither is an adversarial sandbox,
authenticated remote ledger, or crash-resumable scheduler. BrowserGraph remains
the richer browser runtime proof, not the definition of the architecture. See
`EXECUTION_PROTOCOL.md` and `READINESS.md` for the exact boundary.

## 12. Definition of done for a new domain

A domain adapter is not complete until it can demonstrate all of the following:

1. A task can be decomposed without domain logic leaking into the core compiler.
2. At least two genuinely interchangeable candidates exist for multiple slots.
3. Every candidate has a strict ABI and content identity.
4. Invalid types, permissions, effects, cycles, and configurations fail before execution.
5. A valid route freezes to a stable plan digest.
6. Prior, bounded, and exhaustive search agree on validity and disclose coverage.
7. Receipts permit independent replay/analysis.
8. A benchmark can compare routes, select a Pareto front, and identify a diverse fallback.
9. A solution pack exactly closes over task, cases, oracle, programs,
   registries, node packs, baselines, and benchmark suites.
10. An agent can implement the adapter by following the repository instructions
   without inventing hidden steps or conflating slots with candidates.
