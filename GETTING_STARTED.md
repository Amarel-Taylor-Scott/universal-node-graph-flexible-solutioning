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
```

The doctor command validates all bundled schemas, templates, reference nodes,
descriptors, and generated catalog projections.

## 2. Explore reusable templates

```bash
solutiongraph templates list
solutiongraph templates list --domain machine-learning.time-series
solutiongraph templates show template.document-intelligence
solutiongraph templates show template.kaggle-tabular --json
```

The library contains 18 domain templates and 317 atomic obligations. A template
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
- `@benchmark-solution-graph` to design route experiments;
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

## 7. Validate a contribution

```bash
solutiongraph catalog export --output catalog
pytest tests/test_solutiongraph*.py -q
ruff check solutiongraph tests/test_solutiongraph*.py
```

For changes that touch BrowserGraph or the viewers, run the full deterministic
suite with `pytest -q`.
