# Runnable examples

All examples below use the public API. The SolutionGraph examples are
dependency-free and run without browser, model-provider, or network access.

## Five-minute paths

| Goal | Command | What it proves |
|---|---|---|
| Compile and search a two-slot graph | `python examples/solutiongraph_quickstart.py` | Full admission, exhaustive route ordering, and a frozen plan |
| Compare control and mutated graphs | `python examples/control_vs_mutated_graph_experiment.py` | Six compatible routes, fixed control, topology mutation, execution, Pareto/champion evidence |
| Discover nodes and templates | `python examples/discovery_and_templates.py` | Capability negotiation, discovery receipt, snapshot, and template inspection |
| Run a portable benchmark pack | `python examples/solution_pack_benchmark_quickstart.py --output-dir .artifacts/quickstart` | Fixed/solver arms, holdout status, receipts, JSON, and HTML evidence |

## CLI-driven domain examples

```bash
solutiongraph examples list
solutiongraph examples run dataset-profiling-and-drift --route all --json
solutiongraph solve golden-customer-table --profile balanced
solutiongraph arena list
solutiongraph benchmarks list
```

The 47 bundled programs cover data quality, documents, images, GIS, APIs,
frontend release checks, synthetic data, reinforcement learning, LLM evaluation,
and ten data-science/ML lifecycle families. They are transparent mechanism
fixtures, not production performance evidence.

## Offline visual explorers

- `universal-dag-explorer.html` — task/stage/slot/candidate/route matrix;
- `catalog-template-explorer.html` — template and node-pack catalog;
- `universal-dag-benchmark-report.html` — embedded benchmark evidence;
- `universal-graph-workbench.html` — full route builder and comparison studio;
- `workbench-suite/index.html` — multi-page projection suite.

Open any HTML file directly. No web server or CDN is required.

## Notebooks

The five numbered notebooks cover browsing/scraping, document extraction,
image checks, data cleaning, and tabular ML. They call the same executable
example API used by CI.

## Claim boundary

Replace fixture data with licensed representative cases and a separately owned,
candidate-inaccessible holdout before making efficacy claims. Use an enforcing
runtime boundary for untrusted generated code; the bundled subprocess adapter
is lifecycle isolation, not a hostile-code sandbox.
