# Getting Started

Universal Node Graph can be explored without a browser, model provider, vector
database, or network service. The domain-neutral core uses only the Python
standard library.

## 1. Install and verify

```bash
git clone https://github.com/Amarel-Taylor-Scott/universal-node-graph-flexible-solutioning.git
cd universal-node-graph-flexible-solutioning
python -m pip install -e .
solutiongraph doctor
solutiongraph verify --catalog-root catalog
```

The doctor command validates all bundled schemas, templates, reference nodes,
descriptors, and generated catalog projections. The release verifier then
compiles and executes all 14 frozen reference routes, checks the three declared
negative controls, and rejects stale checked-in catalog JSON.

## 2. Explore reusable templates

```bash
solutiongraph templates list
solutiongraph templates list --domain machine-learning.time-series
solutiongraph templates show template.document-intelligence
solutiongraph templates show template.kaggle-tabular --json
```

The library contains 19 domain templates and 339 atomic obligations. A template
describes what must happen; node registries independently provide the possible
ways to accomplish each obligation.

Open `examples/catalog-template-explorer.html` to browse stages and atomic slots
visually without running a server.

## 3. Create a template

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

## 4. Use the repository skills

Agents that support workspace skills can be asked to use:

- `@create-solution-template` to author or refine a domain template;
- `@author-node-pack` to wrap reusable implementations and connectors;
- `@execute-solution-graph` to add runtimes, artifacts, verifiers, and executable examples;
- `@benchmark-solution-graph` to design route experiments;
- `@design-autoresearch-campaign` to run bounded LLM-generated improvement campaigns;
- `@model-solution-graph` for the complete end-to-end workflow.

The skills guide the agent, while schemas, compiler diagnostics, tests, and CI
remain the enforcement boundary.

## 5. Build or discover nodes

Read `NODE_REPOSITORY_PROTOCOL.md`. A reusable node pack separates:

- strict executable `NodeSpec` contracts;
- exact parameter-bound candidates;
- optional descriptions, documents, and embeddings;
- advertised registry capabilities;
- content-addressed artifacts and manifests.

Discovery may nominate a node. Only compiler admission against a pinned
registry snapshot can make it runnable.

## 6. Compile and search

Run the minimal executable example:

```bash
python examples/solutiongraph_quickstart.py
python examples/discovery_and_templates.py
```

Choose prior, beam, seeded-sprout, or explicitly exhaustive search according to
the available budget. Search reports preserve coverage, skips, invalid routes,
duplicates, unvisited routes, seeds, and belief revision.

## 7. Execute the reference domain skeletons

Execute the six reference programs (grouped into five notebook task families):

```bash
solutiongraph examples list
solutiongraph examples run browse-and-scrape
solutiongraph examples run document-to-schema
solutiongraph examples run image-check-and-process
solutiongraph examples run data-cleanup
solutiongraph examples run tabular-regression
solutiongraph examples run tabular-classification
```

These runs recompile exact plans, execute trusted standard-library nodes,
content-address outputs, independently verify outcomes, and retain negative
results. Read `REAL_WORLD_EXAMPLES.md` before extending them and
`EXECUTION_PROTOCOL.md` before adding a runtime. The default Python adapter is
in-process and is not a production sandbox.

For an LLM harness that will generate or mutate nodes and routes, read
`AUTORESEARCH_REVIEW.md` and use `@design-autoresearch-campaign`. Freeze an
`EvaluationBoundary`, declare a `CampaignBudget`, preserve every proposal's
parents in a `CampaignLedger`, and keep hidden evaluators outside the
candidate's trust domain. `template.numerical-linear-system` demonstrates the
same decomposition for Cholesky, QR, SVD, LDL, sparse, iterative, precision,
and verification alternatives without adding a numerical dependency.

## 8. Validate a contribution

```bash
solutiongraph catalog export --output catalog
pytest tests/test_solutiongraph*.py -q
ruff check solutiongraph tests/test_solutiongraph*.py
```

For changes that touch BrowserGraph or the viewers, run the full deterministic
suite with `pytest -q`.
