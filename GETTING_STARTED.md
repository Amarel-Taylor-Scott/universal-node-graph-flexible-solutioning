# Getting Started

Universal Node Graph can be explored without a browser, model provider, vector
database, or network service. The domain-neutral core uses only the Python
standard library. Version 0.6 is a developer preview; read `READINESS.md`
before production integration.

## 1. Install and verify

```bash
git clone https://github.com/Amarel-Taylor-Scott/universal-node-graph-flexible-solutioning.git
cd universal-node-graph-flexible-solutioning
python -m pip install -e .
solutiongraph doctor
solutiongraph conformance
solutiongraph verify --catalog-root catalog --runtime in-process
solutiongraph verify --catalog-root catalog --runtime subprocess
```

The doctor command validates all bundled schemas, templates, reference nodes,
descriptors, solution packs, benchmark closures, and generated catalog
projections. The release verifier then compiles and executes all 54 frozen
reference routes, checks 21 declared negative controls, runs 11 installed-wheel
conformance mechanisms, and rejects stale checked-in catalog JSON.

For a non-editable installation directly from GitHub:

```bash
python -m pip install \
  "browsergraph @ git+https://github.com/Amarel-Taylor-Scott/universal-node-graph-flexible-solutioning.git@main"
```

`browsergraph` is the compatibility distribution name; `solutiongraph` is the
primary domain-neutral import and CLI.

## 2. Create a task workspace

Generate a complete, non-destructive starter directory for a developer or LLM
coding harness:

```bash
solutiongraph init invoice-solution \
  --template template.document-intelligence
cd invoice-solution
```

The generated workspace contains the exact starting template and digest,
task-contract intake, agent instructions, project metadata, and safety rules.
It does not fabricate nodes, permissions, or benchmark evidence. If the target
directory already exists, initialization fails instead of overwriting it.

## 3. Explore reusable templates

```bash
solutiongraph templates list
solutiongraph templates list --domain machine-learning.time-series
solutiongraph templates show template.document-intelligence
solutiongraph templates show template.kaggle-tabular --json
```

The library contains 31 domain templates and 544 atomic obligations. A template
describes what must happen; node registries independently provide the possible
ways to accomplish each obligation.

Open `examples/universal-dag-explorer.html` for a strictly left-to-right view of
nested submatrices, every visible candidate, structured-control semantics, and
parallel routes. Open `examples/catalog-template-explorer.html` to browse every
template and node pack without running a server.

## 4. Create a template

Copy the strict authoring example, edit the task, stages, and slots, then
validate it:

```bash
cp examples/custom-template-blueprint.json my-template.json
solutiongraph templates validate my-template.json
solutiongraph templates create my-template.json --output my-template.compiled.json
```

Every slot needs a purpose, independent success contract, and semantic
capability. Unknown fields, duplicate identifiers, missing capabilities, and
invalid contracts fail before a template is emitted.

The linear blueprint is a convenience for left-to-right stage matrices. Use
the full `SolutionTemplate` and `ProgramGraph` Python models when the task has
real branches, joins, maps, barriers, composite subgraphs, or multiple values.

## 5. Use the repository skills

Agents that support workspace skills can be asked to use:

- `@create-solution-template` to author or refine a domain template;
- `@author-node-pack` to wrap reusable implementations and connectors;
- `@execute-solution-graph` to add runtimes, artifacts, verifiers, and executable examples;
- `@benchmark-solution-graph` to design route experiments;
- `@design-autoresearch-campaign` to run bounded LLM-generated improvement campaigns;
- `@design-topology-family` to author and benchmark alternative graph shapes;
- `@author-structured-workflow` to implement branches, composites, and bounded loops safely;
- `@solve-universal-dag` to implement or solve an Arena task with evidence-backed route selection;
- `@package-solution-graph` to freeze a task, cases, evaluator, programs, registries, and baselines into one exact solution-pack closure;
- `@run-benchmark-arena` to compare fixed routes and bounded solver policies under one controlled suite;
- `@expand-node-library` to add source-bound reusable primitives and discovery sidecars;
- `@model-solution-graph` for the complete end-to-end workflow.

The skills guide the agent, while schemas, compiler diagnostics, tests, and CI
remain the enforcement boundary.

## 6. Build or discover nodes

Read `NODE_REPOSITORY_PROTOCOL.md`. A reusable node pack separates:

- strict executable `NodeSpec` contracts;
- exact parameter-bound candidates;
- optional descriptions, documents, and embeddings;
- advertised registry capabilities;
- content-addressed artifacts and manifests.

Discovery may nominate a node. Only compiler admission against a pinned
registry snapshot can make it runnable.

## 7. Compile and search

Run the minimal executable example:

```bash
python examples/solutiongraph_quickstart.py
python examples/discovery_and_templates.py
```

Choose prior, beam, seeded-sprout, or explicitly exhaustive search according to
the available budget. Search reports preserve coverage, skips, invalid routes,
duplicates, unvisited routes, seeds, and belief revision.

## 8. Solve and execute the reference domain skeletons

Inspect all 36 Arena contracts and execute or solve the 24 local programs:

```bash
solutiongraph examples list
solutiongraph arena list
solutiongraph arena show arena.validated-analytical-dataset
solutiongraph solve multi-feed-analytical-dataset --profile balanced
solutiongraph arena run --profile quick
```

Inspect the six portable solution packs and run controlled fixed-route versus
solver comparisons:

```bash
solutiongraph packs list
solutiongraph packs show solution-pack.stdlib-data-quality
solutiongraph benchmarks list
solutiongraph benchmarks run benchmark.stdlib-data-quality \
  --runtime subprocess \
  --artifact-dir .artifacts/stdlib-benchmark \
  --receipt-journal .artifacts/benchmark-receipts.jsonl \
  --report-html .artifacts/stdlib-benchmark.html \
  --report-json .artifacts/stdlib-benchmark.json
python examples/solution_pack_benchmark_quickstart.py \
  --output-dir .artifacts/solution-pack-quickstart
```

These bundled cases are transparent mechanism fixtures. Replace them with
representative licensed development data and a candidate-inaccessible holdout
before making domain-performance or production claims. See
`TASK_AND_SOLUTION_PACK_PROTOCOL.md` and `BENCHMARK_PROTOCOL.md`.

Run the same frozen routes through the bounded subprocess adapter and retain
durable evidence:

```bash
solutiongraph examples run document-to-schema \
  --runtime subprocess \
  --artifact-dir .artifacts/document \
  --receipt-journal .artifacts/receipts.jsonl
solutiongraph ledger verify .artifacts/receipts.jsonl
```

These runs recompile exact plans, execute trusted standard-library nodes,
content-address outputs, independently verify outcomes, and retain negative
results. Read `REAL_WORLD_EXAMPLES.md` before extending them and
`EXECUTION_PROTOCOL.md` before adding a runtime. The default Python adapter is
in-process. The subprocess adapter adds lifecycle and resource separation, but
it is also not an adversarial sandbox.

For an LLM harness that will generate or mutate nodes and routes, read
`AUTORESEARCH_REVIEW.md` and use `@design-autoresearch-campaign`. Freeze an
`EvaluationBoundary`, declare a `CampaignBudget`, preserve every proposal's
parents in a `CampaignLedger`, and keep hidden evaluators outside the
candidate's trust domain. `template.numerical-linear-system` demonstrates the
same decomposition for Cholesky, QR, SVD, LDL, sparse, iterative, precision,
and verification alternatives without adding a numerical dependency.

The address fixture exercises an authority connector contract against an
offline reference directory. It is not an official USPS lookup. Replace that
node with a credentialed, policy-aware connector before making USPS validation
claims. The Arena preserves this limitation in its task metadata and verifier
details.

## 9. Validate a contribution

```bash
solutiongraph catalog export --output catalog
pytest tests/test_solutiongraph*.py -q
ruff check solutiongraph tests/test_solutiongraph*.py
solutiongraph conformance
solutiongraph verify --catalog-root catalog --runtime in-process
solutiongraph verify --catalog-root catalog --runtime subprocess
```

For changes that touch BrowserGraph or the viewers, run the full deterministic
suite with `pytest -q`.
