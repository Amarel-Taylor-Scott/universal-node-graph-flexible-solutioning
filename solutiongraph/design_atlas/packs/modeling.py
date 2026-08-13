"""Model, search, evaluation, causality, synthetic-data, and RL packs."""

from __future__ import annotations

from solutiongraph.design_atlas.packs.base import make_pack, q, standard_choices


def _questions(pack_key: str, rows: tuple[tuple, ...]):
    return tuple(
        q(
            pack_key,
            key,
            title,
            prompt,
            rationale,
            standard_choices(pack_key, key, evaluate_label, baseline_label),
            cost=cost,
            risk=risk,
            evidence=evidence,
            trigger_any=triggers,
            references=references,
        )
        for (
            key, title, prompt, rationale, evaluate_label, baseline_label,
            cost, risk, evidence, triggers, references,
        ) in rows
    )


SELECTION_REDUCTION = make_pack(
    "selection-reduction",
    "Feature selection and dimensionality reduction",
    "Bound high-dimensional search while testing stability, leakage, compatibility, and interpretability.",
    "stage.modeling",
    _questions("selection-reduction", (
        (
            "need", "Need for reduction",
            "Do width, sparsity, collinearity, sample ratio, noise, latency, or interpretability create a measured need for selection or reduction?",
            "Reduction can discard useful signal and should solve an observed constraint.",
            "Benchmark no-reduction against bounded reducers", "Use the full compatible feature set", 3, 0.55,
            ("evidence.shape-profile", "evidence.resource-baseline"), (), (),
        ),
        (
            "method-family", "Selection versus projection",
            "Should filter, wrapper, embedded, sparse, supervised, unsupervised, nonlinear, or random projection families be compared?",
            "Families produce different semantics, costs, and compatibility with inference and explanation.",
            "Compare materially different reduction families", "Use a fold-local filter baseline", 5, 0.65,
            ("evidence.reduction-hypothesis", "evidence.fold-local-scope"), (),
            ("source.sklearn.common-pitfalls",),
        ),
        (
            "stability", "Selection stability",
            "Do selected features or components remain stable across folds, seeds, resamples, time, and relevant slices?",
            "A high-scoring unstable subset may not support durable inference or explanation.",
            "Bootstrap and compare selection stability", "Report fold-level selection frequency", 5, 0.75,
            ("evidence.selection-stability",), (), (),
        ),
        (
            "dimension-choice", "Dimension and stopping rule",
            "What variance, reconstruction, predictive, stability, latency, or diminishing-return rule chooses the retained dimension?",
            "Choosing dimension on final test performance leaks and encourages arbitrary complexity.",
            "Trace validation utility versus dimension", "Use a predeclared compact dimension", 5, 0.8,
            ("evidence.dimension-curve", "evidence.stop-rule"), (), (),
        ),
    )),
)


BASELINES_MODELS = make_pack(
    "baselines-models",
    "Baselines and model-family selection",
    "Establish hard-to-beat controls and a diverse, compatible model portfolio before fine tuning.",
    "stage.modeling",
    _questions("baselines-models", (
        (
            "naive-baseline", "Naive and operational controls",
            "Which constant, heuristic, prior-production, linear, seasonal, retrieval, or rule control must every candidate beat?",
            "Without controls, complexity can look useful even when it adds no decision value.",
            "Execute multiple simple controls", "Freeze the strongest simple valid control", 2, 0.9,
            ("evidence.control-plan", "evidence.control-receipts"), (), (),
        ),
        (
            "family-diversity", "Model-family diversity",
            "Which linear, tree, boosted, kernel, nearest-neighbor, probabilistic, neural, retrieval, or hybrid families fit the task and constraints?",
            "Materially different inductive biases improve search coverage and fallback diversity.",
            "Screen compatible model families", "Use linear and tree baselines", 4, 0.65,
            ("evidence.compatibility-admission", "evidence.family-rationale"), (), (),
        ),
        (
            "resource-fit", "Resource and inference fit",
            "Can training, memory, accelerator, batch, streaming, startup, and per-request limits support each family?",
            "Offline quality cannot excuse an unrunnable or unaffordable serving route.",
            "Measure end-to-end resource envelopes", "Choose a resource-safe baseline", 4, 0.85,
            ("evidence.resource-measurements", "evidence.serving-contract"), (),
            ("source.breck.ml-test-score",),
        ),
        (
            "failure-diversity", "Failure and dependency diversity",
            "Do champion and fallback candidates depend on different libraries, providers, features, assumptions, and failure classes?",
            "Second-best average score is not a robust fallback when failures are correlated.",
            "Score fallback portfolios for failure diversity", "Keep a simple independent fallback", 5, 0.8,
            ("evidence.failure-taxonomy", "evidence.dependency-map"), (), (),
        ),
    )),
)


TUNING_SEARCH = make_pack(
    "tuning-search",
    "Hyperparameter, route, and topology search",
    "Declare compatible spaces, priors, budgets, seeds, promotion rules, and exact unvisited coverage.",
    "stage.optimization",
    _questions("tuning-search", (
        (
            "search-space", "Conditional search space",
            "Are parameter domains, conditional activation, forbidden combinations, adapters, and topology alternatives explicit and type-compatible?",
            "Invalid or hidden combinations make search accounting and reproducibility unreliable.",
            "Compile the full declared space", "Search a small explicit compatible grid", 4, 0.95,
            ("evidence.admitted-space", "evidence.constraint-tests"), (), (),
        ),
        (
            "policy", "Search policy and warm starts",
            "Should prior, grid, random, beam, Bayesian, evolutionary, seeded-sprout, successive-halving, or exhaustive policies be allocated?",
            "Policies change proposal order and budget use, not semantic validity or acceptance.",
            "Compare search policies under equal budgets", "Use prior plus seeded random sprouts", 5, 0.65,
            ("evidence.search-policy", "evidence.random-seeds"), (), (),
        ),
        (
            "history", "History-based starts without transfer leakage",
            "Which task attributes and prior receipts justify warm starts, and how will negative transfer and exploration be measured?",
            "Similarity can nominate routes but cannot replace task-local execution evidence.",
            "Compare history, type-only, and random starts", "Mix one prior route with diverse random starts", 5, 0.8,
            ("evidence.history-query", "evidence.prior-receipts", "evidence.negative-transfer-check"), (), (),
        ),
        (
            "budget-coverage", "Budget, coverage, and stopping",
            "What trial, time, cost, failure, fidelity, seed, and concurrency limits apply, and how will skipped and unvisited routes be reported?",
            "A hidden cap can be mistaken for exhaustive search or global optimality.",
            "Trace best-so-far versus budget", "Use a fixed bounded-search budget", 4, 0.9,
            ("evidence.search-budget", "evidence.search-report"), (), (),
        ),
    )),
)


ENSEMBLE_CALIBRATION = make_pack(
    "ensemble-calibration",
    "Ensembling, calibration, and decision thresholds",
    "Separate out-of-fold prediction lineage, diversity, probability quality, threshold utility, and output constraints.",
    "stage.modeling",
    _questions("ensemble-calibration", (
        (
            "oof-lineage", "Out-of-fold prediction lineage",
            "Were ensemble and calibration inputs generated strictly out of fold with immutable model, split, and prediction identities?",
            "Training a meta-model on in-sample predictions creates direct target leakage.",
            "Verify every base-prediction lineage", "Use only cross-fitted base predictions", 4, 1.0,
            ("evidence.oof-lineage", "evidence.split-manifest"), (),
            ("source.sklearn.common-pitfalls",),
        ),
        (
            "diversity", "Ensemble diversity and pruning",
            "Do members add complementary errors after considering correlation, slice behavior, cost, and common dependencies?",
            "Many nearly identical members add latency without robust value.",
            "Measure residual and failure diversity", "Blend a small diverse portfolio", 5, 0.65,
            ("evidence.prediction-correlation", "evidence.failure-diversity"), (), (),
        ),
        (
            "calibration", "Probability and interval calibration",
            "Which calibration notion matters, on which population and slices, and is a separate untouched calibration set required?",
            "Discrimination, calibration, and coverage are different properties.",
            "Compare calibration methods and reliability slices", "Report uncalibrated reliability plus one calibrator", 5, 0.85,
            ("evidence.calibration-curves", "evidence.calibration-split"), (), (),
        ),
        (
            "decision-policy", "Threshold and action policy",
            "How do costs, capacity, abstention, deferral, ranking depth, constraints, and human review turn scores into actions?",
            "A default threshold rarely represents operational utility or capacity.",
            "Optimize policy on validation utility and stress cases", "Use a predeclared conservative threshold", 5, 0.9,
            ("evidence.utility-function", "evidence.capacity-constraint"), (), (),
        ),
    )),
)


EVALUATION_ERROR = make_pack(
    "evaluation-error",
    "Metrics, uncertainty, and error analysis",
    "Evaluate acceptance, utility, slices, uncertainty, learning curves, and concrete failure clusters.",
    "stage.evaluation",
    _questions("evaluation-error", (
        (
            "metric-fit", "Metric-to-decision alignment",
            "Does each metric represent the decision unit, error cost, ranking depth, horizon, calibration, coverage, or resource tradeoff that matters?",
            "Optimizing a convenient metric can worsen the actual decision.",
            "Compare metric sensitivity to stakeholder utility", "Use one primary metric plus hard acceptance", 3, 0.95,
            ("evidence.metric-definition", "evidence.utility-link"), (), (),
        ),
        (
            "uncertainty", "Statistical and run uncertainty",
            "What repeated seeds, resamples, paired tests, intervals, practical-effect thresholds, and multiple-comparison controls are warranted?",
            "A single best score cannot distinguish improvement from noise.",
            "Estimate paired uncertainty and minimum effect", "Report repeated-seed mean and spread", 5, 0.85,
            ("evidence.repeated-receipts", "evidence.uncertainty-analysis"), (), (),
        ),
        (
            "slices", "Slice and intersection evaluation",
            "Which operational, temporal, geographic, demographic, source, difficulty, and low-support intersections need separate results?",
            "Aggregate metrics can conceal severe localized failure.",
            "Evaluate predeclared and discovered slices", "Report all predeclared risk slices", 5, 0.95,
            ("evidence.slice-definitions", "evidence.slice-support"), (),
            ("source.mitchell.model-cards", "source.nist.ai-rmf-1"),
        ),
        (
            "failure-clusters", "Error clusters and counterexamples",
            "What do worst cases, confident errors, abstentions, residual patterns, disagreements, and newly discovered clusters reveal?",
            "Concrete failure modes guide graph mutations more effectively than one aggregate score.",
            "Cluster errors and promote diagnostic cases", "Review worst and confident-error cases", 5, 0.75,
            ("evidence.error-identities", "evidence.failure-taxonomy"), (), (),
        ),
    )),
)


ROBUSTNESS_STABILITY = make_pack(
    "robustness-stability",
    "Robustness, stability, and stress testing",
    "Test plausible distribution shifts, corruptions, adversaries, perturbations, and dependency failures.",
    "stage.evaluation",
    _questions("robustness-stability", (
        (
            "shift-model", "Plausible shift model",
            "Which population, prevalence, covariate, concept, label, temporal, geographic, source, or policy shifts are credible?",
            "Generic noise tests do not substitute for a deployment-grounded shift model.",
            "Construct shift-specific stress suites", "Use temporal/source holdouts", 5, 0.9,
            ("evidence.shift-hypotheses", "evidence.stress-cases"), (),
            ("source.tensorflow.data-validation",),
        ),
        (
            "perturbation", "Semantic perturbation invariance",
            "Which format, spelling, unit, image, wording, missingness, or measurement perturbations should preserve or predictably change output?",
            "Metamorphic checks can test behavior when exact ground truth is expensive.",
            "Execute typed metamorphic relations", "Test declared invariances", 5, 0.8,
            ("evidence.metamorphic-cases",), (), (),
        ),
        (
            "adversary", "Adversary and misuse model",
            "At which lifecycle stage can an attacker poison, evade, extract, infer, inject, exfiltrate, or misuse, with what knowledge and authority?",
            "Attack names without capability and lifecycle context do not define a testable threat.",
            "Build threat-model-specific adversarial cases", "Apply the declared abuse-case baseline", 6, 1.0,
            ("evidence.threat-model", "evidence.adversarial-cases"),
            ("risk.high", "risk.critical", "task.llm-red-teaming"),
            ("source.nist.adversarial-ml",),
        ),
        (
            "dependency-failure", "Dependency and degradation failures",
            "What happens under missing features, provider outage, stale data, model timeout, schema change, or partial downstream failure?",
            "Reliability requires tested degradation and fallback behavior, not only clean offline cases.",
            "Inject dependency and data failures", "Fail closed or use a simple independent fallback", 6, 0.95,
            ("evidence.failure-injection", "evidence.fallback-receipts"), (),
            ("source.breck.ml-test-score",),
        ),
    )),
)


FAIRNESS_RISK = make_pack(
    "fairness-risk",
    "Fairness, privacy, and consequential-risk design",
    "Map affected parties, harms, sensitive attributes, privacy exposure, recourse, and human authority.",
    "stage.governance",
    _questions("fairness-risk", (
        (
            "affected-parties", "Affected parties and harms",
            "Who benefits, who can be burdened, what harms are plausible, and who can contest or correct an output?",
            "Technical users are not the only people affected by a system.",
            "Map stakeholder-specific harms and benefits", "Apply the declared impact assessment", 5, 1.0,
            ("evidence.impact-assessment", "evidence.stakeholder-review"), (),
            ("source.nist.ai-rmf-1",),
        ),
        (
            "fairness-construct", "Fairness construct and groups",
            "Which allocation or quality notion is appropriate, which groups and intersections matter, and what tradeoffs are impossible to satisfy together?",
            "A fairness metric has meaning only relative to the decision, population, and harm model.",
            "Evaluate stakeholder-approved fairness constructs", "Report group quality without optimizing a proxy", 6, 1.0,
            ("evidence.fairness-rationale", "evidence.group-definition"), (),
            ("source.nist.ai-rmf-1", "source.mitchell.model-cards"),
        ),
        (
            "privacy", "Privacy and memorization risk",
            "What personal, confidential, inferred, linked, or memorized information can enter artifacts, prompts, models, logs, or outputs?",
            "Removing obvious identifiers does not eliminate linkage, inference, or memorization risk.",
            "Run privacy threat and data-flow review", "Minimize and aggregate data by default", 6, 1.0,
            ("evidence.privacy-impact", "evidence.data-flow-map"), (),
            ("source.nist.ai-rmf-1",),
        ),
        (
            "human-authority", "Human oversight, recourse, and automation",
            "Which decisions require review, override, appeal, abstention, explanation, or prohibition of automated action?",
            "A human in the loop is ineffective without time, information, authority, and a defined responsibility.",
            "Test review and appeal workflows", "Require human confirmation for consequential actions", 5, 1.0,
            ("evidence.authority-matrix", "evidence.recourse-test"), (),
            ("source.nist.ai-rmf-playbook",),
        ),
    )),
)


INTERPRETABILITY = make_pack(
    "interpretability",
    "Interpretability and explanation",
    "Match explanation method, audience, claim, stability, and actionability to the actual decision.",
    "stage.evaluation",
    _questions("interpretability", (
        (
            "audience-purpose", "Explanation audience and purpose",
            "Is the explanation for debugging, validation, affected-person notice, decision support, recourse, audit, or scientific inference?",
            "One explanation form cannot serve every audience or claim.",
            "Test explanation utility with target audiences", "Provide model and data facts plus limitations", 4, 0.85,
            ("evidence.explanation-purpose", "evidence.audience-review"), (),
            ("source.mitchell.model-cards",),
        ),
        (
            "method", "Global and local explanation methods",
            "Which intrinsic, permutation, attribution, partial-dependence, surrogate, example, or counterfactual methods match model and feature assumptions?",
            "Explanation methods have compatibility conditions and failure modes of their own.",
            "Compare complementary compatible explainers", "Use intrinsic facts and permutation tests", 5, 0.7,
            ("evidence.explainer-compatibility",), (), (),
        ),
        (
            "stability-faithfulness", "Explanation stability and faithfulness",
            "Do explanations remain stable under seeds, resamples, equivalent inputs, correlated features, and model refits, and do they predict intervention effects?",
            "A plausible-looking attribution is not automatically stable, faithful, or causal.",
            "Stress explanation stability and sanity checks", "Label explanations as observational", 6, 0.9,
            ("evidence.explanation-stability", "evidence.sanity-checks"), (), (),
        ),
        (
            "documentation", "Model and system documentation",
            "Will intended use, training/evaluation data, metrics, slices, ethical considerations, caveats, and operational limits be recorded?",
            "A chart or feature list does not communicate system scope and limitations.",
            "Audit the model/system card with stakeholders", "Emit a complete model card", 4, 0.85,
            ("evidence.model-card",), (), ("source.mitchell.model-cards",),
        ),
    )),
)


CAUSALITY_EXPERIMENTS = make_pack(
    "causality-experiments",
    "Causal questions and experiments",
    "Separate prediction from intervention, define estimands and assumptions, and preserve experiment assignment evidence.",
    "stage.specialized",
    _questions("causality-experiments", (
        (
            "estimand", "Causal estimand and intervention",
            "What intervention, population, outcome, horizon, contrast, and aggregation define the estimand?",
            "Causal inference cannot begin with an estimator name; it begins with a precise question.",
            "Review candidate estimands with domain owners", "Keep the task predictive until an estimand exists", 5, 1.0,
            ("evidence.estimand", "evidence.intervention-definition"), ("task.causal-inference",), (),
        ),
        (
            "identification", "Identification assumptions",
            "What exchangeability, positivity, consistency, interference, timing, instrument, discontinuity, or parallel-trend assumptions are required?",
            "No algorithm can recover an unidentified causal effect from the available data.",
            "Challenge assumptions with falsification tests", "Report associations only", 6, 1.0,
            ("evidence.causal-diagram", "evidence.identification-argument"), ("task.causal-inference",), (),
        ),
        (
            "experiment-design", "Randomized experiment design",
            "Can unit, cluster, switchback, stepped-wedge, factorial, or adaptive assignment answer the question without unacceptable interference or risk?",
            "Assignment, power, exposure, and analysis plans must be fixed before outcomes are observed.",
            "Simulate and review experiment designs", "Use a pre-registered fixed design", 7, 1.0,
            ("evidence.assignment-plan", "evidence.power-analysis"), ("task.experiment-design", "task.causal-inference"), (),
        ),
        (
            "sensitivity", "Sensitivity and heterogeneous effects",
            "How sensitive are conclusions to unmeasured confounding, attrition, noncompliance, model choice, interference, and subgroup multiplicity?",
            "Point estimates without robustness and uncertainty hide identification fragility.",
            "Run predeclared sensitivity analyses", "Report bounds and uncertainty", 7, 0.95,
            ("evidence.sensitivity-analysis",), ("task.causal-inference",), (),
        ),
    )),
)


SYNTHETIC_DATA = make_pack(
    "synthetic-data",
    "Synthetic and augmented data",
    "Define purpose, generator boundary, fidelity, privacy, utility, contamination, and mixture experiments.",
    "stage.specialized",
    _questions("synthetic-data", (
        (
            "purpose", "Synthetic-data purpose",
            "Is synthetic data for privacy, coverage, rare cases, simulation, augmentation, balancing, testing, red teaming, or pretraining?",
            "A generator cannot be evaluated without a purpose-specific utility and risk contract.",
            "Define and compare purpose-specific generators", "Use synthetic data only for test fixtures", 4, 0.9,
            ("evidence.synthetic-purpose", "evidence.acceptance-oracle"), ("task.synthetic-data",),
            ("source.gebru.datasheets",),
        ),
        (
            "training-boundary", "Generator training and contamination boundary",
            "Which real records, protected labels, holdouts, prompts, models, or external corpora may the generator inspect?",
            "A generator trained on holdout information can contaminate every downstream experiment.",
            "Audit generator inputs and nearest-neighbor overlap", "Train only on the development partition", 5, 1.0,
            ("evidence.generator-lineage", "evidence.contamination-test"), ("task.synthetic-data",),
            ("source.sklearn.common-pitfalls",),
        ),
        (
            "fidelity-privacy", "Fidelity, diversity, and privacy",
            "Which marginal, dependency, temporal, spatial, semantic, rare-slice, privacy, and memorization measures define acceptable generation?",
            "High aggregate similarity can coexist with mode loss or disclosure of source records.",
            "Evaluate utility, coverage, and privacy jointly", "Reject near-duplicate or unsupported generations", 6, 1.0,
            ("evidence.fidelity-report", "evidence.privacy-tests"), ("task.synthetic-data",),
            ("source.nist.ai-rmf-1",),
        ),
        (
            "mixture-ablation", "Real/synthetic mixture and ablation",
            "At which ratios, stages, curricula, slices, and model families does synthetic supplementation help, hurt, or merely duplicate?",
            "Synthetic data earns value only through clean downstream comparisons and failure analysis.",
            "Run real-only, synthetic-only, and mixture arms", "Use real-only as the control", 6, 0.85,
            ("evidence.mixture-experiment", "evidence.holdout-results"), ("task.synthetic-data",), (),
        ),
    )),
)


REINFORCEMENT_LEARNING = make_pack(
    "reinforcement-learning",
    "Reinforcement learning and sequential decisions",
    "Specify state, action, reward, horizon, behavior policy, simulator validity, constraints, and offline evaluation.",
    "stage.specialized",
    _questions("reinforcement-learning", (
        (
            "mdp-contract", "State, action, reward, and horizon",
            "What information is observable at each decision, which actions are allowed, how is reward delayed, and when does an episode end?",
            "An underspecified sequential decision process cannot support a valid policy comparison.",
            "Validate alternative process formulations", "Freeze the declared finite-horizon process", 5, 1.0,
            ("evidence.sequential-task-contract",), ("task.reinforcement-learning",), (),
        ),
        (
            "logging-policy", "Behavior policy and support",
            "What policy collected offline trajectories, are propensities known, and does it cover candidate actions in relevant states?",
            "Offline policy evaluation fails where the logging data lacks support.",
            "Measure action support and overlap", "Constrain policy to supported actions", 6, 1.0,
            ("evidence.logging-policy", "evidence.support-analysis"), ("task.reinforcement-learning",), (),
        ),
        (
            "evaluation", "Offline and online policy evaluation",
            "Which direct, importance-weighted, doubly robust, simulator, shadow, interleaving, or randomized evaluations are defensible?",
            "Reward estimates from one learned simulator or estimator can be systematically biased.",
            "Compare independent policy estimators", "Require conservative off-policy bounds", 7, 1.0,
            ("evidence.policy-evaluation", "evidence.evaluator-independence"), ("task.reinforcement-learning",), (),
        ),
        (
            "safety", "Constraints and safe exploration",
            "Which actions, states, cumulative costs, populations, or failure probabilities are prohibited, and who can halt or roll back?",
            "Exploration can cause real harm even when expected reward improves.",
            "Stress constrained policies before shadow deployment", "Disallow online exploration", 7, 1.0,
            ("evidence.safety-constraints", "evidence.rollback-test"), ("task.reinforcement-learning",),
            ("source.nist.ai-rmf-1",),
        ),
    )),
)


MODELING_PACKS = (
    SELECTION_REDUCTION,
    BASELINES_MODELS,
    TUNING_SEARCH,
    ENSEMBLE_CALIBRATION,
    EVALUATION_ERROR,
    ROBUSTNESS_STABILITY,
    FAIRNESS_RISK,
    INTERPRETABILITY,
    CAUSALITY_EXPERIMENTS,
    SYNTHETIC_DATA,
    REINFORCEMENT_LEARNING,
)

__all__ = ["MODELING_PACKS"]
