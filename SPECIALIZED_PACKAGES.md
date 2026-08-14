# Specialized capability packages

SolutionGraph can present one domain-neutral graph substrate through focused,
installable product surfaces. A specialized capability package collects useful
starting recipes, task/data profiling features, evaluation metrics, quality
gates, and links to checked-in assets for one engineering practice. It helps an
engineer or agent discover and compose a solution space; it does not authorize
or execute that solution by itself.

The reference release includes 26 individually importable packages. They are
layered rather than mutually exclusive: a task can combine a practice pack, a
modality or assurance pack, and a mission/industry pack before exact recipe
composition and compiler admission.

### Practice foundations

| Package | Typical work | Recipes | Features | Metrics | Gates |
|---|---|---:|---:|---:|---:|
| Data engineering | Cleaning, contracts, enrichment, reconciliation, batch and event-time pipelines | 4 | 7 | 6 | 2 |
| Data analysis | EDA, cohorts, funnels, geotemporal analysis and experiment evidence | 4 | 7 | 5 | 2 |
| Data science | Regression, classification, forecasting, ranking, clustering, anomalies and ensembles | 5 | 8 | 6 | 2 |
| ML engineering | Reproducible training, synthetic supplementation, serving, monitoring, RL and rollback | 5 | 7 | 6 | 3 |
| LLM engineering | Grounded RAG, agents/tools, synthetic curricula, evaluation, red teaming and sealed promotion | 4 | 8 | 7 | 3 |
| Software engineering | Repository repair, testing, APIs, frontend journeys, migrations and staged releases | 5 | 7 | 6 | 2 |
| Operations and reliability | Observability, incidents, recovery, compliance, workflows and constrained planning | 5 | 7 | 6 | 3 |

### Modality, assurance, and cyber-physical packs

| Package | Typical work | Readiness |
|---|---|---|
| LLM evaluation and safety | Independent evaluation, judge calibration, agent trajectories, red-team regression curricula, sealed promotion | Executable fixture |
| Cybersecurity | Authorized threat modeling, defensive telemetry investigation, containment/recovery evidence | Executable read-only fixture; effectful response is permission-gated |
| Privacy, governance, and compliance | Privacy-by-design, de-identification, control testing, exception and attestation evidence | Executable fixture |
| Document intelligence | OCR/layout-aware extraction, source grounding, rendering, visual verification, redaction | Executable fixture |
| Media intelligence | Image, audio, and video integrity, timelines, captions, transformations, release assurance | Executable fixture |
| 3D and simulation assets | Geometry, materials, collision, LOD, rendering regression, export budgets | Executable synthetic fixture |
| Game engineering | State contracts, builds, deterministic replay, bot/human playtests, balance, release | Executable rules fixture |
| Geospatial and temporal | Addresses, CRS, boundaries, time zones, event time, place-time enrichment, maps | Credentialed connector |
| Robotics and control | Robot models, planning, simulation, safety envelopes, recovery, physical authority | Executable simulation-only fixture |
| Scientific computing and digital twins | Numerical solve, calibration, validation, uncertainty, sensitivity, scenario decisions | Executable synthetic fixture |
| Embedded systems and IoT | Firmware assurance, device identity, event-time telemetry, fleet state, commands, rollout | Executable telemetry fixture |

### Mission and industry packs

| Package | Typical work | Readiness |
|---|---|---|
| Healthcare and biomedical evidence | Cohorts, evidence synthesis, subgroup evaluation, bounded clinical decision support | Catalog only; no clinical-use claim |
| Finance, risk, and fraud | Ledger reconciliation, calibrated fraud/risk decisions, forecasting and stress evidence | Executable synthetic fixture |
| Supply chain and planning | Network data, demand/inventory, constrained plans, fulfillment and disruption loops | Executable logistics fixture |
| Product experimentation | Event contracts, journeys/funnels, randomization, causal estimates, guardrails | Executable event fixture |
| Search and recommendation | Permission-aware indexing, hybrid retrieval, ranking, recommendation, feedback bias | Executable ranking fixture |
| Knowledge and research | Provenance-first knowledge bases, conflict-aware synthesis, reproducible dossiers, grounded answers | Executable document/research fixtures |
| Education and assessment | Objectives, content, assessment blueprints, rubrics, accessibility, educator review | Catalog only; no high-stakes scoring claim |
| Creative content production | Briefs, diverse concepts, multimodal production, rights/brand/accessibility review, delivery | Executable media-assurance fixture |

Together the 26 packs expose 89 typed recipes, 127 profiling features, 118
metrics, and 55 independent or escalation-oriented quality gates. Every recipe
references real catalog assets, and release verification rejects stale
references. A readiness label applies only to the evidence explicitly linked
from the pack; it is not a production, safety, regulatory, or domain-quality
certification.

## Three different meanings of “pack”

These contracts solve different problems and should remain separate:

| Contract | Purpose | Executable? |
|---|---|---|
| `SpecializedPackDefinition` | Discover, recommend, and compose a vertical authoring surface | No; it is an advisory asset index |
| `NodePackManifest` | Distribute reusable, content-addressed executable node definitions | Contains executable definitions, but not a complete task run |
| `SolutionPackManifest` | Freeze the exact task, program, registry, node packs, cases, oracle, baselines, and benchmark closure | Yes, after ordinary compilation and runtime checks |

The CLI therefore uses `solutiongraph packages` for specialized packages and
retains `solutiongraph packs` for exact solution-pack manifests.

## Five-minute package workflow

List and inspect the bundled packages:

```bash
solutiongraph packages list
solutiongraph packages show specialized-pack.data-engineering
solutiongraph packages show specialized-pack.robotics-control
```

Rank every package for a task. The recommended list is bounded, but the report
keeps every package, component score, match, missing capability, blocked
permission, and reason visible:

```bash
solutiongraph packages recommend \
  "Validate and enrich company addresses, then train and deploy a churn model" \
  --input-kind artifact.raw-records \
  --output-kind artifact.deployed-model \
  --limit 4
```

Enumerate exact recipe chains by artifact kind:

```bash
solutiongraph packages compose \
  --input-kind artifact.raw-records \
  --output-kind artifact.deployed-model \
  --max-steps 5
```

One valid reference chain is:

```text
raw records
  -> data-engineering: batch quality
  -> data-science: supervised modeling
  -> ml-engineering: model release
  -> deployed model
```

Composition is an exact, bounded breadth-first search over declared artifact
kinds. It never inserts an implicit conversion, silently drops a goal, or
claims that a recipe chain is a compiler-valid executable route. Its report
includes visited, expanded, queued-but-unexpanded, truncation, and unresolved-
goal accounting.

JSON output is available on every command:

```bash
solutiongraph packages recommend "Investigate a production outage" --json
solutiongraph packages recommend \
  "Validate a 3D mesh, generate LODs, and run render regressions" --json
solutiongraph packages compose \
  --input-kind artifact.deployed-service \
  --output-kind artifact.recovery-evidence \
  --json
```

## Python API

```python
from solutiongraph.specialized import (
    REFERENCE_SPECIALIZED_PACK_REGISTRY,
    PackageCompositionRequest,
    TaskPackageRequest,
    compose_specialized_packs,
    recommend_specialized_packs,
)

request = TaskPackageRequest(
    id="package-request.customer-quality",
    description="Clean, validate, and enrich customer records",
    input_kind_ids=("artifact.raw-records",),
    output_kind_ids=("artifact.enriched-dataset",),
)
recommendations = recommend_specialized_packs(
    request,
    REFERENCE_SPECIALIZED_PACK_REGISTRY,
    selection_limit=3,
)

composition = compose_specialized_packs(
    PackageCompositionRequest(
        id="composition-request.customer-quality",
        starting_kind_ids=("artifact.raw-records",),
        goal_kind_ids=("artifact.enriched-dataset",),
        max_steps=4,
    ),
    REFERENCE_SPECIALIZED_PACK_REGISTRY,
)
```

Recommendation scores are transparent lexical, task-category, capability,
artifact-kind, permission, and explicit preference signals. They are starting
priors, not compatibility probabilities or empirical performance claims.

## From nomination to evidence

A safe end-to-end lifecycle is:

1. Describe the task with a `TaskContract` or `TaskPackageRequest`.
2. Nominate specialized packages and compose candidate recipes.
3. Choose or refine a semantic `SolutionTemplate` without inventing node
   capabilities.
4. Discover node descriptors, negotiate provider capabilities, and freeze a
   closed-world registry snapshot.
5. Compile every candidate against exact ports, types, permissions, effects,
   parameters, and graph constraints.
6. Search only compiler-admitted routes under an explicit effort budget,
   preserving random and history-blind lanes where appropriate.
7. Freeze a plan, execute it through a declared runtime boundary, and collect
   immutable receipts.
8. Apply an independently identified oracle, compare controls and mutations,
   and promote only within the benchmark's declared claim scope.
9. Package reproducible task/run closure as a `SolutionPackManifest`; feed
   observations back into history without rewriting semantics.

## Author a third-party package

Create one module whose `PACK` value is a validated
`SpecializedPackDefinition`. Keep executable node implementations in a node
pack and reference their IDs from recipes.

```python
# acme_solutiongraph_security/pack.py
from solutiongraph.specialized import SpecializedPackDefinition

PACK = SpecializedPackDefinition(
    # See the JSON Schema and bundled package modules for all required fields.
    ...
)
```

Declare it as an entry point:

```toml
[project.entry-points."solutiongraph.specialized_packs"]
security-engineering = "acme_solutiongraph_security.pack:PACK"
```

Inspect provider metadata without importing third-party code, then load only
when explicitly requested:

```bash
solutiongraph packages providers
solutiongraph packages providers --load
solutiongraph packages list --include-installed
solutiongraph packages recommend "Audit a governed data release" \
  --include-installed
```

Discovery is declare-before-load. Loading records provider failures, validates
definitions, and rejects identity conflicts instead of quietly replacing a
built-in package. `--include-installed` is an explicit fail-closed opt-in: if
any declared provider cannot load, the command reports the failure instead of
using a silently incomplete registry.

The strict wire contracts are in:

- `solutiongraph/schemas/specialized-pack.schema.json`
- `solutiongraph/schemas/specialized-pack-registry.schema.json`
- `solutiongraph/schemas/specialized-task-request.schema.json`
- `solutiongraph/schemas/specialized-recommendation-report.schema.json`
- `solutiongraph/schemas/specialized-composition-request.schema.json`
- `solutiongraph/schemas/specialized-composition-report.schema.json`

## Extraction and product boundaries

The 26 built-ins currently ship in the `browsergraph` distribution so one
checkout and one test suite can prove cross-package contracts. Each definition
records an extraction target such as `solutiongraph-pack-data-engineering` or
`solutiongraph-pack-llm-engineering`. That makes later repository/package
splits mechanical without pretending they have already happened.

The intended extraction axes are deliberately composable:

- practice packages such as `solutiongraph-pack-data-engineering`;
- modality packages such as `solutiongraph-pack-document-intelligence`;
- assurance packages such as `solutiongraph-pack-llm-evaluation-safety`;
- cyber-physical packages such as `solutiongraph-pack-robotics-control`; and
- mission packages such as `solutiongraph-pack-healthcare-biomedical`.

See [COMPETITIVE_LANDSCAPE_AND_INTEGRATION_STRATEGY.md](COMPETITIVE_LANDSCAPE_AND_INTEGRATION_STRATEGY.md)
for the current build-versus-integrate boundary across workflow engines,
data/ML orchestration, LLM evaluation, observability, cyber, robotics, and 3D.

A focused distribution should contain its package definition, relevant
templates/question banks, executable node packs, fixtures, and benchmark
manifests. The domain-neutral compiler, contracts, discovery protocol, runtime
seams, evidence model, and schemas remain in the core. Vendor SDKs, credentials,
orchestrator implementations, hosted evaluators, and production isolation
belong in optional adapters.

## Current limitations

- Recipes are curated authoring starting points, not a complete registry of all
  possible engineering procedures.
- Recommendation has no learned calibration until real, comparable receipts
  are supplied; no bundled score is a success-rate claim.
- Composition operates on declared artifact kinds, not full port schemas. The
  compiler remains the compatibility authority.
- Most reference assets are dependency-free teaching fixtures. Credentialed
  services, hostile-code isolation, distributed execution, and production
  durability require external adapters and operational evidence.
- Package extraction targets are recorded but not yet independently released.

These boundaries are intentional: horizontal breadth comes from additional
packages and recipes, while vertical maturity comes from exact nodes,
production adapters, independent evaluation, and reproducible benchmark
evidence.
