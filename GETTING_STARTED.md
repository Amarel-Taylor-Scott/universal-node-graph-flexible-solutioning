# Getting Started

Universal Node Graph can be explored without a browser, model provider, vector
database, or network service. The domain-neutral core uses only the Python
standard library. Version 0.7 is a developer preview; read `READINESS.md`
before production integration.

## Interrogate a dataset before building a pipeline

For CSV, TSV, JSON, or JSONL records, the shortest evidence-producing path is:

```bash
solutiongraph concepts map examples/data/dirty_organizations.json
solutiongraph questions plan examples/data/dirty_organizations.json --effort E3
solutiongraph questions run examples/data/dirty_organizations.json \
  --effort E3 --output-dir .artifacts/interrogation
```

The planner displays selected, deferred, blocked, and inapplicable questions;
it never silently hides the remainder of the bank. The run operates on a deep
shadow copy, emits implementation-bound check receipts, redacts patch values in
portable reports, and records an independent promote/quarantine/reject decision.
See [the semantic interrogation protocol](SEMANTIC_INTERROGATION_PROTOCOL.md)
before adding authority lookups, LLM adjudication, or automatic corrections.

## Design a data-science or AI system before compiling it

The design atlas turns a task archetype into an all-visible worklist with
branches, required evidence, experiment templates, stop conditions, research
sources, and explicit capability/permission blocking:

```bash
solutiongraph atlas archetypes
solutiongraph atlas coverage
solutiongraph atlas plan \
  --context examples/data-science-design-context.json \
  --effort E3 \
  --output-dir .artifacts/data-science-design
```

Open the self-contained HTML report or pass the JSON to a human/LLM harness.
The 618 technique entries are catalog records, not executable node claims. Read
[the design-atlas guide](DATA_SCIENCE_DESIGN_ATLAS.md) before translating a
decision dossier into nodes, graph mutations, or benchmark arms.

To exercise the same lifecycle through typed ports, compiler admission, a
frozen plan, an independent verifier, and runtime receipts:

```bash
python examples/data_science_design_atlas_graph.py --runtime subprocess
```

The fixture grants `human.review`; switch to the model planning implementation
only by building the program with `model.invoke` and supplying a compatible
answer-set producer.

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
projections. The release verifier then compiles and executes all 120 frozen
reference routes, checks 44 declared negative controls, runs 11 installed-wheel
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

Run the minimal compiler example and the complete control/mutation experiment:

```bash
python examples/solutiongraph_quickstart.py
python examples/control_vs_mutated_graph_experiment.py
python examples/discovery_and_templates.py
```

Choose prior, beam, seeded-sprout, or explicitly exhaustive search according to
the available budget. Search reports preserve coverage, skips, invalid routes,
duplicates, unvisited routes, seeds, and belief revision. The graph experiment
executes one exact control beside compiler-gated typed topology mutations, uses common
cases/seeds/objectives, and reports raw control deltas, Pareto membership, and a
transparent weighted projection. See `GRAPH_EXPERIMENTS.md`.

## 8. Use intelligent task solutioning

Inspect a complete task binding before any execution, then run it:

```bash
solutiongraph solutioning inspect data-cleanup --effort 1
solutiongraph solutioning run data-cleanup --effort 1
python examples/intelligent_solutioning_study.py
```

The inspect command shows task classification, fingerprint attributes, exact
compiler admission, the effort policy, historical recommendations, randomized
sprouts, and protected history-blind starting lanes. The run command continues
through frozen plans, ordinary execution and verification, ranking, and
matched-budget negative-transfer assessment.

The Python example closes cold-start development receipts into a new immutable
history snapshot, reuses it for a warm start, generates a topology mutation,
and analyzes matched control/candidate receipts with uncertainty and practical-
effect thresholds. History remains a prior, not an admission or acceptance
authority. See `INTELLIGENT_SOLUTIONING.md`.

## 9. Solve and execute the reference domain skeletons

Inspect all 52 Arena contracts and execute or solve the 40 Arena-linked local programs:

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
solutiongraph benchmarks adapters
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

`solutiongraph benchmarks adapters` lists strict manifest profiles for Kaggle,
MLE-bench, SkillsBench, SWE-bench, BrowserGym, and DueCare-style evaluations.
Run `python examples/external_benchmark_adapter.py` for a side-effect-free
normalization example. Fetching, credential use, execution, submission, and
external score claims remain separate authorized integrations.

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

## 10. Compare coding agents with and without repository context

Run the safe 10-task/20-trial transport and evaluator smoke:

```bash
solutiongraph agent-bench tasks
solutiongraph agent-bench smoke --output .artifacts/agent-benchmark-smoke
solutiongraph agent-bench journal-verify \
  .artifacts/agent-benchmark-smoke/trial-receipts.jsonl
```

The fixture uses the same prompt, task, public case, harness label, model label,
budget, seed, and repetition across each pair. Only the treatment workspace
receives the digest-pinned SolutionGraph context pack. It calls no model and
should report practical equivalence; that proves transport, evaluator, receipt,
analysis, diagram, and report behavior—not an efficacy uplift.

Prepare a real matrix without executing it:

```bash
solutiongraph agent-bench example-config --output agent-benchmark.local.json
solutiongraph agent-bench plan agent-benchmark.local.json
```

Pin and enable the intended OpenCode, Aider, or private command harnesses and
small-to-frontier models, then use `agent-bench run ... --allow-external` only
inside an appropriate isolation boundary. Follow
`LLM_AGENT_BENCHMARK_ARENA.md` and notebook
`notebooks/06_llm_harness_ab_arena.ipynb` for the full protocol and analysis.

## 11. Validate a contribution

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
