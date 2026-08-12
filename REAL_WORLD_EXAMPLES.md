# Executable real-world example skeleton

The repository now includes 47 dependency-free programs, including five
notebook task families, 18 additional Arena fixtures, and one reusable
standard-library data-quality program, plus thirteen engineering and evaluation
showcases and ten data-science lifecycle graphs, that pass through
the same universal lifecycle: full registry admission, route compilation,
frozen fallbacks, execution, content-addressed artifacts, independent
verification, and immutable receipts.

They are intentionally small enough for a coding harness to inspect and extend.
They prove the mechanism; they do not claim production accuracy or package
coverage.

## Run from a fresh checkout

```bash
python -m pip install -e .
solutiongraph doctor
solutiongraph examples list
solutiongraph examples run browse-and-scrape
solutiongraph examples run document-to-schema
solutiongraph examples run image-check-and-process
solutiongraph examples run data-cleanup
solutiongraph examples run conflict-aware-data-contract
solutiongraph examples run event-time-windowing
solutiongraph examples run exact-gis-boundary-resolution
solutiongraph examples run idempotent-api-contract
solutiongraph examples run frontend-release-journey
solutiongraph examples run document-render-and-verify
solutiongraph examples run tabular-regression
solutiongraph examples run tabular-classification
solutiongraph examples run golden-customer-table
solutiongraph examples run address-reference-verification
solutiongraph examples run verified-product-dataset
solutiongraph examples run calibrated-time-series-forecast
solutiongraph examples run organization-entity-linking
solutiongraph examples run tested-code-repair
solutiongraph examples run multi-feed-analytical-dataset
solutiongraph examples run contact-verification
solutiongraph examples run web-change-monitoring
solutiongraph examples run transaction-reconciliation
solutiongraph examples run pii-redaction
solutiongraph examples run schema-migration
solutiongraph examples run incident-triage
solutiongraph examples run dependency-assurance
solutiongraph examples run recommendation-ranking
solutiongraph examples run scientific-experiment
solutiongraph examples run numerical-linear-system
solutiongraph examples run geotemporal-enrichment
solutiongraph examples run user-journey-modeling
solutiongraph examples run synthetic-tabular-augmentation
solutiongraph examples run synthetic-llm-curriculum
solutiongraph examples run grounded-document-extraction
solutiongraph examples run reinforcement-learning-loop
solutiongraph examples run duecare-llm-evaluation-harness
solutiongraph examples run dataset-profiling-and-drift
solutiongraph examples run wide-table-feature-reduction
solutiongraph examples run imbalanced-classification-and-calibration
solutiongraph examples run robust-regression-and-conformal
solutiongraph examples run time-series-feature-backtest
solutiongraph examples run text-classification-pipeline
solutiongraph examples run unsupervised-segmentation-and-anomaly
solutiongraph examples run model-explainability-and-stability
solutiongraph examples run ensemble-selection-and-stacking
solutiongraph examples run model-release-monitoring-and-rollback
solutiongraph examples run stdlib-data-quality
```

Use the bounded child-process adapter and persist each completed receipt before
the next experiment allocation:

```bash
solutiongraph examples run data-cleanup \
  --runtime subprocess \
  --artifact-dir .artifacts/data-cleanup \
  --receipt-journal .artifacts/receipts.jsonl
solutiongraph ledger verify .artifacts/receipts.jsonl
```

The subprocess adapter is lifecycle isolation, not a hostile-code sandbox.
The JSONL journal is tamper-evident local persistence, not authenticated WORM
storage. See `READINESS.md` and `SECURITY.md` before adapting either boundary.

Persist output artifacts locally:

```bash
solutiongraph examples run tabular-regression \
  --artifact-dir .artifacts/tabular-regression --json
```

## What each example demonstrates

| Example | Atomic obligations | Interchangeable choices | Independent result |
|---|---|---|---|
| Browse and scrape | load → extract → project schema | offline/urllib loaders; parser/regex extraction | exact title and links |
| Document to schema | normalize → extract → project | conservative/compact normalization; line/regex extraction | required field match |
| Image check/process | decode → enhance → inspect | token/line decoder; identity/min-max; direct/histogram inspection | dimensions and contrast |
| Data cleanup | normalize → deduplicate → emit | conservative/aggressive normalization; exact/normalized dedupe | unique expected entities |
| Conflict-aware data contract | profile → normalize missing → impute → resolve conflicts → validate → quarantine | baseline/reference evidence routes | valid canonical rows, field provenance, scoped imputation, and explicit quarantine |
| Event-time windowing | normalize time → dedupe → watermark → window → lateness → retractions | baseline/reference evidence routes | accepted late event, explicit too-late drop, and correction linked to the prior emission |
| Exact GIS boundary | coordinate → CRS → prefilter → exact predicate → resolve overlap → provenance | baseline/reference evidence routes | city/borough/neighborhood membership with CRS, predicate, authority, and boundary vintage |
| Idempotent API contract | validate → authorize → idempotency → execute → response contract → audit | baseline/reference evidence routes | two retries, one logical mutation, stable response, and secret-free audit evidence |
| Frontend release journey | trace → accessibility → API contracts → journey → budgets → release | baseline/reference evidence routes | accessible controls, contract-valid calls, completed journey, performance pass, and evidence-bound gate |
| Document render/verify | parse → assets → layout → render → visual checks → receipt | baseline/reference evidence routes | asset closure, two valid pages, source/output digests, and an explicit fixture-renderer boundary |
| Tabular regression | split → train → evaluate | tail/alternating split; mean/OLS training | finite predictions and RMSE threshold |
| Tabular classification | split → train → evaluate | tail/alternating split; majority/threshold training | requested labels and accuracy threshold |
| Golden customer table | normalize → validate contacts → resolve → merge | conservative/canonical cleanup; syntax/reference checks; email/multi-key grouping; first/complete merge | entity count, verified fields, completeness, provenance |
| Address reference verification | parse → normalize → reference match → emit | comma/structured parsing; basic/postal normalization; exact/alias-aware fixture match | canonical components and explicit offline-reference verdict |
| Verified product dataset | acquire → extract → normalize → corroborate | preserved/sorted captures; parser/regex; float/Decimal money; single/cross-source evidence | exact products with two-source evidence |
| Calibrated forecast | prepare → fit → forecast → intervals | observed/interpolated series; mean/trend; fixed/residual intervals | holdout MAE and coverage |
| Organization entity linking | normalize → block → link → components | basic/legal cleanup; domain/token blocking; exact/multi-evidence links | exact entity components |
| Tested code repair | inspect → propose → apply → test | AST/test inspection; operator/contract proposal; exact/line apply; AST/symbolic tests | all fixed tests and changed-file scope |
| Multi-feed analytical data | decode → normalize → reconcile → validate | CSV module/line parsing; strict/coerce; priority/completeness; schema/lineage checks | row count, total, quarantine, lineage |
| Contact verification | normalize → check syntax/reference → classify | strict/heuristic endpoint handling at every operation | verified endpoint and consent-safe disposition |
| Web change monitoring | canonicalize → compare → corroborate | strict/heuristic snapshot, diff, and evidence paths | exact significant-change event |
| Transaction reconciliation | normalize → match → balance | strict/heuristic matching and residual handling | balanced groups and explicit exceptions |
| PII redaction | detect → redact → leakage check | strict/heuristic span handling and verification | expected redaction with zero prohibited leakage |
| Schema migration | transform → validate → shadow compare | strict/heuristic migration and invariant paths | row-preserving compatible result |
| Incident triage | normalize → correlate → disposition | strict/heuristic signal and evidence handling | evidence-backed priority and hypothesis |
| Dependency assurance | inventory → policy evaluate → verdict | strict/heuristic SBOM, advisory, and license handling | expected allow/block result with findings |
| Recommendation ranking | score → policy → diversify | strict/heuristic relevance and constraint handling | eligible, deterministic diverse ranking |
| Scientific experiment | allocate → compare → robustness | strict/heuristic analysis paths | expected effect and robustness verdict |
| Numerical solve | validate → solve → residual | strict/heuristic 2×2 solver and verification paths | exact solution within residual tolerance |
| Geotemporal enrichment | normalize → reference match → timezone → time features → city/date context | permissive/strict processing at every operation | canonical record, explicit local-reference authority, UTC/time features, and provenance-bearing event join |
| User journey modeling | normalize/dedupe → sessionize → transitions → funnel → anomalies | permissive/strict event processing | exact sessions, completed funnel, and impossible-flow anomaly |
| Synthetic tabular augmentation | profile → latent aggregate → generate → constraints → privacy/utility screens → lineage split | weak/gated synthesis routes | valid novel rows, explicit non-guarantee, acceptable utility, and untouched holdout |
| Synthetic LLM curriculum | facts → views → counterfactuals → hard negatives → benign controls → family split → gates | weak/fact-grounded curriculum routes | supported examples, isolated families, lineage, and no hidden chain-of-thought target |
| Grounded document extraction | detect → layout parse → extract → ground → schema → provenance | weak/grounded extraction routes | exact values tied to source blocks and content digest |
| Reinforcement-learning loop | validate environment → propose policies → estimate → select → outer comparison | weak/bounded policy routes | correct finite-environment policy and untouched holdout |
| DueCare-style LLM harness | scenarios → SUT → deterministic grades → panel → claims → improvement → sealed receipt | self-serving/grounded harness routes | direct, benign, adversarial, disagreement, claim, lineage, and firewall checks |
| Dataset profiling/drift | schema → distributions → missingness → duplicates → drift → report | minimal/robust/alternate candidates at every stage | exact accounting, duplicate and missing findings, drift, and source-bound report |
| Wide-table feature reduction | impute → scale → variance → collinearity → relevance → project | minimal/robust/alternate candidates at every stage | non-missing reduced matrix and selected/removed feature manifest |
| Imbalanced classification | split → rebalance → fit → calibrate → threshold → slices | minimal/robust/alternate candidates at every stage | perfect fixture holdout, minority recall, slice coverage, and split lineage |
| Robust regression | group split → outliers → fit → predict → intervals → stress | minimal/robust/alternate candidates at every stage | exact outlier ledger, low held-group error, coverage, and sensitivity evidence |
| Time-series backtest | chronology → interpolate → calendar → lags → walk-forward → forecast | minimal/robust/alternate candidates at every stage | gap evidence, no shuffle, low backtest error, and ordered forecast intervals |
| Text classification | normalize → tokenize → n-grams → vectorize → fit → evaluate | minimal/robust/alternate candidates at every stage | untouched-document predictions and fixture accuracy |
| Segmentation/anomaly | scale → choose k → cluster → assign → anomaly → profile | minimal/robust/alternate candidates at every stage | cluster evidence, complete assignments, anomaly, and segment summaries |
| Explainability/stability | register → importance → resample → slices → counterfactual → card | minimal/robust/alternate candidates at every stage | model/data identity, stable ranking, slice results, scoped counterfactual, limitations |
| Ensemble/stacking | collect OOF → lineage → prune → blend → calibrate → holdout | minimal/robust/alternate candidates at every stage | no fold leakage, weak-model removal, weights, and untouched-holdout error |
| Model release/rollback | package → replay → shadow → drift → gate → rollback | minimal/robust/alternate candidates at every stage | exact identities, non-mutating shadow, human-gated approval, rollback target |
| Standard-library data quality | normalize keys → trim → normalize missing → case-fold/pass → filter/pass → deduplicate/pass → profile | 19 reusable source-bound primitives expanded into 32 candidate bindings | exact normalized records, profile, and deterministic digest |

Both ML examples are real DAGs rather than only lists: each split artifact fans
out to training and evaluation, while the trained model joins evaluation.

Forty-four controls are expected to be rejected by their independent oracles.
Preserving those valid-but-poor routes is part of the evidence model. The
release gate compiles and executes all 120 declared routes through both runtime
adapters.

The thirteen showcase mechanisms and the linked-graph DueCare-style boundary are
explained in
[ENGINEERING_DAG_AND_DUECARE_HARNESS_SHOWCASE.md](ENGINEERING_DAG_AND_DUECARE_HARNESS_SHOWCASE.md).
The broader 560-technique lifecycle mapping, 729-route composition model, and
node-pack extension seams are documented in
[DATA_SCIENCE_AI_ML_PIPELINE_EXAMPLES.md](DATA_SCIENCE_AI_ML_PIPELINE_EXAMPLES.md).
The catalog also publishes a strict evidence closure containing criterion-level
judgments, blinded panels, a development failure cluster, an aggregate-only
outer summary, and a two-human promotion decision with rollback identity.

Six of the programs are also packaged as controlled benchmark suites with exact
task/case/oracle identities, fixed controls, quick and balanced solver arms,
holdout status, and JSON/HTML evidence. Run `solutiongraph benchmarks list` and
read `BENCHMARK_PROTOCOL.md`.

## Let the universal solver choose routes

Declared routes prove specific positive and negative controls. The solver also
explores combinations directly from every compiler-admitted candidate column:

```bash
solutiongraph solve golden-customer-table --profile quick
solutiongraph solve golden-customer-table --profile balanced
solutiongraph solve golden-customer-table --profile broad --runtime subprocess
solutiongraph solve address-reference-verification \
  --profile exhaustive --allow-exhaustive
```

The result includes search coverage, learned belief revisions, receipts,
rankings, a Pareto set, an accepted champion, and separately evaluated diverse
fallback routes. See `UNIVERSAL_DAG_ARENA.md` for the profile contract.

## Notebooks

- `notebooks/01_browse_and_scrape.ipynb`
- `notebooks/02_document_to_schema.ipynb`
- `notebooks/03_image_check_and_process.ipynb`
- `notebooks/04_data_cleanup.ipynb`
- `notebooks/05_tabular_machine_learning.ipynb`

Every notebook calls the same public `run_example()` API and can write its
content-addressed outputs under `.artifacts/`.

## Where an LLM harness extends the skeleton

The semantic slots should remain implementation-neutral. Add mature packages
as new node packs rather than replacing the compiler or hiding a package choice
inside one mega-node:

| Domain | Natural additional node families |
|---|---|
| Web | BrowserGraph, Playwright, Selenium, CDP, authenticated sessions, robots/policy checks, structured extractors |
| Documents | PDF parsers, DOCX, OCR, layout recovery, language detection, translation, chunking, deterministic/LLM extraction |
| Images | Pillow, OpenCV, OCR, EXIF, forensic detectors, classical vision, learned vision models, encoders |
| Data quality | pandas, Polars, postal/address parsers, USPS/Census connectors, entity linkage, sampled review |
| ML | scikit-learn, XGBoost, LightGBM, CatBoost, neural models, calibration, MAPIE/conformal, ensembles, packaging |
| Forecasting | statsmodels, sktime, Prophet, gradient boosting, conformal intervals, hierarchical reconciliation |
| Entity resolution | Splink, recordlinkage, probabilistic pair scoring, graph clustering, human-review queues |
| Code repair | language parsers, linters, test runners, patch sandboxes, dependency/security checks, isolated build systems |
| Data engineering | Arrow, DuckDB, dbt, Great Expectations, Soda, API capture, schema registries, warehouse publishers |

For forecasting, ranking, clustering, anomaly detection, deep learning, or
multimodal systems, refine the relevant catalog template and add task-specific
value types and verifiers. Do not force those semantics through either small
tabular program merely because it is already executable.

## Minimum acceptance for a contributed executable domain

1. Use a real task input or clearly labeled mechanism fixture.
2. Define an independent oracle before selecting nodes.
3. Refine schematic types into explicit domain types and schemas.
4. Provide at least two genuine candidates for multiple obligations.
5. Run the full registry through compiler admission.
6. Freeze exact implementation identities and fallbacks.
7. Execute a fixed baseline and alternatives.
8. Preserve failures, artifacts, environment, seeds, and receipts.
9. Add a holdout before learning or optimization claims.
10. Label in-process examples separately from isolated production execution.

Read `EXECUTION_PROTOCOL.md`, then use the workspace skills
`model-solution-graph`, `author-node-pack`, `execute-solution-graph`, and
`benchmark-solution-graph` in that order. Use `solve-universal-dag` when adding
or solving an Arena task end to end.

If the harness will generate or mutate code after the baseline exists, also
use `design-autoresearch-campaign` and freeze the evaluator boundary before the
first proposal.
