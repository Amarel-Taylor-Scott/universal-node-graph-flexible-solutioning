# Universal engineering system

SolutionGraph is a domain-neutral compiler, experiment, and evidence control
plane. It is not an AI/ML pipeline with a few unrelated examples attached.
Data science, browser automation, APIs, incident response, documents, human
workflows, and LLM evaluation are domain packs over the same typed graph model.

This guide is the shortest route to the universal layer added after the Taedri
comparison and the repository-wide review. It explains what is executable,
what is only projected, how coverage is derived, and how to add a domain
without changing the core ontology.

## The reusable model

Every engineering task is described through four independent layers:

1. A `TaskContract` fixes inputs, outputs, success, objectives, effects,
   permissions, cases, and an independent oracle.
2. Universal obligations identify *what must be true* without prescribing a
   tool, implementation, or industry.
3. A domain pack chooses relevant obligations, standards, questions, and exact
   repository assets.
4. A semantic program and admitted registry provide the executable graph and
   candidate implementations.

This separation matters. A question, template, adapter profile, node, admitted
route, benchmark receipt, and production observation are different evidence
classes. None is silently promoted into another.

### Fourteen obligations

| Obligation | Design concern |
|---|---|
| Acquire | Source, snapshot, freshness, authority, and consent |
| Decode | Format, encoding, version, malformed-input policy |
| Validate | Independent precondition and invariant checks |
| Normalize | Canonical form, locale, units, and loss policy |
| Transform | Reversibility, state, fit/apply boundaries, and leakage |
| Enrich | Authority, vintage, match policy, confidence, and provenance |
| Reconcile | Conflict, precedence, tolerance, abstention, and escalation |
| Decide | Evidence, authority, threshold, abstention, and appeal |
| Persist | Consistency, idempotency, retention, encryption, and lineage |
| Serve | API, event, UI, file, latency, and compatibility contract |
| Verify | Independent rejection of plausible but incorrect results |
| Observe | Traces, metrics, logs, lineage, privacy, and alerts |
| Recover | Retry, compensation, checkpoint, rollback, and terminal failure |
| Govern | Owner, policy, approval, evidence, retention, and audit boundary |

The catalog lives in `solutiongraph/universal/catalog.py`. These are obligation
families, not a required 14-stage linear pipeline. A graph can branch, join,
lower a bounded loop, select a subset, or instantiate an obligation more than
once when the task contract requires it.

## Domain packs

The reference catalog contains 13 curated views:

| Domain pack | Current lowest evidence level | Typical work |
|---|---:|---|
| Data integration and quality | C5 | ingest, clean, validate, enrich, merge |
| Backend services and APIs | C5 | contracts, idempotency, effects, serving |
| Event and streaming systems | C5 | event time, windows, lateness, retractions |
| Platform and release engineering | C2 | build, release, progressive delivery |
| SRE and incident response | C5 | observe, diagnose, mitigate, recover |
| Security, privacy, and compliance | C1 | policy gates, evidence, approvals |
| Frontend and browser systems | C5 | journeys, rendering, release checks |
| Database and storage systems | C5 | migration, consistency, persistence |
| Business and human workflows | C0 | human tasks, escalation, compensation |
| Documents, images, and media | C6 | extraction, rendering, quality checks |
| Scientific computing and optimization | C5 | numerical routes, search, verification |
| AI and machine learning | C6 | data, training, evaluation, release |
| LLM and agent systems | C5 | harnesses, judging, red teaming, promotion |

The levels above are generated from checked-in evidence, not hand-maintained
badges. Run the current assessment rather than copying this table:

```bash
solutiongraph universal domains
solutiongraph universal show domain-pack.backend-api
solutiongraph universal coverage
solutiongraph universal coverage --json
```

The reference snapshot currently contains 9 strong, 24 thin, 1 catalog-only,
4 blocked, and 1 empty capability cell. Those visible gaps are intentional.
For example, a BPMN structural projection is not evidence of a durable human
workflow runtime, and a policy checklist is not evidence of hostile-code
isolation.

### Evidence ladder

Coverage is computed through contiguous gates:

| Level | Required evidence |
|---|---|
| C0 | No cataloged capability |
| C1 | Capability declaration exists |
| C2 | Every declared template, question pack, adapter, and example resolves |
| C3 | Referenced executable examples compile |
| C4 | Compiled examples admit at least one route |
| C5 | At least one example admits a genuine implementation choice |
| C6 | Referenced benchmark or agent-benchmark evidence resolves |
| C7 | Referenced operational evidence resolves |

Later evidence cannot skip an earlier gate. The repository ships no C7 claim:
local fixtures and mechanism benchmarks are not production observations.

## Intelligent task context and historical starts

Taedri demonstrates the value of task-family profiles, capability manifests,
effort arms, strategy forks, route history, negative results, and
content-addressed receipts. SolutionGraph generalizes those ideas through ten
independent fingerprint channels:

| Channel | Examples |
|---|---|
| Outcome | success contract, objective direction, hard constraints |
| Interface | input/output types, schema digests, media types |
| Workload | cases, scale signals, external requirements |
| Topology | domain packs, obligations, classified task categories |
| Effects | allowed reads/writes and granted authority |
| Temporal | event, stream, forecast, or point-in-time signals |
| Risk | oracle independence, candidate visibility, hard gates |
| Environment | formats, dependencies, runtime constraints |
| Evidence | evaluator identity, cases, lineage |
| Semantics | intent, tags, task identity, optional embeddings |

`context_from_task()` derives the channels from a strict task contract.
`fingerprint_attributes_from_context()` converts them into privacy-conservative
digest attributes accepted by the existing history-informed search layer.
Domain-specific profilers may add row count, dimensionality, missingness,
target shape, imbalance, drift, collinearity, spatial coverage, temporal
cadence, text/image statistics, or embedding-space coordinates. They must keep
missing values explicit, name the embedding model and version, preserve source
provenance, and avoid storing raw sensitive data in retrieval memory.

History proposes starts; it does not grant admission. A historical route must
still match the task interface, compile against the exact registry snapshot,
execute on current cases, and pass current acceptance gates. Keep a seeded
history-blind lane so negative transfer can be measured rather than assumed.

## All-visible engineering questions

The universal bank contains three questions for each obligation. Every plan
contains all 42 question records with one of four statuses: `selected`,
`deferred`, `blocked`, or `not-applicable`. Effort changes allocation, never
visibility.

```bash
solutiongraph universal questions --obligation recover
solutiongraph universal plan idempotent-api-contract \
  --domain domain-pack.backend-api --effort E3
```

E1, E3, E5, E7, and E10 use explicit cost budgets and a recorded random seed.
Deterministic work needs no additional permission. Human, model, and external
work fail closed unless both the response mode and its authority are present:

| Response mode | Required permission |
|---|---|
| deterministic | none |
| human | `human.review` |
| llm | `model.invoke` |
| external | `network.read` |

For example, an LLM-assisted and authority-backed planning run can be requested
explicitly:

```bash
solutiongraph universal plan idempotent-api-contract \
  --domain domain-pack.backend-api --effort E7 \
  --mode deterministic --mode llm --mode human --mode external \
  --permission model.invoke --permission human.review \
  --permission network.read --random-seed 41 --json
```

Selection authorizes attention to a question, not an external action or a
solution. Answers still need evidence references, and consequential changes
still belong in independently verified graph nodes.

## Standards and orchestrator boundaries

`solutiongraph.integrations` provides side-effect-free authoring projections:

- OpenAPI 3.0–3.2 path operations become typed operation evidence with
  read/write effects and security metadata.
- CloudEvents 1.0 envelopes become explicit event-type/source evidence.
- BPMN 2.0/2.0.2 flow nodes and sequence dependencies become structural
  workflow evidence; DTD/entity input is rejected.
- Frozen plans export to portable Airflow, Dagster, Temporal, and Kubernetes
  task manifests with exact plan, registry, node, dependency, fallback,
  resource, effect, and permission identity.

These projections do not fetch references, call APIs, create clusters, deploy
jobs, or emulate native runtime semantics. An authorized deployment adapter
must translate and enforce them. That boundary follows the official
[OpenAPI 3.2 specification](https://spec.openapis.org/oas/v3.2.0.html),
[CloudEvents specification](https://github.com/cloudevents/spec),
[BPMN 2.0.2 specification](https://www.omg.org/spec/BPMN),
[Airflow executor model](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/executor/index.html),
[Dagster documentation](https://docs.dagster.io/),
[Temporal documentation](https://docs.temporal.io/), and
[Kubernetes Job documentation](https://kubernetes.io/docs/concepts/workloads/controllers/job/).

Minimal projections:

```python
from solutiongraph.integrations import project_cloudevents, project_openapi

api_projection = project_openapi(openapi_document)
event_projection = project_cloudevents(event_envelopes)
```

Export a compiler-frozen route without pretending it is deployable native
code:

```python
from solutiongraph.integrations import export_frozen_plan

manifest = export_frozen_plan(
    plan,
    program,
    registry,
    adapter_id="adapter.orchestrator.kubernetes",
)
```

## Runtime payload validation

Compiler admission proves exact nominal type identity. It cannot prove that a
runtime value conforms to the schema named by a digest. The opt-in validator
registry closes that gap for trusted validators and records their identities
in the execution environment digest.

```python
from solutiongraph.executor import ReferenceExecutor
from solutiongraph.runtime_validation import (
    CallablePayloadValidator,
    PayloadValidatorRegistry,
)

validator = CallablePayloadValidator(
    identifier="validator.orders-v1",
    schema_digest=ORDER_SCHEMA_DIGEST,
    function=validate_order,
)
validators = PayloadValidatorRegistry((validator,), require_registered=True)
executor = ReferenceExecutor(payload_validators=validators)
```

Validation runs at graph inputs, node inputs, node outputs, and graph outputs.
Stable failures distinguish invalid data, validator errors, and missing
fail-closed registrations. The default remains non-strict so existing nominal
types without schema validators preserve compatibility.

## Parallel local experiments

`ParallelExperimentRunner` allocates independent cells from an immutable
`ExperimentBundle`. Each cell must receive a fresh executor and artifact store.
Receipts are appended as runs finish, while the returned ledger is ordered by
the deterministic case/plan/seed/repetition schedule.

```python
from solutiongraph.executor import ReferenceExecutor
from solutiongraph.parallel_experiments import (
    ParallelExperimentPolicy,
    ParallelExperimentRunner,
)

runner = ParallelExperimentRunner(
    lambda: ReferenceExecutor(),
    policy=ParallelExperimentPolicy(max_parallel_runs=4),
)
result = runner.run_bundle(bundle, receipt_sink=journal)
```

This is bounded local thread allocation, not a distributed scheduler. Remote
leases, fencing, backpressure, secret brokerage, exactly-once effects, and host
failure recovery remain adapter responsibilities.

## How to expand horizontally

Add a new domain without changing compiler primitives:

1. Reuse the 14 obligations; add a new one only if it is genuinely
   domain-independent and cannot be expressed by composition.
2. Define a `DomainPack` with exact capability IDs, required obligations,
   standards, limitations, and asset references.
3. Add declarative questions for missing universal concerns, keeping executable
   checks and repair nodes separate.
4. Add a semantic template before implementation details.
5. Author small source-bound nodes with strict ports, effects, permissions,
   resources, failure classes, and provenance.
6. Compile at least one negative control and more than one compatible route.
7. Add a task contract, independent oracle, cases, experiment design, and
   receipts before claiming C6 evidence.
8. Regenerate the catalog and run every release gate.

Good next horizontal packs include infrastructure-as-code, messaging and
notifications, finance operations, commerce and payments, customer support,
identity/access administration, and hardware/edge workflows. Prefer a domain
pack plus adapters over domain-specific fields in core dataclasses.

## How to expand vertically

Deepen an existing pack by moving one exact capability through the evidence
ladder:

- replace a catalog-only technique with an importable node and fixture;
- replace one-route examples with meaningful compatible alternatives;
- add failure-preserving controls, slice cases, property tests, and mutation
  tests;
- compare control and mutation under identical cases, seeds, budgets, and
  objectives;
- add an integration adapter only when it preserves frozen identities and
  authority boundaries;
- add operational evidence only from a real, identified environment.

For the AI/ML pack, Taedri's strongest near-term lessons are capability density,
explicit activation/exclusion rules, fit/apply leakage boundaries, independent
grading, multi-objective metrics, slice evaluation, bounded search, and
negative-transfer measurement. Its model families and feature techniques
belong in the AI/ML pack; its evidence discipline belongs in the universal
core.

## What this release does not claim

- It does not solve an arbitrary task from prose without a task contract.
- It does not synthesize every compatible DAG; it compiles declared programs,
  topology families, mutations, candidates, and finite bindings.
- Adapter profiles are not live production connectors.
- Local parallelism is not distributed orchestration.
- Subprocess isolation is not a hostile-code sandbox.
- Question selection is not an answer, evaluator, or approval.
- Mechanism fixtures and synthetic cases do not establish business value,
  model superiority, or production readiness.

These limitations are part of the machine-readable profiles and coverage
report so downstream tools and LLM harnesses can reason about them directly.
