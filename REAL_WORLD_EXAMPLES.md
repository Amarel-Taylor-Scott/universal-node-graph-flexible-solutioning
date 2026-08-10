# Executable real-world example skeleton

The repository now includes six dependency-free programs, grouped into five
notebook task families, that pass through
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
```

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

Both ML examples are real DAGs rather than only lists: each split artifact fans
out to training and evaluation, while the trained model joins evaluation.

The data-cleaning baseline, mean-regression control, and majority-classification
control are expected to be rejected by their independent oracles. Preserving
those valid-but-poor routes is part of the evidence model.

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
`benchmark-solution-graph` in that order.

If the harness will generate or mutate code after the baseline exists, also
use `design-autoresearch-campaign` and freeze the evaluator boundary before the
first proposal.
