# Semantic Solution Template Protocol

Status: research preview 0.1  
Normative Python model: `solutiongraph.templates`  
Reference catalogue: `solutiongraph.template_library` and `catalog/templates/`

A solution template is a reusable decomposition of a problem class into typed
semantic obligations. It is not a hard-coded route, a list of preferred tools,
or a prompt that asks a model to improvise architecture.

## 1. Template layers

```text
solution template
├── task and independent success-contract pattern
├── macro stages / visible submatrices
│   └── atomic semantic slots / columns
├── typed forward edges
└── bounded refinement policies (control plane, never route steps)
```

Every atomic slot is a substitution boundary. A node belongs in that slot only
when it is a genuine implementation of the same obligation with compatible
ports, capabilities, effects, and authority.

Stages exist for navigation and localized experimentation. They do not execute,
receive candidates, or change types. Every slot appears in exactly one stage,
and stage order cannot run backward across a semantic edge.

## 2. When to split a slot

Split a slot when any candidate would need to:

- perform a materially different sequence of actions;
- consume or produce a different semantic type;
- have a different independently testable success condition;
- request additional effects or authority;
- expose a reusable intermediate value;
- be optimized, retried, cached, or replaced independently;
- contain a hidden finite choice users should be able to compare.

Do not split merely because one implementation uses several private functions.
The boundary is an externally meaningful contract, not code size.

## 3. Template instantiation

An agent or developer instantiates a template in this order:

1. Replace the template task with the concrete task or ticket.
2. Define typed external inputs and outputs.
3. Replace the generic acceptance pattern with an independent oracle.
4. Remove irrelevant slots only after proving the obligation is absent.
5. Add missing domain obligations and split oversized slots.
6. Refine schematic value types into versioned schemas and units.
7. Declare allowed effects and separately granted permissions.
8. Discover node registries through the negotiated protocol.
9. Compile the complete snapshot and preserve all admission decisions.
10. Select, execute, and learn only inside the admitted space.

The reference templates use versioned schematic state types so they validate
as complete graphs. A production instantiation SHOULD replace them with
domain-specific values and explicit fan-out/merge structure. The template is a
starting hypothesis, not permission to pass an opaque mutable dictionary
through every node.

## 4. Optional obligations and pass-through candidates

“Skip this step” is not a topology mutation. Prefer a visible optional slot with
an explicit identity candidate when all of these are true:

- the slot contract says no transformation may be necessary;
- input and output types, schema, units, and cardinality are identical;
- identity preserves required invariants and ordering;
- no effect or verification obligation is being bypassed;
- the compiler can admit the identity node like every other candidate.

If input and output types differ, an identity node is invalid. If skipping
would remove a required audit, safety, or acceptance check, pass-through is not
an admissible candidate.

## 5. Refinement and iteration

Iteration is represented in two different ways:

- a task-semantic loop is a structured `loop` or composite slot with a nested
  graph and explicit state/termination contract;
- an optimizer refinement loop proposes another frozen route after observing a
  receipt and stays outside the executable DAG.

`RefinementPolicy` declares trigger, scope, proposal strategy, evaluation and
stop contracts, history behavior, snapshot refresh, and either a maximum
iteration count or external budget reference. An unbounded implicit “try until
it works” loop is invalid.

## 6. Reference template catalogue

The repository ships 18 deliberately varied templates containing 317 atomic
obligations:

| Template | Atomic slots | What it demonstrates |
|---|---:|---|
| `template.kaggle-tabular` | 27 | EDA, leakage-safe preprocessing, model pool, calibration, ensembling, audit |
| `template.data-quality` | 15 | normalization, postal/geographic validation, entity resolution, publishing |
| `template.qa-engineering` | 13 | impact analysis, independent oracles, layered tests, flake diagnosis, gating |
| `template.login-system` | 14 | threat model, identity operations, sessions, recovery, abuse protection |
| `template.deployment-release` | 14 | reproducible build, provenance, staged rollout, verification, rollback |
| `template.shipping-notifications` | 15 | external events, reconciliation, policy, delivery, feedback |
| `template.document-intelligence` | 18 | format detection, text/vision decoding, normalization, grounded extraction |
| `template.web-automation` | 19 | authorization, runtime selection, perception, action, verification, recovery |
| `template.image-processing` | 18 | integrity, quality, vision, transformation, encoding, provenance |
| `template.batch-data-pipeline` | 18 | source contracts, ETL, lineage, reconciliation, publication, recovery |
| `template.api-service` | 18 | API contracts, domain state, auth, resilience, observability, assurance |
| `template.event-driven-system` | 17 | event semantics, idempotency, transitions, sagas, replay |
| `template.time-series-forecasting` | 20 | temporal leakage, backtests, diverse models, calibration, reconciliation |
| `template.recommendation-ranking` | 19 | candidates, eligibility, multi-objective ranking, evaluation, exposure |
| `template.incident-response` | 18 | evidence, triage, containment, recovery, notification, learning |
| `template.customer-support` | 17 | intake, identity, policy, resolution, communication, follow-up |
| `template.infrastructure-provisioning` | 17 | desired state, drift, policy plan, approval, apply, lifecycle |
| `template.scientific-experiment` | 20 | hypotheses, preregistration, measurement, sensitivity, replication |

These are test fixtures for the universal abstraction, not claims that every
project needs exactly these steps. Their value is that agents can start with a
known obligation vocabulary, compare it with the concrete task, and make every
addition/removal explicit.

## 7. Authoring formats

The normative `SolutionTemplate` model supports arbitrary valid DAGs. The
optional `LinearTemplateBlueprint` is a smaller JSON authoring format for the
common left-to-right stage/slot matrix. It requires explicit purposes, success
contracts, and semantic capabilities, then compiles into the normative model.

```bash
solutiongraph templates list
solutiongraph templates show template.document-intelligence
solutiongraph templates validate examples/custom-template-blueprint.json
solutiongraph templates create examples/custom-template-blueprint.json \
  --output /tmp/template.json
```

The convenience blueprint MUST NOT hide a real branch, join, map, barrier,
composite subgraph, or second typed value inside opaque state. Use the full
Python model for those topologies.

## 8. Template quality checks

A template is ready for reuse only when:

- the task and success pattern describe outcomes rather than tools;
- slots are atomic substitution boundaries;
- every slot has named typed ports and its own success contract;
- every slot belongs to exactly one visible stage;
- all stage transitions move forward;
- branches, loops, maps, reduces, and barriers are structured;
- effects and permissions are not inferred from a likely implementation;
- optimization and feedback are not fake execution steps;
- refinement loops disclose budgets and evaluation rules;
- at least one realistic domain instantiation compiles;
- tests detect omitted, duplicated, unknown, and backward-grouped slots.

## 9. Anti-patterns

- **Tool-first template:** stages named “OpenAI,” “Postgres,” or “Chrome.” Those
  are candidates or deployments, not semantic obligations.
- **Mega-step:** “clean data” or “build model” with dozens of hidden choices.
- **Graph-shaped checklist:** boxes have no typed values or success contracts.
- **Optimization step:** “pick best model” inserted between business actions
  without separating experimental evidence from execution.
- **Implicit skip:** deleting a node and reconnecting incompatible ports.
- **Prompt-only contract:** assuming an LLM will infer types, authority, or
  acceptance from prose.
- **Template worship:** retaining irrelevant slots because the example had them.
- **Opaque state forever:** shipping production nodes that mutate an unversioned
  catch-all object because the schematic template used a state envelope.
