# Taedri data-science and AI/ML technique inventory

> Historical snapshot: this 2026-08-12 Markdown is retained as supplied source
> context. The current 2026-08-13 inventory is normalized into 618 strict C1
> catalog entries under `solutiongraph/design_atlas/data/techniques.json` and
> projected into `catalog/design-atlas/`. Source status labels are unverified
> provenance, not SolutionGraph maturity. See
> [DATA_SCIENCE_DESIGN_ATLAS.md](DATA_SCIENCE_DESIGN_ATLAS.md).

> Provenance and claim boundary: this catalogue was supplied by the project owner on
> 2026-08-12. Its Taedri status column describes that separate source implementation
> as reported in the supplied inventory; it is not a SolutionGraph implementation or
> readiness claim. See [the executable lifecycle guide](DATA_SCIENCE_AI_ML_PIPELINE_EXAMPLES.md)
> for the mechanisms actually implemented and verified in this repository.

## Complete technique taxonomy

## Every step, substep, and technique — with Taedri implementation status

**Legend:**
- ✅ **Implemented in Taedri** — has a graph slot + fillings
- 🔶 **Partially implemented** — has fillings but no dedicated slot, or slot exists but limited fillings
- 🔲 **Designed but not built** — in `deep_graph_fillings.py` or planned
- ❌ **Not implemented** — known technique, not yet in Taedri's graph

---

## 1. DATA LOADING & INGESTION

| Step | Technique | Taedri | Notes |
|---|---|---|---|
| 1.1 File format detection | CSV, Parquet, JSON, Excel, Feather, ORC, Avro | ✅ | `task_file_roles.py` handles CSV/Parquet |
| 1.2 Schema inference | Header detection, dtype inference, date parsing | ✅ | `frozen_grader.py` reads schemas |
| 1.3 Multi-file assembly | Train/test split files, multiple CSVs, sharded data | ✅ | Task manifest specifies file roles |
| 1.4 Database ingestion | SQL queries, connection pooling, incremental reads | ❌ | Not in scope for benchmark tasks |
| 1.5 Streaming ingestion | Kafka, Kinesis, event streams, change data capture | ❌ | Batch-only currently |
| 1.6 API ingestion | REST, GraphQL, SDK-based data fetching | ❌ | Not in scope |
| 1.7 Data versioning | DVC, Pachyderm, Delta Lake, Iceberg | ❌ | Task capsules provide content addressing |
| 1.8 Data validation on load | Great Expectations, schema enforcement, constraint checking | 🔶 | Task contracts exist; no runtime validation suite |

---

## 2. DATA UNDERSTANDING & PROFILING

| Step | Technique | Taedri | Notes |
|---|---|---|---|
| 2.1 Basic statistics | Count, mean, std, min, max, quartiles, median | ✅ | `task_profile_prior.py` computes these |
| 2.2 Missing value analysis | Missing count, missing pattern, missing mechanism (MCAR/MAR/MNAR) | ✅ | Engine detects missingness; no mechanism classification |
| 2.3 Cardinality analysis | Unique count per column, cardinality ratio | ✅ | Used for encoding strategy selection |
| 2.4 Distribution analysis | Skewness, kurtosis, normality tests (Shapiro-Wilk, KS) | 🔶 | Skewness used for target transform gating |
| 2.5 Correlation analysis | Pearson, Spearman, Kendall, distance correlation | ✅ | Pearson used in feature selection slot |
| 2.6 Collinearity detection | VIF, condition number, correlation matrix clustering | 🔲 | `collinearity_group_medoid` in deep fillings |
| 2.7 Outlier detection | IQR, Z-score, isolation forest, LOF, DBSCAN | 🔶 | Winsorize in feature_taming; no dedicated outlier slot |
| 2.8 Data type classification | Numeric, categorical, ordinal, text, datetime, image, geospatial | ✅ | `task_file_roles.py` classifies columns |
| 2.9 Target analysis | Target distribution, class balance, target leakage detection | ✅ | Target transform slot; class weights in row_weighting |
| 2.10 Feature-target relationship | Mutual information, ANOVA F-test, chi-squared, SHAP dependence | 🔶 | Mutual info in deep fillings; no SHAP |
| 2.11 Data quality report | Automated profiling (pandas-profiling, sweetviz, ydata-profiling) | ❌ | Not automated; manual inspection |
| 2.12 Drift detection | PSI, KS test, Jensen-Shannon divergence, MMD | ❌ | Not implemented |
| 2.13 Duplicate detection | Exact duplicates, fuzzy duplicates, near-duplicates | ❌ | Not implemented |
| 2.14 Constant/binary feature detection | Zero variance, near-zero variance, single-value columns | ✅ | Variance threshold in deep fillings |

---

## 3. EXPLORATORY DATA ANALYSIS (EDA)

| Step | Technique | Taedri | Notes |
|---|---|---|---|
| 3.1 Univariate visualization | Histograms, KDE, box plots, violin plots, bar charts | ❌ | Visualization not in scope |
| 3.2 Bivariate visualization | Scatter plots, hexbin, correlation heatmaps, pair plots | ❌ | Visualization not in scope |
| 3.3 Multivariate visualization | PCA projection, t-SNE, UMAP, parallel coordinates | ❌ | Visualization not in scope |
| 3.4 Time series EDA | Trend, seasonality, autocorrelation, stationarity tests | 🔶 | `calendar-features.json` profile; no dedicated slot |
| 3.5 Text EDA | Word clouds, n-gram frequency, TF-IDF, topic modeling | ❌ | `TF_TEXT` arm exists but unused |
| 3.6 Geospatial EDA | Map plots, spatial autocorrelation, hotspot analysis | ❌ | Not in scope |
| 3.7 Automated EDA | AutoViz, D-Tale, Lux, Bamboolib | ❌ | Not automated |
| 3.8 Hypothesis testing | t-test, ANOVA, chi-squared, Mann-Whitney, bootstrap tests | ❌ | Not implemented |
| 3.9 Effect size measurement | Cohen's d, eta-squared, Cramer's V, odds ratio | ❌ | Not implemented |

---

## 4. DATA CLEANING & PREPROCESSING

### 4.1 Missing Value Handling

| Technique | Taedri | Notes |
|---|---|---|
| 4.1.1 Deletion — listwise (drop rows with any NA) | ❌ | Not a filling; could be a pre-filter |
| 4.1.2 Deletion — pairwise (drop for specific analyses) | ❌ | Not implemented |
| 4.1.3 Deletion — column drop (drop columns above threshold) | ❌ | Not a filling |
| 4.1.4 Simple imputation — mean | ✅ | `median_fill` in missing_repair slot |
| 4.1.5 Simple imputation — median | ✅ | `median_fill` in missing_repair slot |
| 4.1.6 Simple imputation — mode / most frequent | ❌ | Not a separate filling |
| 4.1.7 Simple imputation — constant (zero, custom value) | ❌ | Not a filling |
| 4.1.8 Simple imputation — forward fill / backward fill (time series) | ❌ | Not a filling |
| 4.1.9 Simple imputation — interpolation (linear, spline, polynomial) | ❌ | Not a filling |
| 4.1.10 Indicator variable — add missingness flag column | ✅ | `median_fill_with_indicator` |
| 4.1.11 KNN imputation | 🔲 | In registry (`knn_impute_fit_apply`) but not enumerated |
| 4.1.12 Iterative imputation (MICE) | 🔲 | In registry (`iterative_impute_fit_apply`) but not enumerated |
| 4.1.13 Matrix factorization imputation (SoftImpute, PCA imputation) | ❌ | Not implemented |
| 4.1.14 Deep learning imputation (autoencoders, GANs, transformers) | ❌ | Not implemented |
| 4.1.15 Multiple imputation (Rubin's rules, pooling) | ❌ | Not implemented |
| 4.1.16 Group-statistic imputation (group mean/median) | 🔲 | In registry (`group_statistic_impute_fit_apply`) |
| 4.1.17 MissForest (random forest imputation) | ❌ | Not implemented |
| 4.1.18 Hot-deck imputation | ❌ | Not implemented |

### 4.2 Outlier Handling

| Technique | Taedri | Notes |
|---|---|---|
| 4.2.1 Winsorization / clipping (percentile-based) | ✅ | `winsorize` in feature_taming slot |
| 4.2.2 Trimming (remove outlier rows) | ❌ | Not a filling |
| 4.2.3 Smooth outlier taper | ✅ | `smooth_outlier_taper` in feature_taming |
| 4.2.4 Rank transformation (rank-based, quantile) | ✅ | `rank_gauss`, `pack_quantile_gauss` in feature_taming |
| 4.2.5 Standardization (z-score, mean=0, std=1) | ✅ | `standardize` in feature_taming |
| 4.2.6 Robust scaling (median + IQR) | ❌ | Not a filling |
| 4.2.7 Min-max scaling (0-1 range) | ❌ | Not a filling |
| 4.2.8 Max-abs scaling | ❌ | Not a filling |
| 4.2.9 Power transforms (Box-Cox, Yeo-Johnson) | ✅ | `pack_yeojohnson_skewed` in feature_taming |
| 4.2.10 Quantile transformation (to uniform/normal) | ✅ | `pack_quantile_gauss` in feature_taming |
| 4.2.11 Log transform (log1p, signed log) | 🔶 | In target_transform slot, not feature_taming |
| 4.2.12 Square root transform | ❌ | Not a filling |
| 4.2.13 Binning / discretization | ✅ | `quantile_bin_partition` in feature_construction |
| 4.2.14 Binarization (threshold-based) | ❌ | Not a filling |
| 4.2.15 Normalization (L1, L2, max norm) | ❌ | Not a filling |
| 4.2.16 Unit vector normalization | ❌ | Not a filling |
| 4.2.17 Polynomial features | ✅ | `pack_polynomial_interactions_fdr` in feature_construction |
| 4.2.18 Spline features | ✅ | `pack_spline_top4` in feature_construction |

### 4.3 Categorical Encoding

| Technique | Taedri | Notes |
|---|---|---|
| 4.3.1 Ordinal encoding (label encoding) | ✅ | `ordinal` in categorical_encoding slot |
| 4.3.2 One-hot encoding | ✅ | `one_hot_small` in categorical_encoding slot |
| 4.3.3 Count encoding (frequency encoding) | ✅ | `count_encode` in categorical_encoding slot |
| 4.3.4 Target encoding (mean encoding, likelihood encoding) | ✅ | `pack_target_encode_oof` in feature_construction |
| 4.3.5 Leave-one-out target encoding | ❌ | Not a separate filling |
| 4.3.6 CatBoost encoding (ordered target encoding) | ❌ | Not a filling |
| 4.3.7 James-Stein encoding | ❌ | Not a filling |
| 4.3.8 Weight of Evidence (WoE) encoding | ❌ | Not a filling |
| 4.3.9 Helmert encoding | ❌ | Not a filling |
| 4.3.10 Backward difference encoding | ❌ | Not a filling |
| 4.3.11 Binary encoding (binary representation) | ❌ | Not a filling |
| 4.3.12 Hashing encoding (feature hashing) | ❌ | Not a filling |
| 4.3.13 Embedding encoding (entity embeddings, neural) | ❌ | Not a filling |
| 4.3.14 Rare category grouping | ❌ | Not a filling |
| 4.3.15 High-cardinality handling (>1000 categories) | 🔶 | No dedicated strategy; count_encode is the fallback |

### 4.4 Date/Time Feature Handling

| Technique | Taedri | Notes |
|---|---|---|
| 4.4.1 Date part extraction (year, month, day, hour, minute, second) | 🔶 | `calendar-features.json` profile; no dedicated slot |
| 4.4.2 Cyclical encoding (sin/cos for hour, day of week, month) | ❌ | Not a filling |
| 4.4.3 Time delta features (days since event, time to next) | ❌ | Not a filling |
| 4.4.4 Holiday / business day flags | ❌ | Not a filling |
| 4.4.5 Fiscal period features (quarter, fiscal year, week number) | ❌ | Not a filling |
| 4.4.6 Lag features (t-1, t-7, t-30) | ❌ | Not a filling |
| 4.4.7 Rolling window features (moving average, rolling std) | ❌ | Not a filling |
| 4.4.8 Expanding window features (cumulative stats) | ❌ | Not a filling |
| 4.4.9 Exponential weighted moving features | ❌ | Not a filling |
| 4.4.10 Seasonality decomposition (STL, Prophet components) | ❌ | Not a filling |

### 4.5 Text Preprocessing

| Technique | Taedri | Notes |
|---|---|---|
| 4.5.1 Lowercasing, punctuation removal, whitespace normalization | ❌ | `TF_TEXT` arm exists but unused |
| 4.5.2 Tokenization (word, character, subword, sentence) | ❌ | Not a filling |
| 4.5.3 Stop word removal | ❌ | Not a filling |
| 4.5.4 Stemming (Porter, Snowball, Lancaster) | ❌ | Not a filling |
| 4.5.5 Lemmatization (WordNet, spaCy) | ❌ | Not a filling |
| 4.5.6 N-gram generation (unigrams, bigrams, trigrams) | ❌ | Not a filling |
| 4.5.7 TF-IDF vectorization | ❌ | Not a filling |
| 4.5.8 Count vectorization (bag of words) | ❌ | Not a filling |
| 4.5.9 Word embeddings (Word2Vec, GloVe, FastText) | ❌ | Not a filling |
| 4.5.10 Contextual embeddings (BERT, RoBERTa, sentence transformers) | ❌ | Not a filling |
| 4.5.11 Topic modeling (LDA, NMF, BERTopic) | ❌ | Not a filling |
| 4.5.12 Named entity recognition | ❌ | Not a filling |
| 4.5.13 Sentiment analysis features | ❌ | Not a filling |
| 4.5.14 Text length, word count, punctuation ratio features | ❌ | Not a filling |

---

## 5. FEATURE ENGINEERING

### 5.1 Mathematical Transformations

| Technique | Taedri | Notes |
|---|---|---|
| 5.1.1 Polynomial features (degree 2, 3, interaction-only) | ✅ | `pack_polynomial_interactions_fdr` |
| 5.1.2 Ratio features (A/B, A/(A+B)) | ✅ | `ratio_quotients_fdr` |
| 5.1.3 Log, exp, sqrt, power transforms | 🔶 | In target_transform; not in feature_construction |
| 5.1.4 Trigonometric transforms (sin, cos) | ❌ | Not a filling |
| 5.1.5 Signed transforms (signed log, signed sqrt) | 🔶 | In target_transform |
| 5.1.6 Box-Cox / Yeo-Johnson per feature | ✅ | `pack_yeojohnson_skewed` in feature_taming |
| 5.1.7 Binning / discretization | ✅ | `quantile_bin_partition`, `pack_quantile_bins_ordinal_5` |
| 5.1.8 Quantile binning with ordinal encoding | ✅ | `pack_quantile_bins_ordinal_5` |
| 5.1.9 KBins discretizer | ✅ | `pack_kbins_discretize` |

### 5.2 Interaction Features

| Technique | Taedri | Notes |
|---|---|---|
| 5.2.1 Pairwise interactions (screened by FDR) | ✅ | `pairwise_interactions_fdr`, `pack_interactions_fdr` |
| 5.2.2 Three-way interactions | ❌ | Not a filling |
| 5.2.3 Polynomial interactions (degree > 2) | ✅ | `pack_polynomial_interactions_fdr` |
| 5.2.4 Division / ratio interactions | ✅ | `ratio_quotients_fdr` |
| 5.2.5 Subtraction / difference interactions | ❌ | Not a filling |
| 5.2.6 Group-by aggregate features (mean, std, count by category) | ❌ | Not a filling |
| 5.2.7 Cross-feature products (weighted combinations) | ❌ | Not a filling |

### 5.3 Clustering-Based Features

| Technique | Taedri | Notes |
|---|---|---|
| 5.3.1 K-means cluster assignment as feature | ✅ | `kmeans_cluster_features_k8` |
| 5.3.2 Cluster distance features (distance to each centroid) | ❌ | Not a filling |
| 5.3.3 Cluster target mean (out-of-fold) | ✅ | `cluster_target_mean_oof` |
| 5.3.4 DBSCAN cluster labels | ❌ | Not a filling |
| 5.3.5 Hierarchical clustering features | ❌ | Not a filling |
| 5.3.6 Gaussian mixture model cluster probabilities | ❌ | Not a filling |
| 5.3.7 Spectral clustering features | ❌ | Not a filling |

### 5.4 Decomposition Features

| Technique | Taedri | Notes |
|---|---|---|
| 5.4.1 PCA components | ✅ | `pack_pca_5`, `orthogonal_components` |
| 5.4.2 ICA components | ✅ | `pack_ica_5` |
| 5.4.3 Truncated SVD components | 🔲 | In deep fillings |
| 5.4.4 Factor analysis components | 🔲 | In deep fillings |
| 5.4.5 NMF components (non-negative matrix factorization) | ❌ | Not a filling |
| 5.4.6 Kernel PCA (RBF, polynomial, sigmoid) | ✅ | `pack_kernel_rbf_16`, `pack_kernel_nystroem_16` |
| 5.4.7 Feature agglomeration | ✅ | `pack_column_pools_5` |
| 5.4.8 LDA (linear discriminant analysis) features | ❌ | Not a filling |
| 5.4.9 t-SNE / UMAP (for visualization, not modeling) | ❌ | Not a filling |
| 5.4.10 Autoencoder features (deep learned representations) | ❌ | Not a filling |

### 5.5 Statistical Features

| Technique | Taedri | Notes |
|---|---|---|
| 5.5.1 Microfeature census (statistical summary features) | ✅ | `pack_microfeature_census` |
| 5.5.2 Rolling statistics (mean, std, min, max over window) | ❌ | Not a filling |
| 5.5.3 Expanding statistics (cumulative mean, cumulative std) | ❌ | Not a filling |
| 5.5.4 Rank features (percentile rank, rank normalization) | ❌ | Not a filling |
| 5.5.5 Count features (count of X in group, count of non-null) | ❌ | Not a filling |
| 5.5.6 Entropy features (Shannon entropy of distribution) | ❌ | Not a filling |
| 5.5.7 Distance features (distance to reference point, Mahalanobis) | ❌ | Not a filling |

### 5.6 Domain-Specific Features

| Technique | Taedri | Notes |
|---|---|---|
| 5.6.1 Financial ratios (P/E, debt/equity, current ratio) | ❌ | Not a filling |
| 5.6.2 Geospatial features (Haversine distance, geohash, tile) | ❌ | Not a filling |
| 5.6.3 Network/graph features (degree, centrality, PageRank) | ❌ | Not a filling |
| 5.6.4 Audio features (MFCC, spectrogram, chroma, zero-crossing) | ❌ | Not a filling |
| 5.6.5 Image features (HOG, SIFT, CNN embeddings, color histograms) | ❌ | Not a filling |
| 5.6.6 NLP features (readability scores, syntax tree depth, entity counts) | ❌ | Not a filling |

---

## 6. DIMENSIONALITY REDUCTION

| Step | Technique | Taedri | Notes |
|---|---|---|---|
| 6.1 Linear projection | PCA (explained variance ratio, fixed components) | 🔲 | In deep fillings; not in main SLOTS |
| 6.2 Linear projection | Truncated SVD (for sparse data) | 🔲 | In deep fillings |
| 6.3 Linear projection | Factor Analysis | 🔲 | In deep fillings |
| 6.4 Linear projection | ICA (Independent Component Analysis) | 🔲 | In deep fillings |
| 6.5 Linear projection | LDA (supervised dimensionality reduction) | ❌ | Not a filling |
| 6.6 Linear projection | PLS (Partial Least Squares, supervised) | ❌ | Not a filling |
| 6.7 Linear projection | CCA (Canonical Correlation Analysis) | ❌ | Not a filling |
| 6.8 Variance-based | Variance threshold (remove low-variance columns) | 🔲 | In deep fillings |
| 6.9 Correlation-based | Collinearity grouping + medoid selection | 🔲 | In deep fillings |
| 6.10 Correlation-based | Correlation threshold (remove one of each correlated pair) | ❌ | Not a filling |
| 6.11 Information-based | Mutual information feature selection | 🔲 | In deep fillings |
| 6.12 Information-based | Information gain ratio | ❌ | Not a filling |
| 6.13 Nonlinear | Kernel PCA (RBF, polynomial, sigmoid) | ✅ | In feature_construction slot |
| 6.14 Nonlinear | Nystroem approximation | ✅ | In feature_construction slot |
| 6.15 Nonlinear | t-SNE (for visualization) | ❌ | Not a filling |
| 6.16 Nonlinear | UMAP (Uniform Manifold Approximation) | ❌ | Not a filling |
| 6.17 Nonlinear | Isomap | ❌ | Not a filling |
| 6.18 Nonlinear | LLE (Locally Linear Embedding) | ❌ | Not a filling |
| 6.19 Nonlinear | Autoencoders (deep dimensionality reduction) | ❌ | Not a filling |
| 6.20 Nonlinear | Random projection (Johnson-Lindenstrauss) | ❌ | Not a filling |
| 6.21 Feature agglomeration | Hierarchical feature clustering + aggregation | ✅ | `pack_column_pools_5` |
| 6.22 Manifold learning | Spectral embedding, MDS | ❌ | Not a filling |
| 6.23 Sparse methods | Sparse PCA, sparse random projection | ❌ | Not a filling |
| 6.24 Incremental methods | Incremental PCA (for large datasets) | ❌ | Not a filling |

---

## 7. FEATURE SELECTION

### 7.1 Filter Methods (univariate, no model)

| Technique | Taedri | Notes |
|---|---|---|
| 7.1.1 Variance threshold | 🔲 | In deep fillings |
| 7.1.2 Pearson correlation with target | ✅ | `fold_local_pearson_top_k` in feature_selection slot |
| 7.1.3 Spearman correlation with target | ❌ | Not a filling |
| 7.1.4 Mutual information with target | 🔲 | In deep fillings |
| 7.1.5 ANOVA F-test | ❌ | Not a filling |
| 7.1.6 Chi-squared test | ❌ | Not a filling |
| 7.1.7 Information gain / gain ratio | ❌ | Not a filling |
| 7.1.8 Fisher score | ❌ | Not a filling |
| 7.1.9 Gini importance (from tree-based models) | ❌ | Not a filling |
| 7.1.10 Relief / ReliefF algorithm | ❌ | Not a filling |
| 7.1.11 mRMR (minimum redundancy maximum relevance) | ❌ | Not a filling |
| 7.1.12 CFS (correlation-based feature selection) | ❌ | Not a filling |
| 7.1.13 FCBF (fast correlation-based filter) | ❌ | Not a filling |

### 7.2 Wrapper Methods (uses a model)

| Technique | Taedri | Notes |
|---|---|---|
| 7.2.1 Forward selection (greedy add best feature) | ❌ | Not a filling |
| 7.2.2 Backward elimination (greedy remove worst feature) | ❌ | Not a filling |
| 7.2.3 Bidirectional / stepwise selection | ❌ | Not a filling |
| 7.2.4 Exhaustive search (all subsets) | ❌ | Not a filling |
| 7.2.5 Recursive feature elimination (RFE) | ❌ | Not a filling |
| 7.2.6 RFE with cross-validation (RFECV) | ❌ | Not a filling |
| 7.2.7 Genetic algorithm feature selection | ❌ | Not a filling |
| 7.2.8 Simulated annealing feature selection | ❌ | Not a filling |
| 7.2.9 Boruta (shadow feature comparison) | ❌ | Not a filling |
| 7.2.10 Sequential feature selector (forward/backward, sklearn) | ❌ | Not a filling |

### 7.3 Embedded Methods (built into model training)

| Technique | Taedri | Notes |
|---|---|---|
| 7.3.1 Lasso (L1 regularization) | ✅ | Ridge in estimator slot; Lasso not a separate filling |
| 7.3.2 Elastic Net (L1 + L2) | ❌ | Not a filling |
| 7.3.3 Tree-based feature importance (Random Forest, XGBoost, LightGBM) | ✅ | Implicit in tree estimators |
| 7.3.4 Permutation importance (model-agnostic) | ❌ | Not a filling |
| 7.3.5 SHAP feature importance | ❌ | Not a filling |
| 7.3.6 LIME feature importance | ❌ | Not a filling |
| 7.3.7 Regularized trees (regularized random forest) | ❌ | Not a filling |
| 7.3.8 Group lasso (feature group selection) | ❌ | Not a filling |
| 7.3.9 Sparse group lasso | ❌ | Not a filling |

### 7.4 Hybrid & Advanced Methods

| Technique | Taedri | Notes |
|---|---|---|
| 7.4.1 Stability selection (combine selection across bootstrap samples) | ❌ | Not a filling |
| 7.4.2 Ensemble feature selection (vote across multiple selectors) | ❌ | Not a filling |
| 7.4.3 Feature selection with cross-validation | ✅ | `fold_local_pearson_top_k` uses inner folds |
| 7.4.4 Multi-objective feature selection (accuracy vs. feature count) | ❌ | Not a filling |
| 7.4.5 Causal feature selection (PC algorithm, FCI, LiNGAM) | ❌ | Not a filling |
| 7.4.6 Markov blanket feature selection | ❌ | Not a filling |
| 7.4.7 Deep feature selection (neural network with sparse input layer) | ❌ | Not a filling |
| 7.4.8 Autoencoder feature selection (concrete autoencoder) | ❌ | Not a filling |

---

## 8. TARGET ENGINEERING

| Step | Technique | Taedri | Notes |
|---|---|---|---|
| 8.1 Target transformation | Log transform (log1p) | ✅ | `log1p` in target_transform slot |
| 8.2 Target transformation | Signed log transform | ✅ | `signed_log1p` in target_transform slot |
| 8.3 Target transformation | Box-Cox transform | ❌ | Not a filling |
| 8.4 Target transformation | Yeo-Johnson transform | ❌ | Not a filling |
| 8.5 Target transformation | Quantile transform (to normal/uniform) | 🔲 | In deep fillings |
| 8.6 Target transformation | Rank transform (rank-based, no distribution assumption) | ✅ | `target_rank_gauss` in target_transform slot |
| 8.7 Target transformation | Square root transform | ❌ | Not a filling |
| 8.8 Target transformation | Power transform (generalized) | ❌ | Not a filling |
| 8.9 Target balancing | Class weighting (inverse frequency, balanced) | ✅ | `inverse_frequency_class_weights` in row_weighting |
| 8.10 Target balancing | SMOTE (Synthetic Minority Oversampling) | 🔲 | In deep fillings |
| 8.11 Target balancing | ADASYN (Adaptive Synthetic Sampling) | ❌ | Not a filling |
| 8.12 Target balancing | Borderline SMOTE | ❌ | Not a filling |
| 8.13 Target balancing | SVMSMOTE | ❌ | Not a filling |
| 8.14 Target balancing | Random oversampling | ❌ | Not a filling |
| 8.15 Target balancing | Random undersampling | ❌ | Not a filling |
| 8.16 Target balancing | Tomek links (cleaning undersampling) | ❌ | Not a filling |
| 8.17 Target balancing | Edited Nearest Neighbors (ENN) | ❌ | Not a filling |
| 8.18 Target balancing | NearMiss undersampling | ❌ | Not a filling |
| 8.19 Target balancing | Cluster centroids undersampling | ❌ | Not a filling |
| 8.20 Target balancing | Combination sampling (SMOTE + Tomek, SMOTE + ENN) | ❌ | Not a filling |
| 8.21 Target balancing | Cost-sensitive learning (weighted loss functions) | 🔶 | Implicit in class weights |
| 8.22 Target balancing | Threshold moving (adjust decision threshold) | ❌ | Not a filling |
| 8.23 Target encoding | Multi-output target handling (multi-label, multi-target) | 🔶 | `multi_output_long_format` family exists |
| 8.24 Target encoding | Ordinal regression target encoding | ❌ | Not a filling |
| 8.25 Target encoding | Survival analysis target (time-to-event, censoring) | ❌ | Not a filling |
| 8.26 Target encoding | Quantile regression target (predict percentiles) | ❌ | Not a filling |

---

## 9. DATA SPLITTING & VALIDATION

| Step | Technique | Taedri | Notes |
|---|---|---|---|
| 9.1 Holdout split | Random train/test split (fixed ratio) | ✅ | `frozen_grader.py` |
| 9.2 Holdout split | Stratified split (preserve class distribution) | ✅ | `frozen_grader.py` |
| 9.3 Holdout split | Time-based split (chronological, out-of-time) | ✅ | `frozen_grader.py` chronological purged split |
| 9.4 Holdout split | Group-based split (same group in one split only) | ✅ | `frozen_grader.py` |
| 9.5 Cross-validation | K-fold (standard, no stratification) | ✅ | Engine uses k-fold |
| 9.6 Cross-validation | Stratified K-fold | ✅ | Engine uses stratified for classification |
| 9.7 Cross-validation | Group K-fold | ❌ | Not implemented |
| 9.8 Cross-validation | Time series split (expanding window) | ✅ | `temporal_oof_coverage_contract.py` |
| 9.9 Cross-validation | Purged time series split (gap between train/test) | ✅ | `frozen_grader.py` |
| 9.10 Cross-validation | Leave-one-out (LOO) | ❌ | Not implemented |
| 9.11 Cross-validation | Leave-P-out | ❌ | Not implemented |
| 9.12 Cross-validation | Leave-one-group-out | ❌ | Not implemented |
| 9.13 Cross-validation | Repeated K-fold | ❌ | Not implemented |
| 9.14 Cross-validation | Nested cross-validation (inner for tuning, outer for eval) | 🔶 | Inner folds for feature selection; no full nested CV |
| 9.15 Cross-validation | Monte Carlo cross-validation (random subsampling) | ❌ | Not implemented |
| 9.16 Cross-validation | Stratified shuffle split | ❌ | Not implemented |
| 9.17 Validation set | Fixed validation set (separate from test) | ✅ | Feedback half vs private half |
| 9.18 Bootstrapping | .632 bootstrap, .632+ bootstrap | ❌ | Not implemented |
| 9.19 Bootstrapping | Out-of-bag (OOB) evaluation | ✅ | Tree estimators provide OOB |
| 9.20 Bootstrapping | Block bootstrap (for time series) | ❌ | Not implemented |

---

## 10. MODEL SELECTION

### 10.1 Linear Models

| Technique | Taedri | Notes |
|---|---|---|
| 10.1.1 Linear regression (OLS) | ❌ | Not a filling |
| 10.1.2 Ridge regression (L2) | ✅ | `ridge` in estimator slot |
| 10.1.3 Lasso regression (L1) | ❌ | Not a filling |
| 10.1.4 Elastic Net (L1 + L2) | ❌ | Not a filling |
| 10.1.5 Huber regression (robust to outliers) | ✅ | `huber` in estimator slot |
| 10.1.6 Quantile regression | ❌ | Not a filling |
| 10.1.7 Poisson regression | ✅ | `hgb_poisson` in estimator slot |
| 10.1.8 Gamma regression | ❌ | Not a filling |
| 10.1.9 Tweedie regression | ❌ | Not a filling |
| 10.1.10 Logistic regression (binary) | ✅ | `logreg` in estimator slot |
| 10.1.11 Multinomial logistic regression | ✅ | `logreg` handles multiclass |
| 10.1.12 Ordinal logistic regression | ❌ | Not a filling |
| 10.1.13 SGD classifier/regressor (stochastic gradient descent) | ❌ | Not a filling |
| 10.1.14 Passive-aggressive classifier/regressor | ❌ | Not a filling |
| 10.1.15 Perceptron | ❌ | Not a filling |
| 10.1.16 LARS (least angle regression) | ❌ | Not a filling |
| 10.1.17 Lasso LARS | ❌ | Not a filling |
| 10.1.18 Bayesian regression (Bayesian Ridge, ARD) | ❌ | Not a filling |
| 10.1.19 RANSAC regression (robust to outliers) | ❌ | Not a filling |
| 10.1.20 Theil-Sen regression (robust non-parametric) | ❌ | Not a filling |

### 10.2 Tree-Based Models

| Technique | Taedri | Notes |
|---|---|---|
| 10.2.1 Decision tree (regression) | ❌ | Not a separate filling |
| 10.2.2 Decision tree (classification) | ❌ | Not a separate filling |
| 10.2.3 Random forest (regression) | ❌ | Not a separate filling (Extra Trees instead) |
| 10.2.4 Random forest (classification) | ❌ | Not a separate filling |
| 10.2.5 Extra Trees (regression) | ✅ | `extra_trees_reg` in estimator slot |
| 10.2.6 Extra Trees (classification) | ✅ | `extra_trees_clf` in estimator slot |
| 10.2.7 Histogram Gradient Boosting (regression) | ✅ | `hgb` variants in estimator slot |
| 10.2.8 Histogram Gradient Boosting (classification) | ✅ | `hgb_clf` variants in estimator slot |
| 10.2.9 LightGBM (regression) | ✅ | `lgbm_reg` in estimator slot |
| 10.2.10 LightGBM (classification) | ✅ | `lgbm_clf` in estimator slot |
| 10.2.11 XGBoost (regression) | ✅ | `xgb_reg` in estimator slot |
| 10.2.12 XGBoost (classification) | ✅ | `xgb_clf` in estimator slot |
| 10.2.13 CatBoost (regression) | 🔲 | In deep fillings |
| 10.2.14 CatBoost (classification) | 🔲 | In deep fillings |
| 10.2.15 Gradient Boosting (sklearn, regression) | ❌ | Not a filling |
| 10.2.16 Gradient Boosting (sklearn, classification) | ❌ | Not a filling |
| 10.2.17 AdaBoost (regression) | ❌ | Not a filling |
| 10.2.18 AdaBoost (classification) | ❌ | Not a filling |
| 10.2.19 Gradient boosting with monotonic constraints | ❌ | Not a filling |
| 10.2.20 Oblique / rotation trees | ❌ | Not a filling |

### 10.3 Nearest Neighbors

| Technique | Taedri | Notes |
|---|---|---|
| 10.3.1 KNN regressor | ✅ | `knn_reg` in estimator slot |
| 10.3.2 KNN classifier | ✅ | `knn_clf` in estimator slot |
| 10.3.3 Radius neighbors | ❌ | Not a filling |
| 10.3.4 Nearest centroid classifier | ❌ | Not a filling |
| 10.3.5 KNN with distance weighting | ❌ | Not a filling |

### 10.4 Support Vector Machines

| Technique | Taedri | Notes |
|---|---|---|
| 10.4.1 SVR (support vector regression) | ✅ | `w14_support_vector` in derived estimators |
| 10.4.2 SVC (support vector classification) | ✅ | `w14_support_vector` in derived estimators |
| 10.4.3 Linear SVC / SVR | ❌ | Not a separate filling |
| 10.4.4 NuSVC / NuSVR | ❌ | Not a filling |
| 10.4.5 One-class SVM (anomaly detection) | ❌ | Not a filling |

### 10.5 Neural Networks & Deep Learning

| Technique | Taedri | Notes |
|---|---|---|
| 10.5.1 MLP regressor (multi-layer perceptron) | 🔲 | In deep fillings |
| 10.5.2 MLP classifier | 🔲 | In deep fillings |
| 10.5.3 Convolutional neural networks (CNN) | ❌ | Not a filling |
| 10.5.4 Recurrent neural networks (RNN, LSTM, GRU) | ❌ | Not a filling |
| 10.5.5 Transformer models (tabular transformers, FT-Transformer) | ❌ | Not a filling |
| 10.5.6 Autoencoders (for feature learning) | ❌ | Not a filling |
| 10.5.7 Wide & Deep networks | ❌ | Not a filling |
| 10.5.8 TabNet (attentive tabular learning) | ❌ | Not a filling |
| 10.5.9 NODE (neural oblivious decision ensembles) | ❌ | Not a filling |
| 10.5.10 DeepFM, xDeepFM (factorization machines + deep) | ❌ | Not a filling |
| 10.5.11 Graph neural networks (for tabular data) | ❌ | Not a filling |

### 10.6 Probabilistic & Bayesian Models

| Technique | Taedri | Notes |
|---|---|---|
| 10.6.1 Naive Bayes (Gaussian, Multinomial, Bernoulli, Complement) | ❌ | Not a filling |
| 10.6.2 Gaussian Process regression/classification | ❌ | Not a filling |
| 10.6.3 Bayesian neural networks | ❌ | Not a filling |
| 10.6.4 Hidden Markov Models | ❌ | Not a filling |
| 10.6.5 Bayesian structural time series | ❌ | Not a filling |

### 10.7 Other Model Families

| Technique | Taedri | Notes |
|---|---|---|
| 10.7.1 Baseline constant predictor (mean, median, majority class) | ✅ | `w14_baseline_constant` in derived estimators |
| 10.7.2 Dummy classifier/regressor (stratified, uniform, prior) | ❌ | Not a filling |
| 10.7.3 Isotonic regression | ❌ | Not a filling |
| 10.7.4 Spline regression (MARS, Earth) | ❌ | Not a filling |
| 10.7.5 Generalized additive models (GAMs) | ❌ | Not a filling |
| 10.7.6 Quantile regression forests | ❌ | Not a filling |
| 10.7.7 Conformal prediction models | 🔲 | MAPIE in deep fillings |
| 10.7.8 Survival models (Cox PH, Random Survival Forest, DeepSurv) | ❌ | Not a filling |
| 10.7.9 Rule-based models (Decision List, RuleFit, Skope-Rules) | ❌ | Not a filling |
| 10.7.10 Fuzzy models / neuro-fuzzy systems | ❌ | Not a filling |

---

## 11. MODEL TRAINING & FITTING

| Step | Technique | Taedri | Notes |
|---|---|---|---|
| 11.1 Training strategy | Full batch training | ✅ | Default |
| 11.2 Training strategy | Mini-batch / stochastic training | ❌ | Not implemented |
| 11.3 Training strategy | Online / incremental learning | ❌ | Not implemented |
| 11.4 Training strategy | Transfer learning (pretrained → fine-tune) | ❌ | Not implemented |
| 11.5 Training strategy | Multi-task learning | ❌ | Not implemented |
| 11.6 Training strategy | Curriculum learning | ❌ | Not implemented |
| 11.7 Training strategy | Self-training / semi-supervised | ❌ | Not implemented |
| 11.8 Training strategy | Active learning | ❌ | Not implemented |
| 11.9 Training strategy | Few-shot / zero-shot learning | ❌ | Not implemented |
| 11.10 Early stopping | Validation-based early stopping | ✅ | LightGBM, XGBoost, HGB use early stopping |
| 11.11 Early stopping | No-improvement-rounds early stopping | ✅ | `early_stopping_rounds` parameter |
| 11.12 Early stopping | Patience-based early stopping | ❌ | Not a separate mechanism |
| 11.13 Regularization | L1 (lasso) | 🔶 | Implicit in some estimators |
| 11.14 Regularization | L2 (ridge, weight decay) | ✅ | Ridge, logreg use L2 |
| 11.15 Regularization | Elastic Net | ❌ | Not a filling |
| 11.16 Regularization | Dropout (neural networks) | ❌ | Not a filling |
| 11.17 Regularization | Batch normalization | ❌ | Not a filling |
| 11.18 Regularization | Layer normalization | ❌ | Not a filling |
| 11.19 Regularization | Data augmentation | ❌ | Not a filling |
| 11.20 Regularization | Label smoothing | ❌ | Not a filling |
| 11.21 Regularization | Mixup / CutMix | ❌ | Not a filling |
| 11.22 Regularization | Weight tying / parameter sharing | ❌ | Not a filling |
| 11.23 Optimization | Gradient descent (SGD, momentum, Nesterov) | ❌ | Not a filling |
| 11.24 Optimization | Adam, AdamW, RMSprop, Adagrad, Adadelta | ❌ | Not a filling |
| 11.25 Optimization | Learning rate scheduling (step, cosine, exponential, cyclic) | ❌ | Not a filling |
| 11.26 Optimization | Warmup (linear, cosine) | ❌ | Not a filling |
| 11.27 Optimization | Gradient clipping | ❌ | Not a filling |
| 11.28 Optimization | Second-order methods (L-BFGS, Newton) | ❌ | Not a filling |
| 11.29 Loss functions | MSE, MAE, Huber, quantile (regression) | ✅ | HGB supports multiple losses |
| 11.30 Loss functions | Cross-entropy, focal loss (classification) | ✅ | Default in classifiers |
| 11.31 Loss functions | Hinge loss, squared hinge | ❌ | Not a filling |
| 11.32 Loss functions | Custom / composite loss functions | ❌ | Not a filling |

---

## 12. HYPERPARAMETER TUNING

| Step | Technique | Taedri | Notes |
|---|---|---|---|
| 12.1 Grid search | Full grid search (exhaustive) | ✅ | Engine enumerates declared parameter domains |
| 12.2 Grid search | Randomized grid search | ❌ | Not implemented |
| 12.3 Grid search | Halving grid search (successive halving) | ❌ | Not implemented |
| 12.4 Bayesian optimization | Gaussian Process-based (GPyOpt, Spearmint) | ❌ | Not implemented |
| 12.5 Bayesian optimization | Tree-structured Parzen Estimator (TPE, Hyperopt) | ❌ | Not implemented |
| 12.6 Bayesian optimization | SMAC (sequential model-based optimization) | ❌ | Not implemented |
| 12.7 Bayesian optimization | BOHB (Bayesian Optimization + Hyperband) | ❌ | Not implemented |
| 12.8 Bayesian optimization | Optuna (TPE + pruning) | ❌ | Not implemented |
| 12.9 Evolutionary | Genetic algorithms (TPOT, GAMA) | ❌ | Not implemented |
| 12.10 Evolutionary | Evolutionary strategies (CMA-ES) | ❌ | Not implemented |
| 12.11 Evolutionary | Particle swarm optimization | ❌ | Not implemented |
| 12.12 Evolutionary | Differential evolution | ❌ | Not implemented |
| 12.13 Bandit-based | Hyperband (successive halving with brackets) | ❌ | Not implemented |
| 12.14 Bandit-based | ASHA (asynchronous successive halving) | ❌ | Not implemented |
| 12.15 Bandit-based | Median stopping rule | ❌ | Not implemented |
| 12.16 Bandit-based | PBT (population-based training) | ❌ | Not implemented |
| 12.17 Gradient-based | Gradient-based hyperparameter optimization | ❌ | Not implemented |
| 12.18 Multi-fidelity | Multi-fidelity optimization (low-res → high-res) | ❌ | Not implemented |
| 12.19 Multi-objective | Pareto optimization (accuracy vs. speed vs. memory) | ❌ | Not implemented |
| 12.20 Multi-objective | NSGA-II, MOEA/D | ❌ | Not implemented |
| 12.21 Meta-learning | Warm-start from previous tasks | 🔶 | `multi_anchor_sprouts` (currently 0) |
| 12.22 Meta-learning | Learning curve prediction | ❌ | Not implemented |
| 12.23 Meta-learning | Portfolio-based selection | ❌ | Not implemented |
| 12.24 Pruning | Early stopping of unpromising trials | ❌ | Not implemented |
| 12.25 Pruning | Learning curve extrapolation | ❌ | Not implemented |
| 12.26 Pruning | Median pruning (Optuna) | ❌ | Not implemented |

---

## 13. AUTOML

| Step | Technique | Taedri | Notes |
|---|---|---|---|
| 13.1 Full AutoML | FLAML (fast and lightweight AutoML) | 🔲 | In deep fillings |
| 13.2 Full AutoML | AutoGluon (multi-layer stacking) | ❌ | Not a filling |
| 13.3 Full AutoML | H2O AutoML | ❌ | Not a filling |
| 13.4 Full AutoML | TPOT (genetic programming pipeline optimization) | ❌ | Not a filling |
| 13.5 Full AutoML | Auto-sklearn (Bayesian optimization + meta-learning) | ❌ | Not a filling |
| 13.6 Full AutoML | MLJar AutoML | ❌ | Not a filling |
| 13.7 Full AutoML | PyCaret (low-code AutoML) | ❌ | Not a filling |
| 13.8 Full AutoML | Ludwig (declarative deep learning) | ❌ | Not a filling |
| 13.9 Neural architecture search | ENAS (efficient NAS) | ❌ | Not a filling |
| 13.10 Neural architecture search | DARTS (differentiable architecture search) | ❌ | Not a filling |
| 13.11 Neural architecture search | Regularized evolution | ❌ | Not a filling |
| 13.12 Feature engineering automation | Featuretools (deep feature synthesis) | ❌ | Not a filling |
| 13.13 Feature engineering automation | AutoFeat (automated feature engineering) | ❌ | Not a filling |
| 13.14 Pipeline optimization | Combined preprocessing + model search | ✅ | Taedri's core function |
| 13.15 Pipeline optimization | Multi-branch pipeline search | ❌ | Not implemented |
| 13.16 Pipeline optimization | Dynamic pipeline construction | ❌ | Not implemented |

---

## 14. ENSEMBLE METHODS

### 14.1 Basic Ensembling

| Technique | Taedri | Notes |
|---|---|---|
| 14.1.1 Simple averaging (equal weights) | ✅ | `greedy_simplex_blend` in ensemble slot |
| 14.1.2 Weighted averaging (performance-based weights) | ✅ | `greedy_ensemble_selection` |
| 14.1.3 Median ensemble | 🔲 | In sub_graph_ensemble.py |
| 14.1.4 Trimmed mean (remove extremes) | ❌ | Not a filling |
| 14.1.5 Rank averaging | ❌ | Not a filling |
| 14.1.6 Geometric mean | ❌ | Not a filling |
| 14.1.7 Harmonic mean | ❌ | Not a filling |

### 14.2 Bagging (Bootstrap Aggregating)

| Technique | Taedri | Notes |
|---|---|---|
| 14.2.1 Standard bagging (same model, bootstrap samples) | 🔲 | In deep fillings |
| 14.2.2 Pasting (subsampling without replacement) | ❌ | Not a filling |
| 14.2.3 Random subspaces (feature bagging) | ❌ | Not a filling |
| 14.2.4 Random patches (sample + feature bagging) | ❌ | Not a filling |
| 14.2.5 Balanced bagging (for imbalanced data) | ❌ | Not a filling |

### 14.3 Boosting

| Technique | Taedri | Notes |
|---|---|---|
| 14.3.1 Gradient boosting | ✅ | HGB, LightGBM, XGBoost |
| 14.3.2 AdaBoost | ❌ | Not a filling |
| 14.3.3 LogitBoost | ❌ | Not a filling |
| 14.3.4 LPBoost | ❌ | Not a filling |
| 14.3.5 CatBoost (ordered boosting) | 🔲 | In deep fillings |
| 14.3.6 NGBoost (natural gradient boosting, probabilistic) | ❌ | Not a filling |
| 14.3.7 ThunderBoost (GPU-accelerated) | ❌ | Not a filling |

### 14.4 Stacking (Stacked Generalization)

| Technique | Taedri | Notes |
|---|---|---|
| 14.4.1 Standard stacking (meta-model on base predictions) | 🔲 | In deep fillings |
| 14.4.2 Multi-layer stacking (stack of stacks) | ❌ | Not a filling |
| 14.4.3 Feature-weighted stacking (original features + predictions) | ❌ | Not a filling |
| 14.4.4 Cross-validated stacking (out-of-fold predictions for meta-model) | 🔲 | In deep fillings |
| 14.4.5 Bayesian model averaging (BMA) | ❌ | Not a filling |
| 14.4.6 Stacking with diverse base models | 🔲 | In deep fillings |

### 14.5 Voting

| Technique | Taedri | Notes |
|---|---|---|
| 14.5.1 Hard voting (majority vote) | 🔲 | In deep fillings |
| 14.5.2 Soft voting (average probabilities) | 🔲 | In deep fillings |
| 14.5.3 Weighted voting | ❌ | Not a filling |

### 14.6 Blending

| Technique | Taedri | Notes |
|---|---|---|
| 14.6.1 Holdout blending (train base on train, meta on holdout) | ❌ | Not a filling |
| 14.6.2 Cross-validated blending | ✅ | `greedy_simplex_blend` |
| 14.6.3 Stacked blending | ❌ | Not a filling |

### 14.7 Advanced Ensembling

| Technique | Taedri | Notes |
|---|---|---|
| 14.7.1 Greedy ensemble selection (Caruana et al.) | ✅ | `greedy_ensemble_selection` |
| 14.7.2 Stability-weighted averaging | 🔲 | In sub_graph_ensemble.py |
| 14.7.3 Ensemble pruning (remove redundant members) | ❌ | Not a filling |
| 14.7.4 Dynamic ensemble selection (choose members per sample) | ❌ | Not a filling |
| 14.7.5 Dynamic classifier selection (DCS) | ❌ | Not a filling |
| 14.7.6 Dynamic ensemble selection (DES, KNORA, META-DES) | ❌ | Not a filling |
| 14.7.7 Heterogeneous ensembles (different model families) | ✅ | Engine can select diverse estimators |
| 14.7.8 Homogeneous ensembles (same model, different params) | ✅ | Engine can vary parameters |
| 14.7.9 Snapshot ensembles (cyclic LR, save snapshots) | ❌ | Not a filling |
| 14.7.10 Fast geometric ensembling (FGE) | ❌ | Not a filling |
| 14.7.11 Sub-graph meta-ensemble (ensemble of complete graphs) | 🔲 | In sub_graph_ensemble.py |
| 14.7.12 Cascade / waterfall ensemble (sequential refinement) | ❌ | Not a filling |

---

## 15. POST-PROCESSING & CALIBRATION

| Step | Technique | Taedri | Notes |
|---|---|---|---|
| 15.1 Probability calibration | Platt scaling (sigmoid) | ❌ | Not a filling |
| 15.2 Probability calibration | Isotonic regression | ✅ | `monotone_calibration` in calibration slot |
| 15.3 Probability calibration | Beta calibration | ❌ | Not a filling |
| 15.4 Probability calibration | Temperature scaling (for neural networks) | ❌ | Not a filling |
| 15.5 Probability calibration | Venn-Abers predictors | ❌ | Not a filling |
| 15.6 Probability calibration | Histogram binning | ❌ | Not a filling |
| 15.7 Probability calibration | Bayesian binning into quantiles | ❌ | Not a filling |
| 15.8 Conformal prediction | Standard conformal prediction | 🔲 | MAPIE in deep fillings |
| 15.9 Conformal prediction | Split conformal prediction | 🔲 | MAPIE in deep fillings |
| 15.10 Conformal prediction | Cross-conformal prediction | ❌ | Not a filling |
| 15.11 Conformal prediction | Adaptive conformal prediction | ❌ | Not a filling |
| 15.12 Conformal prediction | Conformalized quantile regression | ❌ | Not a filling |
| 15.13 Prediction intervals | Bootstrap prediction intervals | ❌ | Not a filling |
| 15.14 Prediction intervals | Quantile regression intervals | ❌ | Not a filling |
| 15.15 Prediction intervals | Gaussian process intervals | ❌ | Not a filling |
| 15.16 Prediction clipping | Clip to valid range (non-negative, [0,1]) | 🔲 | In deep fillings |
| 15.17 Prediction clipping | Clip to training target range | 🔲 | In deep fillings |
| 15.18 Prediction rounding | Round to integers (for count targets) | ✅ | `route: round regression predictions to integer` |
| 15.19 Prediction transformation | Inverse target transform (log → exp, etc.) | ✅ | Engine inverts target_transform |
| 15.20 Threshold optimization | Find optimal decision threshold (classification) | ❌ | Not a filling |
| 15.21 Threshold optimization | F1-maximizing threshold | ❌ | Not a filling |
| 15.22 Threshold optimization | Youden's J statistic threshold | ❌ | Not a filling |
| 15.23 Threshold optimization | Cost-sensitive threshold | ❌ | Not a filling |
| 15.24 Threshold optimization | ROC-based threshold selection | ❌ | Not a filling |

---

## 16. EVALUATION & METRICS

### 16.1 Regression Metrics

| Metric | Taedri | Notes |
|---|---|---|
| 16.1.1 MSE (mean squared error) | ✅ | Via shared metric registry |
| 16.1.2 RMSE (root mean squared error) | ✅ | Primary regression metric |
| 16.1.3 MAE (mean absolute error) | ✅ | Via shared metric registry |
| 16.1.4 MedAE (median absolute error) | ✅ | Engine-local fallback |
| 16.1.5 MAPE (mean absolute percentage error) | ✅ | Via shared metric registry |
| 16.1.6 SMAPE (symmetric MAPE) | ✅ | Via shared metric registry |
| 16.1.7 RMSLE (root mean squared log error) | ✅ | Via shared metric registry |
| 16.1.8 MSLE (mean squared log error) | ✅ | Engine-local fallback |
| 16.1.9 R² (coefficient of determination) | ❌ | Not a metric |
| 16.1.10 Adjusted R² | ❌ | Not a metric |
| 16.1.11 Explained variance | ❌ | Not a metric |
| 16.1.12 Max error | ❌ | Not a metric |
| 16.1.13 Mean squared logarithmic error | ✅ | MSLE |
| 16.1.14 Mean Poisson deviance | ❌ | Not a metric |
| 16.1.15 Mean Gamma deviance | ❌ | Not a metric |
| 16.1.16 Mean Tweedie deviance | ❌ | Not a metric |
| 16.1.17 Pinball loss (quantile regression) | ❌ | Not a metric |
| 16.1.18 D² score (explained deviance) | ❌ | Not a metric |
| 16.1.19 Pearson correlation | ✅ | `pearson_correlation` in frozen_grader |
| 16.1.20 Spearman correlation | ❌ | Not a metric |
| 16.1.21 Kendall's tau | ❌ | Not a metric |

### 16.2 Classification Metrics

| Metric | Taedri | Notes |
|---|---|---|
| 16.2.1 Accuracy | ✅ | Via shared metric registry |
| 16.2.2 Balanced accuracy | ✅ | Via shared metric registry |
| 16.2.3 F1 score (binary, micro, macro, weighted) | ✅ | Via shared metric registry |
| 16.2.4 Precision | ❌ | Not a separate metric |
| 16.2.5 Recall (sensitivity) | ❌ | Not a separate metric |
| 16.2.6 Specificity | ❌ | Not a metric |
| 16.2.7 ROC AUC (area under ROC curve) | ✅ | Via shared metric registry |
| 16.2.8 PR AUC (area under precision-recall curve) | ✅ | `average_precision` |
| 16.2.9 Log loss (cross-entropy) | ✅ | Via shared metric registry |
| 16.2.10 Brier score | ✅ | Via shared metric registry |
| 16.2.11 Matthews correlation coefficient (MCC) | ❌ | Not a metric |
| 16.2.12 Cohen's kappa | ❌ | Not a metric |
| 16.2.13 Quadratic weighted kappa | ✅ | Via shared metric registry |
| 16.2.14 Hamming loss (multi-label) | ❌ | Not a metric |
| 16.2.15 Jaccard score (multi-label) | ❌ | Not a metric |
| 16.2.16 Top-k accuracy | ❌ | Not a metric |
| 16.2.17 MAP\@K (mean average precision at K) | ✅ | `map_at_k` for ranked labels |
| 16.2.18 NDCG (normalized discounted cumulative gain) | ❌ | Not a metric |
| 16.2.19 Gini coefficient (2*AUC - 1) | ❌ | Not a metric |
| 16.2.20 Kolmogorov-Smirnov statistic | ❌ | Not a metric |

### 16.3 Evaluation Techniques

| Technique | Taedri | Notes |
|---|---|---|
| 16.3.1 Holdout evaluation (single train/test split) | ✅ | Primary evaluation |
| 16.3.2 Cross-validation evaluation (k-fold average) | ✅ | Inner folds for selection |
| 16.3.3 Stratified evaluation | ✅ | Stratified splits |
| 16.3.4 Group-aware evaluation | ✅ | Group-based splits |
| 16.3.5 Time-aware evaluation (backtesting, walk-forward) | ✅ | Chronological purged splits |
| 16.3.6 Bootstrap evaluation (confidence intervals) | ❌ | Not implemented |
| 16.3.7 Permutation test (statistical significance) | ❌ | Not implemented |
| 16.3.8 McNemar's test (classifier comparison) | ❌ | Not implemented |
| 16.3.9 Dietterich's 5x2cv test | ❌ | Not implemented |
| 16.3.10 Bayesian signed-rank test | ❌ | Not implemented |
| 16.3.11 Confusion matrix | ❌ | Not a metric |
| 16.3.12 Classification report (per-class metrics) | ❌ | Not a metric |
| 16.3.13 ROC curve, PR curve | ❌ | Not a metric |
| 16.3.14 Calibration curve (reliability diagram) | ❌ | Not a metric |
| 16.3.15 Lift curve, gain chart | ❌ | Not a metric |
| 16.3.16 Learning curve (performance vs. training size) | ❌ | Not a metric |
| 16.3.17 Validation curve (performance vs. hyperparameter) | ❌ | Not a metric |
| 16.3.18 Residual analysis (residuals vs. fitted, Q-Q plot) | ❌ | Not a metric |
| 16.3.19 Error analysis (worst predictions, error distribution) | ❌ | Not a metric |
| 16.3.20 Slice-based evaluation (fairness across subgroups) | ❌ | Not a metric |

---

## 17. STABILITY & ROBUSTNESS

| Step | Technique | Taedri | Notes |
|---|---|---|---|
| 17.1 Stability analysis | Feature selection stability (Jaccard, Kuncheva index) | ❌ | Not implemented |
| 17.2 Stability analysis | Prediction stability across seeds | 🔶 | `validation_seed` separation exists |
| 17.3 Stability analysis | Model parameter stability | ❌ | Not implemented |
| 17.4 Stability analysis | Cross-validation variance analysis | ✅ | Fold scores recorded |
| 17.5 Robustness testing | Adversarial examples (evasion attacks) | ❌ | Not implemented |
| 17.6 Robustness testing | Noise injection (feature perturbation) | ❌ | Not implemented |
| 17.7 Robustness testing | Missing value robustness | ❌ | Not implemented |
| 17.8 Robustness testing | Distribution shift robustness (covariate shift) | ❌ | Not implemented |
| 17.9 Robustness testing | Label noise robustness | ❌ | Not implemented |
| 17.10 Robustness testing | Out-of-distribution detection | ❌ | Not implemented |
| 17.11 Sensitivity analysis | One-at-a-time sensitivity (OAT) | ❌ | Not implemented |
| 17.12 Sensitivity analysis | Morris method (elementary effects) | ❌ | Not implemented |
| 17.13 Sensitivity analysis | Sobol indices (variance-based) | ❌ | Not implemented |
| 17.14 Sensitivity analysis | SHAP global feature importance | ❌ | Not implemented |
| 17.15 Sensitivity analysis | Partial dependence plots (PDP) | ❌ | Not implemented |
| 17.16 Sensitivity analysis | Individual conditional expectation (ICE) | ❌ | Not implemented |
| 17.17 Sensitivity analysis | Accumulated local effects (ALE) | ❌ | Not implemented |
| 17.18 Stress testing | Extreme value analysis | ❌ | Not implemented |
| 17.19 Stress testing | Worst-case analysis | ❌ | Not implemented |
| 17.20 Stress testing | Scenario analysis | ❌ | Not implemented |

---

## 18. INTERPRETABILITY & EXPLAINABILITY

| Step | Technique | Taedri | Notes |
|---|---|---|---|
| 18.1 Global interpretability | Feature importance (tree-based, permutation) | ❌ | Not a filling |
| 18.2 Global interpretability | SHAP values (global) | ❌ | Not a filling |
| 18.3 Global interpretability | Partial dependence plots | ❌ | Not a filling |
| 18.4 Global interpretability | Accumulated local effects | ❌ | Not a filling |
| 18.5 Global interpretability | Friedman's H-statistic (interaction strength) | ❌ | Not a filling |
| 18.6 Global interpretability | Model distillation (teach a simple model) | ❌ | Not a filling |
| 18.7 Local interpretability | LIME (local interpretable model-agnostic explanations) | ❌ | Not a filling |
| 18.8 Local interpretability | SHAP values (local) | ❌ | Not a filling |
| 18.9 Local interpretability | Anchor explanations | ❌ | Not a filling |
| 18.10 Local interpretability | Counterfactual explanations | ❌ | Not a filling |
| 18.11 Local interpretability | Contrastive explanations | ❌ | Not a filling |
| 18.12 Model-specific | Decision tree visualization | ❌ | Not a filling |
| 18.13 Model-specific | Linear model coefficients with confidence intervals | ❌ | Not a filling |
| 18.14 Model-specific | GAM component plots | ❌ | Not a filling |
| 18.15 Model-specific | Neural network attribution (Integrated Gradients, DeepLIFT) | ❌ | Not a filling |
| 18.16 Example-based | Prototypes and criticisms (MMD-critic) | ❌ | Not a filling |
| 18.17 Example-based | Influential instances (influence functions) | ❌ | Not a filling |
| 18.18 Example-based | k-nearest neighbors explanations | ❌ | Not a filling |

---

## 19. FEEDBACK LOOPS & ITERATIVE IMPROVEMENT

| Step | Technique | Taedri | Notes |
|---|---|---|---|
| 19.1 Score feedback | Use holdout score to adjust strategy | ✅ | `TF_LOOP` escalation ladder |
| 19.2 Score feedback | Multi-round improvement with score feedback | ✅ | L3F arm (LLM with feedback) |
| 19.3 Score feedback | Bayesian optimization with score feedback | ❌ | Not implemented |
| 19.4 Score feedback | Reinforcement learning for pipeline optimization | ❌ | Not implemented |
| 19.5 Graph mutation | Add/remove nodes from graph | ✅ | `add_or_remove_node` arm |
| 19.6 Graph mutation | Swap fillings within a slot | ✅ | `variation_swap` arm |
| 19.7 Graph mutation | Cross-axis recombination | ✅ | `cross_axis` arm |
| 19.8 Graph mutation | Transplant from another task's solution | ✅ | `transplant` arm (opt-in) |
| 19.9 Graph mutation | Random sprout (random feasible graph) | ✅ | `taedri-random-sprout-effort-5` |
| 19.10 Graph mutation | Model-guided graph mutation | 🔶 | `model_guided_graph_session` (unscored) |
| 19.11 Graph mutation | LLM-proposed graph patches | 🔶 | `HYBRID_MODEL_PROPOSES` (unscored) |
| 19.12 Graph mutation | LLM diagnosis + patch suggestion | 🔶 | `HYBRID_MODEL_PATCHES` (unscored) |
| 19.13 Graph mutation | LLM selection from Taedri proposals | 🔶 | `HYBRID_MODEL_SELECTS` (unscored) |
| 19.14 Meta-learning | Learn from prior task outcomes | ✅ | `multi_anchor_sprouts` (currently 0) |
| 19.15 Meta-learning | Task-attribute prior (similar tasks → similar graphs) | ✅ | `task_profile_prior.py` (opt-in) |
| 19.16 Meta-learning | Distilled rules from winning model programs | 🔶 | `taedri-medium-distilled` profile |
| 19.17 Meta-learning | Warm-start from similar task solutions | ✅ | `starting_point_binding` |
| 19.18 Meta-learning | Portfolio-based warm-start | ❌ | Not implemented |
| 19.19 Meta-learning | Gradient-based meta-learning (MAML, Reptile) | ❌ | Not implemented |
| 19.20 Meta-learning | Learned optimizer for pipeline search | ❌ | Not implemented |

---

## 20. DEPLOYMENT & SERVING

| Step | Technique | Taedri | Notes |
|---|---|---|---|
| 20.1 Model serialization | pickle, joblib, ONNX, PMML, PFA | ❌ | Not in scope |
| 20.2 Model serialization | MLflow model format | ❌ | Not in scope |
| 20.3 Model serialization | BentoML, Triton, Seldon format | ❌ | Not in scope |
| 20.4 Model optimization | Quantization (INT8, FP16) | ❌ | Not in scope |
| 20.5 Model optimization | Pruning (weight pruning, neuron pruning) | ❌ | Not in scope |
| 20.6 Model optimization | Knowledge distillation | ❌ | Not in scope |
| 20.7 Model optimization | Graph optimization (ONNX, TensorRT) | ❌ | Not in scope |
| 20.8 Model optimization | Compilation (JAX, TVM, OpenVINO) | ❌ | Not in scope |
| 20.9 Serving | REST API (Flask, FastAPI) | ❌ | Not in scope |
| 20.10 Serving | gRPC serving | ❌ | Not in scope |
| 20.11 Serving | Batch inference | ❌ | Not in scope |
| 20.12 Serving | Streaming inference | ❌ | Not in scope |
| 20.13 Serving | Real-time vs. batch tradeoffs | ❌ | Not in scope |
| 20.14 Monitoring | Data drift monitoring | ❌ | Not in scope |
| 20.15 Monitoring | Model performance monitoring | ❌ | Not in scope |
| 20.16 Monitoring | Prediction logging | ❌ | Not in scope |
| 20.17 Monitoring | A/B testing framework | ❌ | Not in scope |
| 20.18 Monitoring | Shadow deployment | ❌ | Not in scope |
| 20.19 Monitoring | Canary deployment | ❌ | Not in scope |
| 20.20 Lifecycle | Model versioning, rollback, approval gates | ❌ | Not in scope |

---

## 21. TAEDRI GRAPH SLOTS — CURRENT STATE

### Current 10 slots (graph_space_search.py:658-682)

| # | Slot | Required | Fillings | Status |
|---|---|---|---|---|
| 0 | `missing_repair` | Yes | 2 (median, median+indicator) | 🔶 Thin — registry has 18-31 options |
| 1 | `categorical_encoding` | Yes | 3 (ordinal, count, one-hot) | 🔶 Thin — registry has 9 encoders |
| 2 | `feature_construction` | No | \~20 (interactions, bins, PCA, ICA, kernels, clusters, target encode, microfeatures) | ✅ Rich |
| 3 | `feature_taming` | No | \~12 (winsorize, rank, taper, standardize, yeo-johnson, quantile) | ✅ Rich |
| 4 | `feature_selection` | No | 4 (fold-local Pearson top-k) | 🔶 Thin — only univariate Pearson |
| 5 | `target_transform` | No | 3 (log1p, signed_log1p, rank_gauss) | 🔶 Thin |
| 6 | `row_weighting` | No | \~5 (residual downweight, class weights) | 🔶 Thin |
| 7 | `estimator` | Yes | \~30 (HGB, Ridge, Huber, ExtraTrees, KNN, LightGBM, XGBoost, SVM, baseline + derived) | ✅ Rich |
| 8 | `calibration` | No | \~2 (isotonic, sigmoid) | 🔶 Thin |
| 9 | `ensemble` | No | 1 (greedy simplex blend) | 🔶 Very thin |

### Proposed new slots (deep_graph_fillings.py)

| # | Slot | Fillings | Purpose |
|---|---|---|---|
| 10 | `dimensionality_reduction` | 16 (PCA, ICA, SVD, factor analysis, variance threshold, collinearity medoid, mutual info) | Fix the 43% gap on wide-feature tasks |
| 11 | `target_balancing` | 3 (SMOTE, quantile transform) | Handle imbalanced/skewed targets |
| 12 | `post_processing` | 3 (MAPIE conformal, prediction clipping) | Uncertainty quantification, safety |

### Proposed new estimator fillings (deep_graph_fillings.py)

| Family | Fillings |
|---|---|
| FLAML AutoML | 4 (reg 60s/120s, clf 60s/120s) |
| MLP neural nets | 4 (reg 100/100, reg 200/100/50, clf 100/100, clf 200/100/50) |
| CatBoost | 2 (reg, clf) |

### Proposed new ensemble fillings (deep_graph_fillings.py)

| Method | Fillings |
|---|---|
| Stacking | 2 (ridge meta, logreg meta) |
| Bagging | 1 (100 estimators) |
| Voting | 2 (soft, hard) |

---

## 22. SUMMARY STATISTICS

| Category | Total techniques | Implemented | Partial | Designed | Not implemented |
|---|---|---|---|---|---|
| Data Loading | 8 | 3 | 1 | 0 | 4 |
| Data Understanding | 14 | 4 | 3 | 1 | 6 |
| EDA | 9 | 0 | 1 | 0 | 8 |
| Missing Values | 18 | 2 | 3 | 0 | 13 |
| Outlier Handling | 18 | 5 | 1 | 0 | 12 |
| Categorical Encoding | 15 | 4 | 1 | 0 | 10 |
| Date/Time Features | 10 | 0 | 1 | 0 | 9 |
| Text Preprocessing | 14 | 0 | 0 | 0 | 14 |
| Feature Engineering | 40 | 12 | 2 | 4 | 22 |
| Dimensionality Reduction | 24 | 2 | 0 | 16 | 6 |
| Feature Selection | 30 | 1 | 0 | 2 | 27 |
| Target Engineering | 26 | 4 | 1 | 2 | 19 |
| Data Splitting | 20 | 8 | 1 | 0 | 11 |
| Model Selection | 60 | 18 | 0 | 8 | 34 |
| Model Training | 32 | 3 | 1 | 0 | 28 |
| Hyperparameter Tuning | 26 | 1 | 1 | 0 | 24 |
| AutoML | 16 | 0 | 0 | 2 | 14 |
| Ensemble Methods | 40 | 3 | 0 | 9 | 28 |
| Post-Processing | 24 | 2 | 0 | 3 | 19 |
| Evaluation | 40 | 14 | 0 | 0 | 26 |
| Stability | 20 | 1 | 1 | 0 | 18 |
| Interpretability | 18 | 0 | 0 | 0 | 18 |
| Feedback Loops | 20 | 8 | 5 | 0 | 7 |
| Deployment | 20 | 0 | 0 | 0 | 20 |
| **TOTAL** | **560** | **95 (17%)** | **23 (4%)** | **47 (8%)** | **395 (71%)** |

---

## 23. HIGHEST-VALUE GAPS (ranked by expected impact)

1. **Dimensionality reduction slot** — 16 fillings designed, fixes the 43% gap on wide-feature tasks
2. **Feature selection expansion** — 27 techniques not implemented; wrapper methods (RFE, forward selection) would directly improve scores
3. **Hyperparameter tuning** — 24 techniques not implemented; Hyperband/BOHB would replace exhaustive enumeration
4. **Ensemble expansion** — 28 techniques not implemented; stacking, bagging, voting would improve every task
5. **Target engineering** — 19 techniques not implemented; SMOTE, cost-sensitive learning for imbalanced tasks
6. **Missing value handling** — 13 techniques not implemented; KNN impute, MICE, iterative impute in registry but not enumerated
7. **Categorical encoding** — 10 techniques not implemented; target encoding, CatBoost encoding, WoE for high-cardinality
8. **Post-processing** — 19 techniques not implemented; conformal prediction, threshold optimization
9. **AutoML integration** — 14 techniques not implemented; FLAML as a node would bring automatic model selection
10. **Meta-learning** — 7 techniques not implemented; the memory system exists but is switched off
