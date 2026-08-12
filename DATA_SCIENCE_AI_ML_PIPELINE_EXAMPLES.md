# Data-science and AI/ML pipeline examples

This repository includes a source-bound data-science lifecycle node pack with
ten executable graph families, 60 typed stage nodes, and 180 exact candidate
bindings. The pack turns a broad data-science technique inventory into small,
composable obligations instead of one opaque `run_ml_pipeline` node.

The examples are deterministic standard-library mechanism fixtures. They prove
that the compiler, candidate matrix, executor, independent verifier, receipts,
and subprocess boundary work across the lifecycle. They do not claim the
accuracy, scalability, numerical behavior, privacy guarantees, or production
readiness of scikit-learn, pandas, XGBoost, PyTorch, a feature store, or an MLOps
platform.

## Run the examples

```bash
solutiongraph examples run dataset-profiling-and-drift --route all
solutiongraph examples run wide-table-feature-reduction --route all
solutiongraph examples run imbalanced-classification-and-calibration --route all
solutiongraph examples run robust-regression-and-conformal --route all
solutiongraph examples run time-series-feature-backtest --route all
solutiongraph examples run text-classification-pipeline --route all
solutiongraph examples run unsupervised-segmentation-and-anomaly --route all
solutiongraph examples run model-explainability-and-stability --route all
solutiongraph examples run ensemble-selection-and-stacking --route all
solutiongraph examples run model-release-monitoring-and-rollback --route all
```

Exercise lifecycle isolation and persist evidence:

```bash
solutiongraph examples run model-release-monitoring-and-rollback \
  --route hybrid-reference \
  --runtime subprocess \
  --artifact-dir .artifacts/model-release \
  --receipt-journal .artifacts/data-science-receipts.jsonl --json
solutiongraph ledger verify .artifacts/data-science-receipts.jsonl
```

Let the universal solver allocate routes instead of running only the four named
evidence routes:

```bash
solutiongraph solve robust-regression-and-conformal --profile balanced
solutiongraph solve text-classification-pipeline --profile broad --runtime subprocess
```

## What is executable

| Graph family | Six typed obligations | Independent acceptance evidence |
|---|---|---|
| Dataset profiling and drift | schema → distributions → missingness → duplicates → drift → quality report | row/column accounting, exact missing and duplicate findings, source digest |
| Wide-table feature reduction | impute → scale → variance → collinearity → relevance → reduced matrix | no missing outputs, constant removal, bounded selected feature set, feature manifest |
| Imbalanced classification | split → rebalance → fit → calibrate → threshold → slices | holdout accuracy, minority recall, both group slices, split lineage |
| Robust regression | group split → outliers → fit → predict → intervals → stress | exact outlier ledger, held-group RMSE, coverage, perturbation sensitivity |
| Time-series backtest | chronology → interpolate → calendar → lags → walk-forward → forecast | gap accounting, no shuffle, backtest MAE, ordered intervals and horizons |
| Text classification | normalize → tokenize → n-grams → vectorize → fit → evaluate | held-document predictions and accuracy with explicit train/holdout identity |
| Segmentation and anomaly | scale → choose k → fit clusters → assign → anomalies → profiles | cluster-count evidence, complete assignments, anomaly identity, segment summaries |
| Explainability and stability | register → importance → resample → slices → counterfactual → model card | model/data digests, stable ranking, slice scores, scoped counterfactual and limitations |
| Ensemble and stacking | collect OOF → audit lineage → prune → blend → calibrate → holdout | fold disjointness, weak-model removal, exact weights, untouched-holdout error |
| Release and rollback | package → replay → shadow → drift → gate → rollback | content identity, replay match, quality delta, drift threshold, human gate, rollback target |

Each graph has six slots and three candidates per slot. The compiler therefore
admits `3^6 = 729` complete routes per example. Four routes are named and run in
the release gate:

- `minimal-control`: runs the mechanics but records insufficient evidence at
  every stage; the independent verifier rejects it.
- `robust-reference`: uses robust or evidence-maximizing choices throughout.
- `alternate-reference`: uses a genuinely different accepted method at every
  stage.
- `hybrid-reference`: alternates robust and alternate candidates, proving that
  accepted components can be recombined without adding a new hard-coded
  pipeline.

The remaining 725 routes are visible to search. They are not silently declared
successful. A solver profile decides which of them receives execution budget,
and all observed failures remain evidence.

## Mapping the broader technique inventory

The supplied inventory groups roughly 560 possible techniques into 21 lifecycle
areas. The normalized source inventory is preserved in
[TAEDRI_DATA_SCIENCE_TECHNIQUE_TAXONOMY.md](TAEDRI_DATA_SCIENCE_TECHNIQUE_TAXONOMY.md).
The executable pack deliberately represents the stable *obligations* and
extension seams, not every package or algorithm as a built-in dependency.

| Technique area | Existing executable seam | Natural additional candidates |
|---|---|---|
| Data loading and ingestion | other real-world/engineering examples cover feeds, contracts, and event time | CSV/JSONL/Parquet/Arrow, database snapshots, object stores, schema-on-read, streaming connectors |
| Dataset profiling | profiling-and-drift | approximate sketches, quantiles, cardinality estimators, semantic typing, dataset embeddings |
| EDA | profiling-and-drift plus scientific experiment | association matrices, interaction discovery, automated plots, cohort comparison, report generation |
| Cleaning | feature reduction and conflict-aware data contract | KNN/MICE/model imputation, winsorization, learned repairs, category consolidation, text/date normalization |
| Feature engineering | feature reduction and time-series backtest | ratios, interactions, splines, target-safe encodings, geospatial, temporal, text/image/document embeddings |
| Dimensionality reduction | feature reduction | PCA/SVD/ICA/NMF, UMAP/t-SNE for analysis, autoencoders, supervised projections |
| Feature selection | feature reduction and explainability | mutual information, RFE, stability selection, L1/elastic net, SHAP-based selection, Boruta |
| Target engineering | classification and regression | transformations, censoring, multilabel expansion, ordinal targets, survival/event definitions |
| Splitting and validation | classification, regression, time series, text, ensembles | nested CV, grouped/blocked/purged folds, spatial CV, repeated seeds, leakage adversaries |
| Model selection | classification, regression, text, clustering | linear, generalized linear, tree, boosted tree, kernel, nearest-neighbor, neural, transformer, hybrid models |
| Training | model-specific fit slots | early stopping, checkpoints, class/cost weights, distributed training, mixed precision, curriculum learning |
| Hyperparameter tuning | universal solver candidate bindings and topology search | grids, random search, Bayesian optimization, successive halving, population-based training |
| AutoML | universal solver plus task-history priors | provider adapters, constrained pipeline synthesis, meta-learned warm starts, budget-aware ensembling |
| Ensembles | ensemble-selection-and-stacking | voting, blending, stacking, bagging, boosting, snapshot ensembles, mixture-of-experts gates |
| Calibration and post-processing | classification and ensemble calibration | isotonic, Platt/beta/temperature scaling, monotonic constraints, conformal sets, decision policies |
| Metrics and evaluation | every example has an independent verifier | task-specific metrics, confidence intervals, paired tests, fairness, utility/cost curves, robustness suites |
| Stability and robustness | regression stress, time backtest, explanation stability, drift | bootstrap confidence, seed sensitivity, perturbation/adversarial tests, subgroup drift, OOD checks |
| Interpretability | explainability-and-stability | permutation, PDP/ICE/ALE, SHAP, LIME, prototypes, counterfactual search, causal caveat checks |
| Feedback and learning | receipts, belief model, task-history layer | error analysis, active learning, label review, champion/challenger evidence, negative-transfer monitoring |
| Deployment and serving | release-monitoring-and-rollback | model registry, batch/online serving, canary, shadow, feature parity, observability, approval and rollback connectors |
| Existing/proposed Taedri slots | all ten graphs plus task fingerprints | historical route retrieval, learned sprouts, task embeddings, portfolio policies, adaptive effort levels |

This distinction is important. `RobustScaler`, `StandardScaler`, PCA, UMAP,
LightGBM, a transformer, and a remote AutoML service should be independently
identified candidates with exact versions, effects, resources, and failure
modes. Hiding them behind a string switch in a production mega-node would
weaken provenance and make admission, fallback, and historical learning less
useful.

## Task fingerprints and history-informed starting points

The task-intelligence protocol in
[TAEDRI_TASK_FINGERPRINT_HISTORY_INFORMED_SEARCH.md](TAEDRI_TASK_FINGERPRINT_HISTORY_INFORMED_SEARCH.md)
can use these graphs as the first concrete data-science vocabulary. A new task
can progressively publish features such as:

- objective family: regression, binary/multiclass/multilabel classification,
  ranking, forecasting, clustering, anomaly detection, generation, or policy
  learning;
- modality and structure: tabular, text, document, image, audio, graph,
  geospatial, event stream, time series, or multimodal;
- shape: row and feature counts, sparsity, wide/tall ratio, cardinality,
  feature-type proportions, sequence lengths, and graph density;
- target profile: prevalence, entropy, moments, skew, tails, modes, censoring,
  zero inflation, ordinal structure, label noise, and group/time dependence;
- feature profile: missingness patterns, uniqueness, moments, tails, outliers,
  mutual dependence, collinearity components, stationarity, autocorrelation,
  spatial concentration, and semantic-type confidence;
- data quality and lineage: duplicates, schema conflicts, source count,
  freshness, authority, coverage, join loss, potential leakage, and split risk;
- operational constraints: latency, memory, privacy, interpretability,
  determinism, update cadence, deployment boundary, cost, and human authority;
- compact representations: task-description embedding, schema/column-name
  embedding, pooled feature-profile vector, sampled-data embedding, target
  distribution embedding, and graph/topology embedding.

History retrieval should combine several channels rather than collapse all of
this into one similarity score:

1. exact objective and modality matches;
2. categorical taxonomy overlap;
3. normalized numeric-profile distance;
4. task/schema/data-profile embedding similarity;
5. past route performance, uncertainty, failures, and environment compatibility;
6. diversity from already selected starts.

Retrieved history remains advisory. It may seed suggested candidates, sprouts,
topologies, and effort allocations, but it cannot bypass current registry
admission, frozen-plan compilation, execution, or the current task's oracle.
Always reserve history-blind and randomized lanes, enforce a matched total
budget, and record negative transfer when historical starts underperform.

## Extension patterns

### Add a mature library implementation

Author one node for one atomic obligation. For example, a scikit-learn scaler
candidate should declare the exact input/output types, fitted-state artifact,
package/version closure, deterministic seed behavior, memory requirements, and
failure modes. Bind configuration values as candidates, publish them in a new
node pack, and allow the compiler to admit them beside the dependency-free
fixture candidates.

Do not replace the fixture implementation in place. Keeping both preserves a
portable control, avoids false digest continuity, and gives the solver and
history layer real alternatives.

### Add a new pipeline family

1. Freeze the task contract, output schema, split boundary, oracle, objectives,
   and budget.
2. Choose the closest Arena template and refine it into atomic typed slots.
3. Reuse compatible nodes and author only missing obligations.
4. Include a fixed weak control and at least two plausible routes.
5. Admit the complete registry; inspect candidate counts and route upper bound.
6. Execute in-process and through the intended isolation boundary.
7. Preserve receipts, artifacts, failures, unvisited space, and claim scope.
8. Add the task to the Arena only at the readiness level the evidence supports.

### Represent nested or non-linear workflows

The six-stage examples are intentionally readable, not a limit on topology.
Use fan-out/fan-in for parallel feature families or model candidates, bounded
loop lowering for iterative training, conditional branches for schema/modality
choices, composite graphs for reusable subpipelines, and saga compensation for
effectful release operations. Topology search can compare those graph shapes
separately from candidate selection.

### Keep evaluation outside the candidate's authority

The candidate may emit predictions and diagnostics; acceptance belongs to the
task case's independent verifier. For learned historical starts, keep
development, validation, and sealed outer evaluation identities distinct.
Human release authority, privacy claims, fairness policy, and external-data
authority must remain explicit rather than inferred from a passing fixture.

## Source locations

- Executable definitions: `solutiongraph/examples/data_science_tasks.py`
- Portable node-pack manifest: `solutiongraph/pack_library.py`
- Arena contracts: `solutiongraph/arena.py`
- Generated catalog: `catalog/nodepacks/data-science-lifecycle/`
- Conformance tests: `tests/test_solutiongraph_data_science.py`
- Historical-start design: `TAEDRI_TASK_FINGERPRINT_HISTORY_INFORMED_SEARCH.md`
- General engineering/harness examples: `ENGINEERING_DAG_AND_DUECARE_HARNESS_SHOWCASE.md`
