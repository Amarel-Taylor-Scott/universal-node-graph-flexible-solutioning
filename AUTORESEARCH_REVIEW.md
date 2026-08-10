# AutoResearch and Cholesky review

Research date: 2026-08-10. This document records design inputs, not dependency
endorsements. Package identity, provenance, release state, licenses, and runtime
behavior must be rechecked before adoption.

## Identity corrections

- No PyPI distribution named `chloesky` was identified. Until a precise project
  URL is supplied, this repository treats the word as a likely reference to
  **Cholesky** factorization. The public `Chloesky` user/name results are not a
  numerical Python project.
- [Karpathy's `autoresearch`](https://github.com/karpathy/autoresearch) is a
  deliberately narrow GitHub experiment, not the generic execution kernel for
  this repository. Its important pattern is a small mutable surface, a fixed
  evaluator, a fixed resource budget, and a mechanical keep/discard loop.
- [`Auto-Research`](https://pypi.org/project/Auto-Research/) is an older,
  unrelated package. Similar names on PyPI do not imply common maintainership,
  compatible APIs, or a coordinated ecosystem.
- [AutoRA](https://autoresearch.github.io/autora/) is a separate automated
  empirical-science project. Its theorist/experimentalist decomposition is a
  useful taxonomy, not an implementation of Universal Node Graph.

## Project assessment

| Project | Verified useful idea | Framework decision |
|---|---|---|
| [Karpathy/autoresearch](https://github.com/karpathy/autoresearch) | One constrained mutable target, a fixed evaluator, one comparable metric, and a fixed five-minute budget | Reproduce the experiment contract as a template; do not depend on the repository |
| [`autoresearch-core`](https://pypi.org/project/autoresearch-core/) | Deterministic decision contracts that keep the model from grading its own work | Study or pilot behind an adapter; the strict core remains dependency-free |
| [`autoresearch-lab`](https://pypi.org/project/autoresearch-lab/) | Generic measurable pipelines, stopping conditions, commit/revert, and a candid Docker threat warning | Potential external runner for trusted code; do not treat Docker alone as an adversarial boundary |
| [`autoresearch-rl`](https://pypi.org/project/autoresearch-rl/) | Frozen preparation, mutable training, progress events, cancellation, resource pools, and hybrid proposal policies | Specialized runner/reference; keep RL and cloud assumptions outside the universal kernel |
| [GEPA](https://github.com/gepa-ai/gepa) | Pareto-aware population search and diagnostic side information for proposing textual changes | Optional candidate-generator policy; it cannot compile, admit, execute, or verify a graph |
| [GEAR](https://arxiv.org/abs/2605.13874) | A population DAG preserves alternative research states, novelty, ancestry, and crossover | The campaign ledger records multiple candidate lineages instead of only one incumbent |
| [Rehearse](https://arxiv.org/abs/2607.27687) | Late proposals benefit from retrieval of similar prior attempts and outcomes | Outcome retrieval is proposal context; it never replaces execution evidence or the oracle |
| [AutoMegaKernel](https://arxiv.org/abs/2606.09682) | Generated schedules pass static correctness gates before expensive execution | Generated nodes and plans enter quarantine, compile, and pass safety checks before benchmarking |
| [SkyPilot parallel AutoResearch](https://blog.skypilot.co/scaling-autoresearch/) | Parallel waves reveal interactions; heterogeneous hardware changes measured outcomes | Runner adapters may fan out, but receipts must fingerprint hardware and confirmation must use a declared reference class |
| [SkyPilot](https://docs.skypilot.co/) | Portable scheduling, queues, recovery, and heterogeneous compute | Candidate external scheduler; it must not own semantic validity or promotion policy |
| [Weco](https://github.com/WecoAI/weco-cli) and [AutoCrucible](https://pypi.org/project/autocrucible/) | Tree search, immutable evaluation surfaces, and bounded code optimization | Study as runner/policy references; do not make either a foundational dependency |

Young or similarly named `autoresearch-*` distributions are independent until
proven otherwise. Never co-install them in the framework environment merely
because their names match. Inspect wheel contents, top-level import names,
dependency locks, source/release provenance, license, evaluator visibility, and
permission flags in an isolated environment first.

## Consequences for the universal framework

The architecture uses five distinct layers:

1. **Semantic graph and registry** — typed obligations and all admitted atomic
   candidates.
2. **Compiler** — the only authority that can prove a route valid and freeze
   exact versions, digests, parameters, edges, and fallbacks.
3. **Proposal/search policy** — priors, beam, sprouts, Bayesian, evolutionary,
   reflective, or exhaustive mechanisms that decide what to try. A policy may
   change order and resource allocation only.
4. **Runner/scheduler** — local process, container, microVM, cluster, or remote
   execution. It cannot decide whether its own output is correct.
5. **Independent evaluator and evidence ledger** — immutable oracle identity,
   task/data split, environment/hardware identity, raw repetitions, metrics,
   failures, and promotion decisions.

`solutiongraph.campaign` adds the missing population-DAG and trust-boundary
records. `CandidateRecord` preserves seed, mutation, crossover, or agent
ancestry. `EvaluationBoundary` rejects candidate-writable evaluators and requires
microVM or remote isolation for explicitly untrusted candidate code; a plain
container remains useful lifecycle isolation, not an adversarial boundary.
`CampaignBudget` makes candidate, trial, failure, time, cost, concurrency,
fidelity, and seed limits explicit. These are skeleton contracts for an LLM
harness; they are not a security sandbox or distributed scheduler.

### Promotion rules

- Keep development cases and untouched holdout cases separate.
- Apply correctness and policy gates before measuring profitability.
- Preserve rejected, crashed, timed-out, and duplicate trials.
- Use paired or interleaved repetitions where order, load, or hardware drift
  can bias comparisons.
- Report uncertainty and minimum effect requirements; do not promote on a
  single noisy improvement.
- Maintain a Pareto frontier for quality, cost, latency, reliability, resource
  use, and policy instead of hiding tradeoffs in an unexplained scalar.
- Screen broadly at low fidelity, then confirm survivors on the reference
  fidelity and hardware class.
- Preserve several diverse strong candidates and failure-mode-diverse
  fallbacks; one greedy incumbent is not the whole learned state.

## Cholesky as a node family

Cholesky factorization is applicable only to a symmetric/Hermitian
positive-definite system. It should not be represented as one universal
`solve` node. The new `template.numerical-linear-system` exposes the decisions
and checks that make solver candidates interchangeable without making them
mathematically dishonest.

Useful implementations include:

| Need | Candidate implementation family | Important contract detail |
|---|---|---|
| Dense portable CPU | [NumPy `linalg.cholesky`](https://numpy.org/doc/stable/reference/generated/numpy.linalg.cholesky.html) or [SciPy `cho_factor`/`cho_solve`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.cho_solve.html) | Verify Hermitian/symmetric positive definiteness, finite inputs, dtype, residual, and conditioning |
| Batched GPU/autograd | [PyTorch `torch.linalg.cholesky_ex`](https://docs.pytorch.org/docs/stable/generated/torch.linalg.cholesky_ex.html) | Preserve batch/device/dtype; interpret per-matrix `info` instead of hiding failures |
| JIT/autodiff | [JAX Cholesky](https://docs.jax.dev/en/latest/_autosummary/jax.scipy.linalg.cholesky.html) | Preserve compilation/static-shape constraints and explicitly verify non-finite failure results |
| Sparse CHOLMOD | [`scikit-sparse`](https://pypi.org/project/scikit-sparse/) | External SuiteSparse and license/runtime requirements are part of the environment contract |
| Sparse tensor interop | [`cholespy`](https://pypi.org/project/cholespy/) | Factorization/solve device behavior, precision, sparse layout, and binary provenance are explicit |
| Rank update/downdate | [`cholrot`](https://pypi.org/project/cholrot/) | Alpha-stage capability; downdates require positive-definiteness checks and residual verification |
| Spatial covariance approximation | [`pyKoLesky`](https://pypi.org/project/pyKoLesky/) | Specialized approximation semantics and non-commercial licensing prevent silent general/product use |

Recommended atomic capabilities include matrix validation, structure
classification, SPD checking, conditioning, scaling, regularization, symbolic
analysis, ordering, numeric factorization, triangular solve, log determinant,
rank update/downdate, iterative refinement, residual/backward-error checking,
precision escalation, and QR/SVD/LDL fallback.

Do not form normal equations `X.T @ X` merely to unlock Cholesky for least
squares: doing so squares the condition number. QR or SVD candidates should be
available unless SPD structure and conditioning are independently established.

## Adoption gate for any external package

Before a harness proposes a package-backed node, record:

- exact distribution name, import name, version, source repository, release
  commit, license, wheel/sdist digest, and build provenance;
- resolved dependency and environment digests;
- runtime, device, dtype, schema, effects, permissions, network, filesystem,
  and secret requirements;
- evaluator visibility and candidate isolation;
- deterministic fixtures, failure taxonomy, timeouts, cancellation, and
  residual or outcome oracle;
- one alternative implementation and a safe fallback path.

Package popularity or semantic similarity can nominate a node. Only explicit
contracts, compiler admission, isolated execution, and independent evidence can
promote it.
