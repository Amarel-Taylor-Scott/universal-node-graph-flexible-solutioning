# Adoption guide: where SolutionGraph fits

SolutionGraph is an external-alpha compiler and experiment layer for software
whose implementation choices can be represented as typed graphs. It is useful
today for designing spaces, packaging reusable nodes, running trusted local
experiments, and integrating an LLM coding harness. It is not yet a hosted
scheduler, marketplace, hostile-code sandbox, or proof of universal real-world
superiority.

## The practical wedge

Existing workflow systems are good at running a graph you already chose.
SolutionGraph focuses on the earlier and later questions:

```text
task contract
   -> semantic obligations
   -> all admitted implementations per obligation
   -> compiler-valid route space
   -> bounded or exhaustive experiments
   -> independently verified receipts
   -> champion + failure-diverse fallbacks
```

The portable unit is not one DAG. It is a content-addressed `SolutionPack` that
contains the task definition, candidate graph programs, closed registry
snapshots, node packs, cases, evaluator, baselines, and benchmark allocation.
That gives teams and coding agents a shared object to build, audit, reproduce,
and improve.

This can complement—not replace—Dagster, Prefect, Temporal, Ray, Kubernetes,
serverless platforms, databases, model providers, and domain libraries. Those
systems can become runtime, scheduling, artifact, registry, or node adapters.
SolutionGraph owns portable semantics, admission, route identity, experiment
accounting, and evidence boundaries.

## Good first users

- an LLM coding harness that needs strict rules for decomposing a ticket and
  proving a generated graph works;
- a data/ML team comparing preprocessing, features, models, ensembles, and
  validation paths without hiding combinations in notebooks;
- a document, web, image, or entity-processing team with multiple providers and
  deterministic fallbacks;
- a platform team building a governed node registry across projects;
- a research team that needs bounded AutoResearch-style candidate generation,
  lineage, fixed evaluation, and negative evidence;
- a systems team that wants a portable specification above its current
  orchestrator rather than another vendor-specific DAG definition.

## Start with one bounded task

Do not begin by modeling an entire company or claiming every program is a DAG.
Choose one measurable workflow with replaceable implementation choices:

1. freeze exact input/output and an independent oracle;
2. select one of the 31 semantic templates and remove irrelevant obligations;
3. split remaining obligations until candidates are genuine substitutes;
4. reuse or author strict nodes;
5. compile the complete snapshot;
6. freeze a control route;
7. run bounded solver arms on development cases and confirm on holdout;
8. publish the solution pack, evidence report, and remaining production gates;
9. adapt the selected frozen plan to the operational runtime.

Use `solutiongraph init`, then give the generated workspace and repository
skills to the coding harness:

```bash
solutiongraph init customer-quality --template template.data-cleaning
solutiongraph packs list
solutiongraph benchmarks list
solutiongraph benchmarks run benchmark.stdlib-data-quality \
  --report-html .artifacts/report.html \
  --report-json .artifacts/report.json
```

## What is reusable

| Layer | Reuse boundary |
|---|---|
| Semantic template | A domain decomposition hypothesis; no implementation claim. |
| Node definition | One strict executable ABI and content digest. |
| Candidate | Exact node version, implementation digest, parameter binding, and deployment. |
| Node pack | Portable implementation collection plus optional discovery sidecars. |
| Task contract | Stable problem meaning and evaluator identity. |
| Solution pack | Reproducible closure for one task and its solution universe. |
| Belief revision | Contextual observational prior tied to evidence; never universal truth. |
| Frozen plan | Exact deployable route with no mutable optimizer score. |
| Receipt/report | Immutable observation and human-readable projection. |

## How an LLM harness should use it

The harness may propose templates, slots, topology variants, node source,
candidate bindings, and search anchors. It may not invent compatibility,
authority, evaluator results, or benchmark evidence.

Its loop should be:

1. read `AGENTS.md` and activate the narrow repository skill;
2. restate the task contract before writing nodes;
3. search registries and record coverage gaps;
4. generate missing nodes into quarantine;
5. validate source-bound contracts and tests;
6. compile every candidate against every slot in the frozen snapshot;
7. run fixed and solver benchmark arms through an independent oracle;
8. keep failures and negative evidence;
9. update a new belief revision;
10. submit a frozen plan and evidence, never prose confidence alone.

Prompt instructions improve consistency. Schemas, compiler checks, content
digests, runtime policy, evaluator isolation, and CI provide enforcement.

## Market test, not market mythology

The repository can help people now as a serious template, compiler, conformance
suite, and experimental skeleton. Whether it becomes a market category depends
on evidence still to be earned:

- third parties can model a new task without maintainers rewriting the core;
- reusable nodes transfer between at least three unrelated task families;
- bounded search beats declared controls under fixed budgets and clean holdouts;
- integrations execute frozen plans on mature external runtimes;
- contributors publish interoperable node and solution packs;
- setup time and debugging time improve versus ordinary one-off pipelines;
- safety and provenance claims survive independent review.

Track those outcomes publicly. Candidate counts and large theoretical route
spaces are not adoption metrics.

## Production boundary

Before production, supply an enforcing runtime for untrusted code, external
authorization and secret brokerage, durable distributed scheduling, telemetry,
retention, tenant isolation, incident response, and domain-specific validation.
Use `READINESS.md` as the authoritative support matrix.

The strongest near-term position is precise: SolutionGraph makes the complete
space of valid implementations inspectable and experimentally comparable, while
keeping task meaning, authority, optimization, execution, and evidence separate.
