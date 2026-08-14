# Specialized capability packages

SolutionGraph can present one domain-neutral graph substrate through focused,
installable product surfaces. A specialized capability package collects useful
starting recipes, task/data profiling features, evaluation metrics, quality
gates, and links to checked-in assets for one engineering practice. It helps an
engineer or agent discover and compose a solution space; it does not authorize
or execute that solution by itself.

The reference release includes seven individually importable packages:

| Package | Typical work | Recipes | Features | Metrics | Gates |
|---|---|---:|---:|---:|---:|
| Data engineering | Cleaning, contracts, enrichment, reconciliation, batch and event-time pipelines | 4 | 7 | 6 | 2 |
| Data analysis | EDA, cohorts, funnels, geotemporal analysis and experiment evidence | 4 | 7 | 5 | 2 |
| Data science | Regression, classification, forecasting, ranking, clustering, anomalies and ensembles | 5 | 8 | 6 | 2 |
| ML engineering | Reproducible training, synthetic supplementation, serving, monitoring, RL and rollback | 5 | 7 | 6 | 3 |
| LLM engineering | Grounded RAG, agents/tools, synthetic curricula, evaluation, red teaming and sealed promotion | 4 | 8 | 7 | 3 |
| Software engineering | Repository repair, testing, APIs, frontend journeys, migrations and staged releases | 5 | 7 | 6 | 2 |
| Operations and reliability | Observability, incidents, recovery, compliance, workflows and constrained planning | 5 | 7 | 6 | 3 |

Together they expose 32 typed recipes, 51 profiling features, 42 metrics, and
17 independent or escalation-oriented quality gates. Every recipe references
real catalog assets, and release verification rejects stale references.

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

The seven built-ins currently ship in the `browsergraph` distribution so one
checkout and one test suite can prove cross-package contracts. Each definition
records an extraction target such as `solutiongraph-pack-data-engineering` or
`solutiongraph-pack-llm-engineering`. That makes later repository/package
splits mechanical without pretending they have already happened.

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
