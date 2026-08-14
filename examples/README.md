# Runnable examples

All examples below use the public API. The SolutionGraph examples are
dependency-free and run without browser, model-provider, or network access.

## Five-minute paths

| Goal | Command | What it proves |
|---|---|---|
| Recommend and compose specialized packages | `python examples/specialized_package_workflow.py` | Seven all-visible verticals, transparent task nomination, exact artifact-kind composition, and search accounting without claiming executable compatibility |
| Plan a cross-domain engineering task | `python examples/universal_engineering_quickstart.py` | Ten-channel task context, all-visible effort plan, evidence-derived coverage, OpenAPI projection, and frozen-plan orchestrator export without network or deployment |
| Compile and search a two-slot graph | `python examples/solutiongraph_quickstart.py` | Full admission, exhaustive route ordering, and a frozen plan |
| Compare control and mutated graphs | `python examples/control_vs_mutated_graph_experiment.py` | Six compatible routes, fixed control, topology mutation, execution, Pareto/champion evidence |
| Learn starts and study a mutation | `python examples/intelligent_solutioning_study.py` | Cold solve, immutable history closure, warm starts, blind lanes, mutation experiment, and paired verdicts |
| Normalize an external benchmark | `python examples/external_benchmark_adapter.py` | Exact source/version/claim metadata without fetching, submitting, or overstating external evidence |
| Discover nodes and templates | `python examples/discovery_and_templates.py` | Capability negotiation, discovery receipt, snapshot, and template inspection |
| Run a portable benchmark pack | `python examples/solution_pack_benchmark_quickstart.py --output-dir .artifacts/quickstart` | Fixed/solver arms, holdout status, receipts, JSON, and HTML evidence |
| Test the coding-agent arena | `python examples/agent_benchmark_quickstart.py --output-dir .artifacts/agent-smoke` | Ten tasks, paired context arms, sealed scoring, hash-chained receipts, Mermaid/SVG diagrams, and offline analysis; no model call |
| Interrogate and repair dirty records | `python examples/semantic_interrogation_quickstart.py` | 86 visible questions, deterministic receipts, reversible shadow patches, an independent decision, and redacted reports |
| Design a data/ML system | `solutiongraph atlas plan --context examples/data-science-design-context.json --effort E3 --output-dir .artifacts/design` | 112 visible design questions, explicit branches/evidence/authority, and portable reports; no technique implementation claim |
| Execute the design graph | `python examples/data_science_design_atlas_graph.py --runtime subprocess` | Aggregate-only typed inputs, compiler-enforced reviewer authority, a frozen E1 route, digest-bound evidence, four isolated node receipts, and an independently verified report |

## CLI-driven domain examples

```bash
solutiongraph examples list
solutiongraph packages list
solutiongraph packages recommend "Build a sealed LLM evaluation harness"
solutiongraph packages compose --input-kind artifact.raw-records \
  --output-kind artifact.deployed-model
solutiongraph universal domains
solutiongraph universal coverage
solutiongraph universal plan idempotent-api-contract \
  --domain domain-pack.backend-api --effort E3
solutiongraph examples run dataset-profiling-and-drift --route all --json
solutiongraph solve golden-customer-table --profile balanced
solutiongraph arena list
solutiongraph benchmarks list
solutiongraph benchmarks adapters
solutiongraph solutioning inspect data-cleanup --effort 1
solutiongraph solutioning run data-cleanup --effort 1
solutiongraph agent-bench tasks
solutiongraph agent-bench smoke --output .artifacts/agent-benchmark-smoke
```

The 47 bundled programs cover data quality, documents, images, GIS, APIs,
frontend release checks, synthetic data, reinforcement learning, LLM evaluation,
and ten data-science/ML lifecycle families. They are transparent mechanism
fixtures, not production performance evidence.

The semantic interrogation example uses one intentionally dirty organization,
address, contact, time, and ML-target dataset. The equivalent CLI workflow is:

```bash
solutiongraph questions plan examples/data/dirty_organizations.json --effort E1
solutiongraph questions run examples/data/dirty_organizations.json \
  --effort E3 --output-dir .artifacts/interrogation
```

## Offline visual explorers

- `universal-dag-explorer.html` — task/stage/slot/candidate/route matrix;
- `catalog-template-explorer.html` — template and node-pack catalog;
- `universal-dag-benchmark-report.html` — embedded benchmark evidence;
- `universal-graph-workbench.html` — full route builder and comparison studio;
- `workbench-suite/index.html` — multi-page projection suite.

Open any HTML file directly. No web server or CDN is required.

## Notebooks

The six numbered notebooks cover browsing/scraping, document extraction,
image checks, data cleaning, tabular ML, and matched LLM coding-harness A/B
experiments. `data_science_design_atlas.ipynb` adds a dependency-free planning
workbook for the 31 task archetypes and E1–E10 decision policies. They call the
same APIs used by CI.

## Claim boundary

Replace fixture data with licensed representative cases and a separately owned,
candidate-inaccessible holdout before making efficacy claims. Use an enforcing
runtime boundary for untrusted generated code; the bundled subprocess adapter
is lifecycle isolation, not a hostile-code sandbox.
