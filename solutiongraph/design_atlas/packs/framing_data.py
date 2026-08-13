"""Problem-framing, data, modality, and split design packs."""

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
            key,
            title,
            prompt,
            rationale,
            evaluate_label,
            baseline_label,
            cost,
            risk,
            evidence,
            triggers,
            references,
        ) in rows
    )


TASK_CONTRACT = make_pack(
    "task-contract",
    "Task contract and decision value",
    "Fix the unit of action, outcome, horizon, acceptance, constraints, and ownership before solution search.",
    "stage.intent",
    _questions("task-contract", (
        (
            "decision-unit", "Decision and prediction unit",
            "What real-world entity, event, or request receives one output, and when is that output actionable?",
            "A row is not necessarily the prediction unit; a wrong unit invalidates labels, splits, and metrics.",
            "Test candidate decision-unit definitions", "Freeze the explicitly supplied unit", 2, 0.95,
            ("evidence.stakeholder-acceptance", "evidence.entity-definition"), (),
            ("source.nist.ai-rmf-1",),
        ),
        (
            "outcome-horizon", "Outcome and horizon",
            "Which observable outcome is required, at what horizon, and when does it become available?",
            "Undefined horizons create label leakage and a mismatch between offline and production questions.",
            "Validate outcome and horizon alternatives", "Use the declared outcome and horizon", 2, 0.95,
            ("evidence.outcome-definition", "evidence.availability-timeline"), (),
            ("source.nist.ai-rmf-playbook",),
        ),
        (
            "acceptance-oracle", "Independent acceptance oracle",
            "What implementation-independent check decides success, and can candidate code read or modify it?",
            "Natural-language goals and self-grading candidates cannot support reliable experiment claims.",
            "Prototype independent oracle candidates", "Use a fixed property-based oracle", 3, 1.0,
            ("evidence.oracle-identity", "evidence.oracle-independence"), (), (),
        ),
        (
            "objectives-constraints", "Objectives and hard constraints",
            "Which quality, cost, latency, reliability, fairness, privacy, and policy measures are objectives versus hard gates?",
            "Turning hard constraints into soft score penalties can select an unacceptable solution.",
            "Elicit and stress-test the objective set", "Use acceptance plus quality/cost/latency", 3, 0.9,
            ("evidence.objective-definition", "evidence.policy-owner"), (),
            ("source.nist.ai-rmf-1",),
        ),
    )),
    ("source.nist.ai-rmf-1", "source.nist.ai-rmf-playbook"),
)


DATA_SOURCE = make_pack(
    "data-source",
    "Data source, collection, and lineage",
    "Interrogate provenance, acquisition, sampling, consent, licensing, freshness, and snapshot identity.",
    "stage.data",
    _questions("data-source", (
        (
            "provenance", "Source provenance and authority",
            "Who created each source, for what purpose, under which authority, and what transformations occurred upstream?",
            "Unknown provenance prevents defensible use, debugging, and transfer claims.",
            "Audit every source and upstream transform", "Accept the signed source manifest", 3, 0.9,
            ("evidence.source-manifest", "evidence.upstream-lineage"), (),
            ("source.gebru.datasheets", "source.pushkarna.data-cards"),
        ),
        (
            "sampling", "Population and sampling mechanism",
            "Which population is represented, who is excluded, and which selection process generated the records?",
            "Selection bias can dominate model choice and is not repaired by a larger model.",
            "Compare sample to the target population", "Document the known sample boundary", 4, 0.9,
            ("evidence.population-definition", "evidence.sampling-analysis"), (),
            ("source.gebru.datasheets",),
        ),
        (
            "license-consent", "License, consent, and retention",
            "Do license, consent, retention, and purpose limitations permit every planned transform, model, and external service?",
            "Technical feasibility cannot grant legal authority or valid consent.",
            "Run source-by-use authorization review", "Restrict use to the declared license", 5, 1.0,
            ("evidence.license", "evidence.consent-policy", "evidence.retention-policy"), (),
            ("source.nist.ai-rmf-1", "source.gebru.datasheets"),
        ),
        (
            "snapshot-freshness", "Snapshot identity and freshness",
            "Can every input be content-addressed, replayed, and compared with expected freshness and late-arrival rules?",
            "Mutable inputs and silent late data make runs irreproducible and invalidate temporal evaluation.",
            "Verify snapshot and freshness behavior", "Freeze one content-addressed snapshot", 3, 0.8,
            ("evidence.dataset-digest", "evidence.freshness-policy"), (),
            ("source.tensorflow.data-validation",),
        ),
    )),
    ("source.gebru.datasheets", "source.pushkarna.data-cards"),
)


SCHEMA_SEMANTICS = make_pack(
    "schema-semantics",
    "Schema and semantic roles",
    "Separate physical types from entity roles, identifiers, units, time semantics, and prohibited fields.",
    "stage.data",
    _questions("schema-semantics", (
        (
            "field-roles", "Semantic field roles",
            "Which fields are identifiers, measurements, categories, free text, targets, groups, timestamps, geography, or metadata?",
            "Dtype inference cannot establish business meaning or whether a field is safe as a feature.",
            "Map and review semantic roles", "Use the signed field-role map", 2, 0.9,
            ("evidence.semantic-field-map",), (), ("source.pushkarna.data-cards",),
        ),
        (
            "units-ranges", "Units, ranges, and invariants",
            "What units, precision, valid ranges, cross-field equations, and state transitions constrain each field?",
            "Unit and invariant violations can remain syntactically valid while being operationally wrong.",
            "Infer then verify candidate constraints", "Apply declared schema constraints", 3, 0.85,
            ("evidence.schema", "evidence.domain-constraints"), (),
            ("source.tensorflow.data-validation",),
        ),
        (
            "identity-keys", "Identity, keys, and multiplicity",
            "Which keys are stable, what is their cardinality, and can one entity legitimately appear in multiple rows or sources?",
            "Unclear identity creates duplicate leakage, incorrect joins, and accidental label replication.",
            "Test candidate identity and join keys", "Use the declared primary/entity keys", 3, 0.9,
            ("evidence.identity-contract", "evidence.cardinality-profile"), (), (),
        ),
        (
            "unknown-schema", "Schema evolution and unknown fields",
            "Should added, removed, reordered, type-changed, and unknown fields fail, warn, quarantine, or adapt?",
            "A schema policy needs explicit forward-compatibility behavior instead of silent coercion.",
            "Replay schema evolution cases", "Reject incompatible schema changes", 3, 0.8,
            ("evidence.schema-evolution-cases",), (), ("source.tensorflow.data-validation",),
        ),
    )),
    ("source.tensorflow.data-validation",),
)


PROFILING_EDA = make_pack(
    "profiling-eda",
    "Profiling and exploratory analysis",
    "Measure distributions, dependencies, missingness, anomalies, slices, and conflicts without converting exploration into proof.",
    "stage.data",
    _questions("profiling-eda", (
        (
            "distribution-shape", "Distribution and support",
            "What are each field's support, quantiles, tails, modes, zero inflation, truncation, and unexpected values?",
            "Shape affects transformations, metrics, estimators, and stress cases.",
            "Profile full and important sliced distributions", "Retain robust summary statistics", 2, 0.65,
            ("evidence.distribution-profile",), (), ("source.tensorflow.data-validation",),
        ),
        (
            "missingness", "Missingness structure",
            "Which values are missing, structurally absent, censored, late, or encoded as placeholders, and how do patterns co-occur?",
            "Treating every null alike can fabricate data and erase informative process failures.",
            "Analyze missingness patterns and causes", "Use typed missingness indicators", 3, 0.8,
            ("evidence.missingness-profile", "evidence.collection-context"), (),
            ("source.gebru.datasheets",),
        ),
        (
            "dependencies", "Dependencies and redundancy",
            "Which linear, monotonic, nonlinear, conditional, temporal, spatial, and entity-level dependencies merit follow-up?",
            "A single correlation matrix misses important dependence and does not establish causality.",
            "Compare complementary dependency screens", "Use robust pairwise screens", 4, 0.65,
            ("evidence.dependency-analysis",), (), (),
        ),
        (
            "conflicts-slices", "Conflicts, anomalies, and slices",
            "Which rare clusters, contradictory records, source disagreements, or stakeholder-relevant slices need separate investigation?",
            "Aggregate summaries can hide systematic failure and valid minority modes.",
            "Interrogate conflict and slice hypotheses", "Review top anomalies and declared slices", 4, 0.85,
            ("evidence.anomaly-identities", "evidence.slice-definitions"), (),
            ("source.nist.ai-rmf-1",),
        ),
    )),
)


QUALITY_CLEANING = make_pack(
    "quality-cleaning",
    "Data quality and reversible cleaning",
    "Choose detection, repair, quarantine, and verification policies without overwriting raw evidence.",
    "stage.data",
    _questions("quality-cleaning", (
        (
            "quality-contract", "Quality acceptance contract",
            "Which completeness, validity, uniqueness, consistency, timeliness, and reconciliation gates are required per field and slice?",
            "A generic cleanliness score hides which defects are unacceptable.",
            "Calibrate field- and slice-specific gates", "Apply the declared quality contract", 3, 0.9,
            ("evidence.quality-contract",), (), ("source.tensorflow.data-validation",),
        ),
        (
            "repair-policy", "Repair versus quarantine",
            "Which defects have deterministic reversible repairs, which need review, and which must be quarantined?",
            "Silent correction can destroy provenance and introduce confident false data.",
            "Shadow-test repair and quarantine policies", "Permit only proven reversible repairs", 3, 0.95,
            ("evidence.repair-receipt", "evidence.reversal-test"), (), (),
        ),
        (
            "duplicates-entities", "Duplicate and entity resolution policy",
            "Are repeated rows, near duplicates, household members, versions, and cross-source entity matches distinct cases?",
            "Deduplication without identity semantics can merge different entities or leak groups across splits.",
            "Benchmark exact, fuzzy, and abstaining match policies", "Use exact duplicate quarantine", 5, 0.9,
            ("evidence.identity-contract", "evidence.match-labeled-set"), (), (),
        ),
        (
            "independent-verification", "Independent post-clean verification",
            "Will a separate verifier rerun critical invariants on the shadow output and compare new versus removed findings?",
            "A repair function should not be the only judge of its own consequence.",
            "Run independent before/after verification", "Verify critical invariants separately", 3, 1.0,
            ("evidence.verification-receipt", "evidence.verifier-identity"), (), (),
        ),
    )),
)


VALIDATION_SPLITS = make_pack(
    "validation-splits",
    "Validation, leakage, and split design",
    "Design immutable development, validation, holdout, stress, temporal, and group boundaries before learned transforms.",
    "stage.evaluation",
    _questions("validation-splits", (
        (
            "split-unit", "Split unit and independence",
            "Must entities, households, devices, sources, locations, or sessions remain wholly inside one split?",
            "Row-level random splitting often leaks correlated units and overstates generalization.",
            "Compare plausible split-unit leakage", "Use group-preserving splits", 3, 1.0,
            ("evidence.group-map", "evidence.split-manifest"), (),
            ("source.sklearn.cross-validation",),
        ),
        (
            "temporal-causality", "Temporal and availability boundary",
            "For each feature and label, was the value actually available at the prediction timestamp?",
            "Event timestamps alone do not prevent future information, revisions, or late joins from leaking.",
            "Replay point-in-time feature availability", "Enforce time-ordered as-of joins", 4, 1.0,
            ("evidence.availability-timeline", "evidence.as-of-join-test"), (),
            ("source.sklearn.common-pitfalls",),
        ),
        (
            "fit-scope", "Fold-local fit scope",
            "Which imputers, encoders, selectors, reducers, samplers, calibrators, and generators learn state and where may they fit?",
            "Nearly every learned preprocessing operation can leak when fitted before the split or outside a fold.",
            "Run explicit leakage negative tests", "Fit all learned transforms fold-locally", 4, 1.0,
            ("evidence.leakage-tests", "evidence.pipeline-scope"), (),
            ("source.sklearn.common-pitfalls",),
        ),
        (
            "holdout-protection", "Holdout and benchmark protection",
            "Who may inspect holdout inputs, labels, oracle code, and results, and when may feedback update the proposal policy?",
            "Repeated tuning on protected results turns the holdout into training data.",
            "Audit evaluator visibility and feedback paths", "Seal holdout until final confirmation", 4, 1.0,
            ("evidence.holdout-policy", "evidence.evaluator-boundary"), (), (),
        ),
    )),
    ("source.sklearn.common-pitfalls", "source.sklearn.cross-validation"),
)


FEATURE_ENGINEERING = make_pack(
    "feature-engineering",
    "Feature engineering and preprocessing",
    "Select typed, fold-safe transformations that preserve inference availability and explain their schema effects.",
    "stage.modeling",
    _questions("feature-engineering", (
        (
            "availability", "Feature availability and stability",
            "Will each candidate feature exist with the same meaning, latency, and reliability at inference time?",
            "Predictive offline fields can be unavailable, delayed, or semantically different in serving.",
            "Replay training-serving feature parity", "Use only contractually available features", 3, 0.95,
            ("evidence.feature-availability", "evidence.training-serving-parity"), (),
            ("source.tensorflow.data-validation",),
        ),
        (
            "encoding", "Encoding and unknown categories",
            "How should ordinal meaning, rare values, high cardinality, unseen categories, and target-based encoding be handled?",
            "Encoding choices impose compatibility, leakage, memory, and extrapolation behavior.",
            "Compare fold-safe encoders including unknowns", "Use ordinal or one-hot baseline with unknown bucket", 4, 0.75,
            ("evidence.cardinality-profile", "evidence.unknown-category-test"), (),
            ("source.sklearn.common-pitfalls",),
        ),
        (
            "scaling-shape", "Scaling and distribution transforms",
            "Which features need robust scaling, monotonic transforms, clipping, binning, or no transform for candidate models?",
            "Transforms should respond to model assumptions and measured shape rather than habit.",
            "Cross-validate compatible transform families", "Use identity or robust scaling baseline", 4, 0.55,
            ("evidence.distribution-profile", "evidence.fold-local-transform"), (),
            ("source.sklearn.common-pitfalls",),
        ),
        (
            "interactions", "Interactions and domain features",
            "Which interactions, aggregates, lags, ratios, embeddings, or domain formulas are causal-time-safe and worth testing?",
            "Unbounded feature generation expands search, instability, and leakage risk.",
            "Ablate bounded feature-family candidates", "Use raw features plus declared domain invariants", 5, 0.65,
            ("evidence.feature-hypothesis", "evidence.ablation-plan"), (), (),
        ),
    )),
)


TARGET_LABELS = make_pack(
    "target-labels",
    "Targets, labels, censoring, and imbalance",
    "Validate how outcomes are generated, transformed, delayed, censored, adjudicated, and represented.",
    "stage.modeling",
    _questions("target-labels", (
        (
            "label-definition", "Label construction and adjudication",
            "What event creates a label, whose judgment is encoded, and how are disagreement, noise, and ambiguity retained?",
            "Labels are measurements with provenance, not automatically ground truth.",
            "Audit and sample-adjudicate label generation", "Use the signed label specification", 4, 0.95,
            ("evidence.label-specification", "evidence.adjudication-sample"), (),
            ("source.gebru.datasheets",),
        ),
        (
            "delay-censoring", "Delay, censoring, and observation windows",
            "Which outcomes are not yet observed, censored, selectively observed, or revised after the training cutoff?",
            "Treating unknown outcomes as negatives systematically biases many real-world tasks.",
            "Model label maturity and censoring alternatives", "Train only on mature labels", 4, 0.95,
            ("evidence.label-maturity-analysis",), (), (),
        ),
        (
            "imbalance-cost", "Imbalance and decision cost",
            "Is rarity meaningful, which errors cost more, and should weighting, sampling, thresholds, ranking, or anomaly framing change?",
            "Class balance alone does not define utility or the correct intervention.",
            "Compare cost-aware imbalance strategies", "Use stratification plus explicit class costs", 4, 0.8,
            ("evidence.class-prevalence", "evidence.error-costs"), (), (),
        ),
        (
            "target-transform", "Target representation and inverse semantics",
            "Would transformation, binning, ordinal framing, multi-task labels, or uncertainty targets improve fit without changing the required output?",
            "Target transforms require reversible output semantics and metrics on the decision scale.",
            "Evaluate target representations with inverse checks", "Preserve the original target scale", 5, 0.65,
            ("evidence.target-profile", "evidence.inverse-transform-test"), (), (),
        ),
    )),
)


TIME_SERIES = make_pack(
    "time-series",
    "Temporal and forecasting design",
    "Make event time, observation time, horizons, exogenous availability, hierarchy, and backtesting explicit.",
    "stage.specialized",
    _questions("time-series", (
        (
            "time-semantics", "Time axes and calendars",
            "Which timestamps mean event, ingestion, revision, availability, local calendar, or forecast origin?",
            "Conflating time axes creates leakage and incorrect seasonality.",
            "Validate time-axis and timezone semantics", "Use event and availability time explicitly", 3, 0.95,
            ("evidence.time-semantics",), ("signal.time-aware", "modality.time-series"), (),
        ),
        (
            "horizon-strategy", "Forecast horizon strategy",
            "Are horizons direct, recursive, multi-output, probabilistic, intermittent, or constrained by downstream decisions?",
            "Different horizons create different error propagation and evaluation requirements.",
            "Backtest multiple horizon strategies", "Use direct horizon-specific baselines", 5, 0.75,
            ("evidence.horizon-contract",), ("task.forecasting",), (),
        ),
        (
            "backtest", "Walk-forward backtest",
            "Do cutoffs reproduce retraining cadence, label delay, late arrivals, cold starts, and realistic exogenous feature availability?",
            "Random cross-validation is usually not a production-faithful forecast evaluator.",
            "Replay rolling-origin backtests", "Use expanding-window backtests", 5, 1.0,
            ("evidence.backtest-manifest",), ("signal.time-aware", "task.forecasting"),
            ("source.sklearn.cross-validation",),
        ),
        (
            "hierarchy-events", "Hierarchy, events, and geotemporal effects",
            "Must forecasts reconcile across entities or geographies, and which holidays, events, weather, or interventions are knowable in advance?",
            "Context enrichments require time-appropriate versions and coherent aggregation.",
            "Ablate hierarchical and event enrichments", "Use calendar-only known-ahead features", 6, 0.7,
            ("evidence.hierarchy", "evidence.event-source-vintage"),
            ("signal.time-aware", "signal.geospatial"), (),
        ),
    )),
)


GEOSPATIAL = make_pack(
    "geospatial",
    "Geospatial and geotemporal enrichment",
    "Resolve place identity, coordinate systems, boundary vintages, proximity, spatial leakage, and time-aware enrichment.",
    "stage.specialized",
    _questions("geospatial", (
        (
            "place-identity", "Place and address identity",
            "Are names, addresses, ZIP codes, counties, regions, coordinates, and jurisdiction codes mutually consistent for the intended vintage?",
            "Strings that look like places may be ambiguous, invalid, historical, or outside the authority source.",
            "Verify against versioned authority sources", "Normalize without asserting unverified identity", 5, 0.9,
            ("evidence.geographic-authority", "evidence.source-vintage"),
            ("signal.geospatial", "modality.geospatial"), (),
        ),
        (
            "coordinate-boundary", "Coordinates, CRS, and boundaries",
            "What coordinate reference system, precision, boundary rule, and boundary vintage apply to point and polygon operations?",
            "CRS or vintage mismatch can produce plausible but wrong joins and distances.",
            "Cross-check CRS and boundary candidates", "Require declared CRS and boundary vintage", 5, 0.95,
            ("evidence.crs", "evidence.boundary-vintage"),
            ("signal.geospatial", "modality.geospatial"), (),
        ),
        (
            "spatial-split", "Spatial dependence and holdouts",
            "Should nearby locations, routes, regions, or spatial clusters be grouped or blocked across evaluation splits?",
            "Random splits can overstate performance when spatial autocorrelation is strong.",
            "Compare random, grouped, and spatial-block splits", "Use region-grouped holdouts", 5, 0.95,
            ("evidence.spatial-dependence", "evidence.split-manifest"),
            ("signal.geospatial", "modality.geospatial"), (),
        ),
        (
            "geotemporal-enrichment", "Time-aware geographic enrichment",
            "For a place and time, which census, event, weather, policy, mobility, or business context was valid and available then?",
            "Joining current geography or future event knowledge to historical rows creates temporal and vintage leakage.",
            "Replay point-in-time geotemporal joins", "Use only versioned as-of enrichment", 6, 1.0,
            ("evidence.as-of-join-test", "evidence.enrichment-lineage"),
            ("signal.geospatial", "signal.time-aware"), (),
        ),
    )),
)


TEXT_DOCUMENT = make_pack(
    "text-document",
    "Text and document systems",
    "Design extraction, normalization, chunking, retrieval, grounding, privacy, and evaluation for unstructured documents.",
    "stage.specialized",
    _questions("text-document", (
        (
            "document-contract", "Document identity and structure",
            "Which pages, sections, tables, versions, languages, encodings, and attachments constitute one document input?",
            "Document boundaries and version identity determine extraction and evaluation truth.",
            "Profile document structure and variants", "Use immutable document/page identities", 3, 0.8,
            ("evidence.document-manifest",), ("modality.text", "modality.document"),
            ("source.gebru.datasheets",),
        ),
        (
            "extraction-grounding", "Extraction and grounding",
            "Must every extracted field or answer retain page, span, region, confidence, and source-version evidence?",
            "Ungrounded values cannot be audited or independently corrected.",
            "Compare grounded extraction routes", "Require source spans for every value", 5, 0.95,
            ("evidence.ground-truth-spans", "evidence.extraction-schema"),
            ("modality.text", "modality.document"), (),
        ),
        (
            "chunk-retrieval", "Chunking and retrieval",
            "Which structural, semantic, sliding, or parent-child chunks preserve context, and how will retrieval misses be measured?",
            "End-answer metrics alone cannot distinguish retrieval failure from generation failure.",
            "Factorially test chunk and retrieval families", "Use structure-aware chunks plus lexical baseline", 6, 0.7,
            ("evidence.retrieval-cases", "evidence.chunk-lineage"),
            ("task.retrieval", "task.llm-evaluation", "modality.document"), (),
        ),
        (
            "untrusted-content", "Untrusted content and privacy",
            "Can documents contain prompt injection, personal data, malicious files, hidden text, or instructions that must remain data?",
            "Document content must not inherit tool authority merely because a model can read it.",
            "Red-team content and authority boundaries", "Treat all document text as untrusted data", 6, 1.0,
            ("evidence.threat-model", "evidence.privacy-review"),
            ("modality.text", "modality.document"),
            ("source.nist.adversarial-ml",),
        ),
    )),
)


IMAGE_MULTIMODAL = make_pack(
    "image-multimodal",
    "Image and multimodal systems",
    "Interrogate capture, transformation, alignment, annotation, robustness, and modality-specific evaluation.",
    "stage.specialized",
    _questions("image-multimodal", (
        (
            "capture-quality", "Capture and representation quality",
            "Which resolution, color, compression, orientation, metadata, device, and acquisition conditions are valid?",
            "Acquisition artifacts can be shortcuts and can shift sharply in deployment.",
            "Profile and stress capture conditions", "Normalize only declared representation fields", 4, 0.75,
            ("evidence.capture-metadata", "evidence.quality-profile"),
            ("modality.image", "modality.multimodal"), (),
        ),
        (
            "annotation", "Annotation geometry and ambiguity",
            "Are labels image-, region-, pixel-, frame-, sequence-, or pair-level, and how are ambiguous cases retained?",
            "A mismatch between annotation and prediction unit invalidates training and metrics.",
            "Audit annotations against prediction units", "Use the signed annotation schema", 5, 0.9,
            ("evidence.annotation-schema", "evidence.annotation-audit"),
            ("modality.image", "modality.multimodal"), (),
        ),
        (
            "alignment", "Cross-modal alignment",
            "Are text, image, audio, video, sensor, and document elements paired at the correct entity and time?",
            "Weak or wrong alignment creates fabricated cross-modal relationships.",
            "Measure alignment confidence and negatives", "Require exact entity/time pairing", 5, 0.9,
            ("evidence.alignment-manifest",), ("modality.multimodal",), (),
        ),
        (
            "robustness-slices", "Visual robustness and slices",
            "Which lighting, viewpoint, occlusion, device, demographic, geography, and corruption slices reflect deployment risk?",
            "Average benchmark performance can hide important capture and population failures.",
            "Evaluate declared natural and synthetic corruptions", "Use capture-condition slice evaluation", 6, 0.9,
            ("evidence.slice-definitions", "evidence.robustness-cases"),
            ("modality.image", "modality.multimodal"),
            ("source.mitchell.model-cards", "source.nist.ai-rmf-1"),
        ),
    )),
)


FRAMING_DATA_PACKS = (
    TASK_CONTRACT,
    DATA_SOURCE,
    SCHEMA_SEMANTICS,
    PROFILING_EDA,
    QUALITY_CLEANING,
    VALIDATION_SPLITS,
    FEATURE_ENGINEERING,
    TARGET_LABELS,
    TIME_SERIES,
    GEOSPATIAL,
    TEXT_DOCUMENT,
    IMAGE_MULTIMODAL,
)

__all__ = ["FRAMING_DATA_PACKS"]
