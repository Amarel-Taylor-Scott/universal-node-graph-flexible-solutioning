# Executable real-world example skeleton

The repository now includes 13 dependency-free programs, including five
notebook task families and seven additional Arena fixtures, that pass through
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
solutiongraph examples run tabular-regression
solutiongraph examples run tabular-classification
solutiongraph examples run golden-customer-table
solutiongraph examples run address-reference-verification
solutiongraph examples run verified-product-dataset
solutiongraph examples run calibrated-time-series-forecast
solutiongraph examples run organization-entity-linking
solutiongraph examples run tested-code-repair
solutiongraph examples run multi-feed-analytical-dataset
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
| Tabular regression | split → train → evaluate | tail/alternating split; mean/OLS training | finite predictions and RMSE threshold |
| Tabular classification | split → train → evaluate | tail/alternating split; majority/threshold training | requested labels and accuracy threshold |
| Golden customer table | normalize → validate contacts → resolve → merge | conservative/canonical cleanup; syntax/reference checks; email/multi-key grouping; first/complete merge | entity count, verified fields, completeness, provenance |
| Address reference verification | parse → normalize → reference match → emit | comma/structured parsing; basic/postal normalization; exact/alias-aware fixture match | canonical components and explicit offline-reference verdict |
| Verified product dataset | acquire → extract → normalize → corroborate | preserved/sorted captures; parser/regex; float/Decimal money; single/cross-source evidence | exact products with two-source evidence |
| Calibrated forecast | prepare → fit → forecast → intervals | observed/interpolated series; mean/trend; fixed/residual intervals | holdout MAE and coverage |
| Organization entity linking | normalize → block → link → components | basic/legal cleanup; domain/token blocking; exact/multi-evidence links | exact entity components |
| Tested code repair | inspect → propose → apply → test | AST/test inspection; operator/contract proposal; exact/line apply; AST/symbolic tests | all fixed tests and changed-file scope |
| Multi-feed analytical data | decode → normalize → reconcile → validate | CSV module/line parsing; strict/coerce; priority/completeness; schema/lineage checks | row count, total, quarantine, lineage |

Both ML examples are real DAGs rather than only lists: each split artifact fans
out to training and evaluation, while the trained model joins evaluation.

Nine controls are expected to be rejected by their independent oracles.
Preserving those valid-but-poor routes is part of the evidence model. The
release gate compiles and executes all 31 declared routes through both runtime
adapters.

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
