"""Additional cross-domain reference templates for real application classes."""

from __future__ import annotations

from solutiongraph.template_authoring import (
    build_reference_linear_template as _template,
)

DOCUMENT_INTELLIGENCE = _template(
    template_id="template.document-intelligence",
    title="Document ingestion and structured extraction",
    description=(
        "An acquisition, decoding, cleanup, interpretation, extraction, and evidence scaffold "
        "for unknown or unstructured documents."
    ),
    domains=("data-engineering.documents", "ai.document-intelligence"),
    tags=("ingestion", "extraction", "unstructured-data"),
    stages=(
        (
            "stage.acquire",
            "Acquire",
            "Accept documents and establish source identity.",
            (
                ("receive_document", "Receive a document with immutable source metadata."),
                ("detect_format", "Detect container, encoding, language hints, and corruption."),
                ("malware_policy", "Apply the declared content safety and quarantine policy."),
            ),
        ),
        (
            "stage.decode",
            "Decode",
            "Produce source-grounded machine-readable content.",
            (
                ("repair_container", "Repair or reject malformed containers without inventing content."),
                ("extract_native_text", "Extract embedded text, layout, and metadata when available."),
                ("render_pages", "Render stable page images for visual processing when required."),
                ("recognize_text", "Recognize text from visual regions with confidence and provenance."),
            ),
        ),
        (
            "stage.normalize",
            "Normalize",
            "Standardize content while preserving traceability.",
            (
                ("remove_boilerplate", "Separate repeated headers, footers, watermarks, and navigation."),
                ("normalize_symbols", "Normalize encodings, whitespace, and symbols under a reversible policy."),
                ("translate_content", "Translate content into the target language when the contract requires it."),
                ("segment_structure", "Segment pages, sections, tables, figures, and reading order."),
            ),
        ),
        (
            "stage.extract",
            "Extract",
            "Generate schema-bound candidate facts.",
            (
                ("prioritize_regions", "Prioritize source regions relevant to the requested schema."),
                ("extract_deterministic", "Apply deterministic parsers, rules, and validators."),
                ("extract_model_assisted", "Apply admitted model-based extraction with structured output."),
                ("reconcile_candidates", "Reconcile conflicting values using source and confidence evidence."),
            ),
        ),
        (
            "stage.deliver",
            "Deliver",
            "Verify and publish traceable structured output.",
            (
                ("validate_schema", "Validate types, required fields, constraints, and cross-field rules."),
                ("ground_output", "Attach page, region, and source citations to extracted values."),
                ("publish_record", "Publish accepted records, rejects, and a replayable receipt."),
            ),
        ),
    ),
)


WEB_AUTOMATION = _template(
    template_id="template.web-automation",
    title="Reliable automated web interaction",
    description=(
        "A browser-agnostic intent, navigation, perception, action, verification, recovery, "
        "and evidence scaffold."
    ),
    domains=("software.web-automation", "ai.computer-use"),
    tags=("browser", "interaction", "verification"),
    stages=(
        (
            "stage.contract",
            "Contract",
            "Turn user intent into bounded web obligations.",
            (
                ("interpret_intent", "Translate the requested outcome into explicit web actions and limits."),
                ("authorize_scope", "Confirm permitted sites, accounts, data, and consequential actions."),
                ("define_oracle", "Define independent observable success and stop conditions."),
            ),
        ),
        (
            "stage.reach",
            "Reach",
            "Establish a usable browsing context.",
            (
                ("select_runtime", "Select an admitted browser binary, controller, and transport."),
                ("open_target", "Reach the intended origin and preserve navigation evidence."),
                ("settle_page", "Wait for the required document, network, and application state."),
            ),
        ),
        (
            "stage.perceive",
            "Perceive",
            "Build a trustworthy view of the current interface.",
            (
                ("capture_state", "Capture DOM, accessibility, visual, and network state as permitted."),
                ("locate_target", "Locate the intended element or region using admitted strategies."),
                ("disambiguate_target", "Resolve multiple matches using context and policy."),
                ("check_preconditions", "Verify visibility, enabled state, identity, and action preconditions."),
            ),
        ),
        (
            "stage.act",
            "Act",
            "Perform one bounded interface mutation.",
            (
                ("choose_action", "Choose a contract-compatible deterministic or model-guided action."),
                ("execute_action", "Execute the action with exact target and parameter evidence."),
                ("capture_outcome", "Capture the immediate application and network outcome."),
            ),
        ),
        (
            "stage.verify",
            "Verify",
            "Confirm that the intended state transition occurred.",
            (
                ("verify_transition", "Compare observed state with the declared success condition."),
                ("detect_side_effects", "Detect unexpected navigation, mutation, download, or account effects."),
                ("extract_result", "Extract the requested typed data or resulting artifact."),
            ),
        ),
        (
            "stage.recover",
            "Recover",
            "Handle failure without hiding it.",
            (
                ("classify_failure", "Classify selector, timing, auth, policy, network, and semantic failures."),
                ("repair_or_fallback", "Retry, heal, or switch routes within the explicit budget."),
                ("publish_receipt", "Publish actions, observations, artifacts, and final acceptance."),
            ),
        ),
    ),
)


IMAGE_PROCESSING = _template(
    template_id="template.image-processing",
    title="Image inspection, transformation, and analysis",
    description="A provenance-preserving image quality, analysis, transformation, and delivery scaffold.",
    domains=("media.image-processing", "ai.computer-vision"),
    tags=("image", "vision", "transformation"),
    stages=(
        (
            "stage.ingest",
            "Ingest",
            "Validate and decode the source image.",
            (
                ("load_image", "Load the exact image bytes and source metadata."),
                ("decode_image", "Decode format, color model, orientation, and frame structure."),
                ("validate_integrity", "Detect truncation, malformed regions, and unsupported encodings."),
            ),
        ),
        (
            "stage.inspect",
            "Inspect",
            "Measure source quality and content evidence.",
            (
                ("quality_profile", "Measure resolution, noise, blur, compression, clipping, and exposure."),
                ("detect_regions", "Detect faces, objects, corners, text regions, and regions of interest."),
                ("detect_synthetic", "Run admitted synthetic-media and manipulation detectors."),
                ("extract_metadata", "Extract permitted metadata and provenance claims."),
            ),
        ),
        (
            "stage.transform",
            "Transform",
            "Apply explicit reversible or declared image operations.",
            (
                ("normalize_geometry", "Correct orientation, crop, pad, resize, or rectify geometry."),
                ("normalize_color", "Convert color space and normalize white balance or tone."),
                ("enhance_signal", "Adjust contrast, sharpness, denoising, or restoration under policy."),
                ("apply_distortion", "Apply requested augmentation or distortion with recorded parameters."),
            ),
        ),
        (
            "stage.analyze",
            "Analyze",
            "Produce typed content findings.",
            (
                ("recognize_text", "Recognize and ground visible text."),
                ("classify_content", "Classify requested visual attributes with confidence."),
                ("measure_geometry", "Measure spatial relationships, boundaries, and regions."),
                ("reconcile_findings", "Reconcile model and deterministic findings."),
            ),
        ),
        (
            "stage.deliver",
            "Deliver",
            "Encode, verify, and publish outputs.",
            (
                ("encode_output", "Encode the requested image and metadata format."),
                ("verify_output", "Verify dimensions, appearance, content constraints, and no unintended loss."),
                ("publish_artifacts", "Publish outputs, masks, findings, and transformation receipt."),
            ),
        ),
    ),
)


BATCH_DATA_PIPELINE = _template(
    template_id="template.batch-data-pipeline",
    title="Batch data engineering pipeline",
    description="A source-contract, ingestion, transformation, quality, publication, and operation scaffold.",
    domains=("data-engineering.batch",),
    tags=("etl", "lineage", "data-quality"),
    stages=(
        (
            "stage.contract",
            "Contract",
            "Define data products and operating constraints.",
            (
                ("define_sources", "Define source identities, ownership, cadence, and access contracts."),
                ("define_product", "Define output schema, semantics, freshness, and consumers."),
                ("define_slas", "Define quality, latency, recovery, and retention objectives."),
            ),
        ),
        (
            "stage.ingest",
            "Ingest",
            "Acquire source snapshots safely.",
            (
                ("extract_sources", "Extract source data using bounded incremental or full reads."),
                ("validate_arrival", "Validate expected partitions, counts, checksums, and freshness."),
                ("capture_lineage", "Capture immutable source, schema, and extraction provenance."),
            ),
        ),
        (
            "stage.transform",
            "Transform",
            "Produce stable intermediate and business values.",
            (
                ("normalize_schema", "Normalize types, names, null semantics, and units."),
                ("apply_business_rules", "Apply versioned deterministic business transformations."),
                ("join_sources", "Join sources with declared keys, cardinality, and loss accounting."),
                ("aggregate_values", "Aggregate at declared grains with reconciliation checks."),
            ),
        ),
        (
            "stage.assure",
            "Assure",
            "Detect invalid or drifting outputs.",
            (
                ("validate_constraints", "Validate schema, uniqueness, referential, and business constraints."),
                ("detect_drift", "Detect source, schema, distribution, and volume drift."),
                ("reconcile_totals", "Reconcile source-to-output counts, balances, and rejects."),
            ),
        ),
        (
            "stage.publish",
            "Publish",
            "Commit one versioned data product.",
            (
                ("write_product", "Write outputs atomically in the declared storage contract."),
                ("publish_metadata", "Publish catalog, lineage, quality, and ownership metadata."),
                ("notify_consumers", "Emit idempotent availability or failure events."),
            ),
        ),
        (
            "stage.operate",
            "Operate",
            "Preserve evidence and recoverability.",
            (
                ("record_run", "Record inputs, route, code, environment, metrics, and outcomes."),
                ("apply_recovery", "Retry, backfill, quarantine, or rollback under explicit policy."),
            ),
        ),
    ),
)


API_SERVICE = _template(
    template_id="template.api-service",
    title="Production API service",
    description="A contract-first API design, implementation, protection, verification, and operation scaffold.",
    domains=("software.backend", "software.api"),
    tags=("service", "api", "operations"),
    stages=(
        (
            "stage.contract",
            "Contract",
            "Define externally observable service behavior.",
            (
                ("identify_consumers", "Identify consumers, trust boundaries, and compatibility commitments."),
                ("define_api_schema", "Define versioned requests, responses, errors, and semantics."),
                ("define_slos", "Define latency, availability, durability, and correctness objectives."),
            ),
        ),
        (
            "stage.design",
            "Design",
            "Choose explicit state and interaction boundaries.",
            (
                ("model_domain", "Model domain values, invariants, and state transitions."),
                ("design_persistence", "Design persistence, transaction, migration, and consistency contracts."),
                ("design_dependencies", "Define external dependency contracts and failure behavior."),
            ),
        ),
        (
            "stage.implement",
            "Implement",
            "Build atomic request-processing obligations.",
            (
                ("parse_request", "Parse and schema-check the exact incoming request."),
                ("authenticate_request", "Authenticate the caller and credential context."),
                ("authorize_operation", "Authorize the requested operation and resource scope."),
                ("execute_domain_logic", "Execute domain rules under transaction and idempotency policy."),
                ("serialize_response", "Serialize typed success or error responses without information leakage."),
            ),
        ),
        (
            "stage.protect",
            "Protect",
            "Apply resilience and abuse controls.",
            (
                ("enforce_limits", "Enforce payload, rate, quota, timeout, and concurrency limits."),
                ("handle_dependency_failure", "Retry, isolate, degrade, or fail dependencies by policy."),
                ("emit_observability", "Emit redacted traces, metrics, logs, and audit events."),
            ),
        ),
        (
            "stage.assure",
            "Assure",
            "Prove the service contract and deployability.",
            (
                ("run_contract_tests", "Run schema, compatibility, property, and integration tests."),
                ("run_security_tests", "Run authorization, input, abuse, and dependency security tests."),
                ("verify_capacity", "Verify capacity and SLO behavior under representative load."),
                ("publish_service", "Deploy, verify, and publish service and operational receipts."),
            ),
        ),
    ),
)


EVENT_DRIVEN_SYSTEM = _template(
    template_id="template.event-driven-system",
    title="Event-driven application",
    description="An event contract, ingestion, processing, coordination, delivery, and observability scaffold.",
    domains=("software.event-driven", "software.distributed"),
    tags=("events", "messaging", "reliability"),
    stages=(
        (
            "stage.contract",
            "Contract",
            "Define event meaning and delivery guarantees.",
            (
                ("define_event_schema", "Define versioned event identity, payload, and semantic meaning."),
                ("define_delivery_semantics", "Define ordering, duplication, latency, and durability semantics."),
                ("define_failure_policy", "Define retry, dead-letter, compensation, and replay policy."),
            ),
        ),
        (
            "stage.ingest",
            "Ingest",
            "Accept and authenticate events.",
            (
                ("receive_event", "Receive an event with transport and source evidence."),
                ("authenticate_event", "Authenticate producer and verify message integrity."),
                ("validate_event", "Validate schema, version, identifiers, and temporal bounds."),
                ("deduplicate_event", "Detect duplicate delivery under the declared identity contract."),
            ),
        ),
        (
            "stage.process",
            "Process",
            "Derive one deterministic state transition.",
            (
                ("load_state", "Load required state at a declared consistency level."),
                ("apply_transition", "Apply domain invariants and compute the intended transition."),
                ("persist_transition", "Persist state and event progress atomically or compensatably."),
            ),
        ),
        (
            "stage.coordinate",
            "Coordinate",
            "Publish downstream work safely.",
            (
                ("derive_events", "Derive typed downstream events from the accepted transition."),
                ("publish_events", "Publish events under the declared atomicity and retry model."),
                ("coordinate_saga", "Advance or compensate multi-step workflows when required."),
            ),
        ),
        (
            "stage.operate",
            "Operate",
            "Observe and recover the event flow.",
            (
                ("observe_lag", "Measure backlog, latency, failure, and replay state."),
                ("handle_poison_event", "Quarantine or repair poison events without blocking unrelated work."),
                ("replay_safely", "Replay a bounded event range with idempotency evidence."),
                ("publish_receipt", "Publish state, offsets, effects, and recovery evidence."),
            ),
        ),
    ),
)


TIME_SERIES_FORECASTING = _template(
    template_id="template.time-series-forecasting",
    title="Time-series forecasting",
    description="A leakage-safe time-series preparation, modeling, validation, combination, and delivery scaffold.",
    domains=("machine-learning.time-series",),
    tags=("forecasting", "validation", "ensemble"),
    stages=(
        (
            "stage.contract",
            "Contract",
            "Define the forecasting decision and evaluation contract.",
            (
                ("define_series", "Define entities, target, timestamps, frequency, and observation semantics."),
                ("define_horizon", "Define forecast origin, horizon, update cadence, and latency."),
                ("define_metric", "Define point, probabilistic, tail, and business evaluation metrics."),
            ),
        ),
        (
            "stage.investigate",
            "Investigate",
            "Understand temporal structure before modeling.",
            (
                ("validate_timeline", "Validate ordering, frequency, gaps, duplicates, and timezone semantics."),
                ("detect_regimes", "Detect trend, seasonality, changepoints, intermittency, and regimes."),
                ("audit_leakage", "Audit future, revision, entity, and aggregation leakage."),
            ),
        ),
        (
            "stage.prepare",
            "Prepare",
            "Construct causal training values.",
            (
                ("repair_observations", "Repair or represent missing, duplicated, and anomalous observations."),
                ("align_covariates", "Align known-future and observed covariates to forecast origins."),
                ("generate_temporal_features", "Generate lag, rolling, calendar, hierarchy, and regime features."),
                ("define_backtests", "Define rolling or expanding backtests representative of deployment."),
            ),
        ),
        (
            "stage.model",
            "Model",
            "Fit diverse admitted forecast routes.",
            (
                ("fit_baseline", "Fit naive and seasonal baselines that establish a floor."),
                ("fit_statistical", "Fit admitted statistical and state-space candidates."),
                ("fit_machine_learning", "Fit admitted feature-based machine-learning candidates."),
                ("fit_deep_model", "Fit admitted deep temporal candidates when justified."),
            ),
        ),
        (
            "stage.combine",
            "Combine",
            "Calibrate and combine forecasts without leakage.",
            (
                ("generate_backtest_predictions", "Generate complete origin-safe validation predictions."),
                ("calibrate_intervals", "Calibrate uncertainty intervals and coverage."),
                ("reconcile_hierarchy", "Reconcile hierarchical or grouped series constraints."),
                ("ensemble_forecasts", "Combine complementary forecasts using held-out evidence."),
            ),
        ),
        (
            "stage.deliver",
            "Deliver",
            "Verify and publish forecast artifacts.",
            (
                ("stress_test", "Stress missingness, shifts, sparse history, and extreme events."),
                ("publish_forecast", "Publish predictions, intervals, route, assumptions, and receipt."),
            ),
        ),
    ),
)


RECOMMENDATION_RANKING = _template(
    template_id="template.recommendation-ranking",
    title="Recommendation and ranking system",
    description="A candidate generation, ranking, policy, evaluation, serving, and feedback scaffold.",
    domains=("machine-learning.recommendation", "software.ranking"),
    tags=("ranking", "personalization", "experimentation"),
    stages=(
        (
            "stage.contract",
            "Contract",
            "Define recommendation outcomes and constraints.",
            (
                ("define_objectives", "Define user, business, ecosystem, and safety objectives."),
                ("define_eligibility", "Define item, user, jurisdiction, and inventory eligibility."),
                ("define_evaluation", "Define offline, counterfactual, online, and guardrail metrics."),
            ),
        ),
        (
            "stage.data",
            "Data",
            "Build time-correct recommendation evidence.",
            (
                ("ingest_interactions", "Ingest impressions, actions, outcomes, and exposure context."),
                ("construct_labels", "Construct outcome labels with delay and censoring policy."),
                ("build_features", "Build point-in-time user, item, context, and interaction features."),
            ),
        ),
        (
            "stage.candidates",
            "Candidates",
            "Retrieve a broad eligible item set.",
            (
                ("retrieve_candidates", "Retrieve candidates using one or more admitted strategies."),
                ("merge_candidate_sets", "Merge, deduplicate, and preserve retrieval provenance."),
                ("filter_eligibility", "Apply hard eligibility, availability, and safety constraints."),
            ),
        ),
        (
            "stage.rank",
            "Rank",
            "Score and arrange candidates.",
            (
                ("score_relevance", "Score expected relevance or utility with calibrated evidence."),
                ("apply_multiobjective_policy", "Balance declared objectives and hard guardrails."),
                ("diversify_results", "Apply diversity, novelty, coverage, and repetition policy."),
                ("assemble_slate", "Assemble a position-aware final slate."),
            ),
        ),
        (
            "stage.evaluate",
            "Evaluate",
            "Test ranking behavior independently.",
            (
                ("offline_evaluation", "Evaluate ranking, calibration, coverage, and subgroup behavior."),
                ("bias_safety_audit", "Audit feedback loops, exposure bias, fairness, and unsafe content."),
                ("online_experiment", "Run bounded randomized or interleaving experiments when authorized."),
            ),
        ),
        (
            "stage.serve",
            "Serve",
            "Deliver and learn from recommendations.",
            (
                ("serve_slate", "Serve the exact slate within latency and consistency limits."),
                ("record_exposure", "Record exposure, route, position, policy, and experiment identity."),
                ("ingest_feedback", "Ingest delayed outcomes and update evidence without rewriting history."),
            ),
        ),
    ),
)


INCIDENT_RESPONSE = _template(
    template_id="template.incident-response",
    title="Cybersecurity incident response",
    description="A bounded detection, triage, containment, eradication, recovery, and learning scaffold.",
    domains=("security.incident-response", "operations.reliability"),
    tags=("security", "incident", "recovery"),
    stages=(
        (
            "stage.prepare",
            "Prepare",
            "Establish authority, evidence, and response boundaries.",
            (
                ("load_response_policy", "Load response authority, severity, privacy, and notification policy."),
                ("identify_assets", "Identify affected assets, owners, dependencies, and criticality."),
                ("preserve_initial_evidence", "Preserve volatile and durable evidence with chain of custody."),
            ),
        ),
        (
            "stage.detect",
            "Detect",
            "Validate and scope the suspected incident.",
            (
                ("normalize_alerts", "Normalize alerts and observations into a versioned event model."),
                ("correlate_indicators", "Correlate identities, indicators, timelines, and affected resources."),
                ("validate_incident", "Distinguish incident, benign behavior, and insufficient evidence."),
            ),
        ),
        (
            "stage.triage",
            "Triage",
            "Prioritize and plan bounded response.",
            (
                ("assess_impact", "Assess confidentiality, integrity, availability, safety, and business impact."),
                ("classify_severity", "Classify severity and reporting obligations under policy."),
                ("select_response_plan", "Select authorized containment and evidence-preservation actions."),
            ),
        ),
        (
            "stage.contain",
            "Contain",
            "Limit harm while preserving recoverability.",
            (
                ("isolate_scope", "Isolate affected identities, hosts, workloads, or network segments."),
                ("block_indicators", "Block verified malicious indicators with expiry and rollback."),
                ("monitor_containment", "Verify containment and detect displacement or persistence."),
            ),
        ),
        (
            "stage.recover",
            "Recover",
            "Remove cause and restore trusted operation.",
            (
                ("eradicate_cause", "Remove persistence, vulnerabilities, compromised secrets, and artifacts."),
                ("restore_services", "Restore services and data from verified trusted state."),
                ("verify_recovery", "Verify security, integrity, functionality, and monitoring coverage."),
            ),
        ),
        (
            "stage.learn",
            "Learn",
            "Close obligations and improve defenses.",
            (
                ("notify_stakeholders", "Complete authorized legal, customer, partner, and internal notifications."),
                ("publish_incident_record", "Publish timeline, evidence, actions, impact, and decisions."),
                ("improve_controls", "Convert verified lessons into owned preventive and detective changes."),
            ),
        ),
    ),
)


CUSTOMER_SUPPORT = _template(
    template_id="template.customer-support",
    title="Customer support case resolution",
    description="An intake, understanding, policy, resolution, communication, and learning scaffold.",
    domains=("business.customer-support", "software.workflow"),
    tags=("support", "case-management", "automation"),
    stages=(
        (
            "stage.intake",
            "Intake",
            "Create a trustworthy support case.",
            (
                ("receive_contact", "Receive the customer contact and channel metadata."),
                ("authenticate_customer", "Authenticate identity only to the level required by the request."),
                ("redact_sensitive_data", "Detect, minimize, and protect unnecessary sensitive content."),
            ),
        ),
        (
            "stage.understand",
            "Understand",
            "Determine intent, context, and urgency.",
            (
                ("classify_intent", "Classify the requested outcome and affected product or process."),
                ("extract_case_facts", "Extract source-grounded facts, dates, identifiers, and commitments."),
                ("retrieve_context", "Retrieve authorized account, order, policy, and interaction context."),
                ("assess_priority", "Assess urgency, vulnerability, impact, and escalation criteria."),
            ),
        ),
        (
            "stage.resolve",
            "Resolve",
            "Select and execute an authorized remedy.",
            (
                ("retrieve_policy", "Retrieve the exact applicable policy, entitlement, and exceptions."),
                ("generate_options", "Generate contract-compatible resolution options."),
                ("select_resolution", "Select a resolution using authority, evidence, cost, and customer impact."),
                ("execute_resolution", "Execute the approved account, refund, replacement, or workflow action."),
            ),
        ),
        (
            "stage.communicate",
            "Communicate",
            "Explain and confirm the outcome.",
            (
                ("compose_response", "Compose a clear, accurate, policy-grounded response."),
                ("verify_response", "Verify facts, promises, tone, privacy, and required disclosures."),
                ("deliver_response", "Deliver through the authorized channel and preserve evidence."),
            ),
        ),
        (
            "stage.close",
            "Close",
            "Verify completion and improve the system.",
            (
                ("verify_resolution", "Verify that promised actions completed and the case oracle passes."),
                ("route_followup", "Schedule, escalate, or reopen unresolved obligations."),
                ("record_outcome", "Record resolution, effort, cost, feedback, and reusable evidence."),
            ),
        ),
    ),
)


INFRASTRUCTURE_PROVISIONING = _template(
    template_id="template.infrastructure-provisioning",
    title="Infrastructure provisioning",
    description="A desired-state, planning, policy, application, verification, and lifecycle scaffold.",
    domains=("operations.infrastructure", "software.delivery"),
    tags=("infrastructure-as-code", "security", "operations"),
    stages=(
        (
            "stage.define",
            "Define",
            "Specify desired infrastructure and constraints.",
            (
                ("load_desired_state", "Load versioned desired state, environment, and ownership."),
                ("resolve_dependencies", "Resolve providers, modules, images, and immutable dependencies."),
                ("define_policies", "Define security, residency, cost, resilience, and naming policies."),
            ),
        ),
        (
            "stage.discover",
            "Discover",
            "Establish the current trusted state.",
            (
                ("authenticate_provider", "Authenticate to the declared provider and account scope."),
                ("read_current_state", "Read current resources, state, drift, and locks."),
                ("import_unmanaged_state", "Detect and explicitly reconcile unmanaged resources."),
            ),
        ),
        (
            "stage.plan",
            "Plan",
            "Compute and qualify the intended changes.",
            (
                ("compute_change_plan", "Compute create, update, replace, and destroy operations."),
                ("estimate_cost", "Estimate one-time and recurring cost deltas."),
                ("evaluate_policy", "Evaluate security, compliance, blast radius, and approval policy."),
                ("approve_plan", "Record authorized approval for the exact plan digest."),
            ),
        ),
        (
            "stage.apply",
            "Apply",
            "Execute the immutable plan safely.",
            (
                ("acquire_lock", "Acquire an environment-scoped mutation lock."),
                ("apply_changes", "Apply changes idempotently with bounded retries."),
                ("handle_partial_failure", "Recover, continue, or rollback partial application by policy."),
            ),
        ),
        (
            "stage.verify",
            "Verify",
            "Prove desired state and operational readiness.",
            (
                ("verify_resources", "Verify actual resources, configuration, connectivity, and health."),
                ("verify_security", "Verify identity, network, encryption, secrets, and logging controls."),
                ("publish_state", "Publish protected state, outputs, drift baseline, and receipt."),
                ("schedule_lifecycle", "Schedule drift detection, rotation, backup, and decommission obligations."),
            ),
        ),
    ),
)


SCIENTIFIC_EXPERIMENT = _template(
    template_id="template.scientific-experiment",
    title="Reproducible scientific experiment",
    description="A hypothesis, design, acquisition, analysis, replication, and publication scaffold.",
    domains=("science.experiment", "research.reproducibility"),
    tags=("experiment", "statistics", "provenance"),
    stages=(
        (
            "stage.question",
            "Question",
            "Turn a research question into falsifiable obligations.",
            (
                ("define_question", "Define scope, population, constructs, and intended inference."),
                ("state_hypotheses", "State falsifiable hypotheses and alternative explanations."),
                ("define_outcomes", "Define primary, secondary, and safety outcomes before observation."),
            ),
        ),
        (
            "stage.design",
            "Design",
            "Create an identifiable and adequately powered study.",
            (
                ("select_design", "Select experimental or observational design and assignment mechanism."),
                ("define_sampling", "Define sampling frame, inclusion, exclusion, and recruitment."),
                ("plan_power", "Plan sample size, precision, stopping, and multiplicity."),
                ("preregister_analysis", "Freeze hypotheses, exclusions, transformations, and analysis plan."),
            ),
        ),
        (
            "stage.acquire",
            "Acquire",
            "Collect trustworthy observations.",
            (
                ("calibrate_instruments", "Calibrate instruments, annotators, or measurement systems."),
                ("collect_observations", "Collect observations under the approved protocol."),
                ("monitor_protocol", "Monitor deviations, missingness, safety, and data integrity."),
            ),
        ),
        (
            "stage.analyze",
            "Analyze",
            "Apply the frozen analysis and explicit sensitivity routes.",
            (
                ("validate_measurements", "Validate measurements, exclusions, and preprocessing provenance."),
                ("estimate_effects", "Estimate effects or associations with uncertainty."),
                ("check_assumptions", "Check model, design, measurement, and missing-data assumptions."),
                ("run_sensitivity", "Run declared robustness, subgroup, and alternative-specification analyses."),
            ),
        ),
        (
            "stage.reproduce",
            "Reproduce",
            "Verify computational and inferential stability.",
            (
                ("reexecute_analysis", "Reexecute from immutable data, code, environment, and seeds."),
                ("independent_review", "Apply independent methodological and domain review."),
                ("replicate_result", "Attempt internal or external replication when feasible."),
            ),
        ),
        (
            "stage.publish",
            "Publish",
            "Report results and limitations without hiding alternatives.",
            (
                ("assemble_evidence", "Assemble data lineage, analysis, diagnostics, and decision receipts."),
                ("report_results", "Report estimates, uncertainty, deviations, limitations, and null findings."),
                ("publish_artifacts", "Publish permitted data, code, environment, and provenance artifacts."),
            ),
        ),
    ),
)


EXTENDED_TEMPLATES = (
    API_SERVICE,
    BATCH_DATA_PIPELINE,
    CUSTOMER_SUPPORT,
    DOCUMENT_INTELLIGENCE,
    EVENT_DRIVEN_SYSTEM,
    IMAGE_PROCESSING,
    INCIDENT_RESPONSE,
    INFRASTRUCTURE_PROVISIONING,
    RECOMMENDATION_RANKING,
    SCIENTIFIC_EXPERIMENT,
    TIME_SERIES_FORECASTING,
    WEB_AUTOMATION,
)


__all__ = [
    "API_SERVICE",
    "BATCH_DATA_PIPELINE",
    "CUSTOMER_SUPPORT",
    "DOCUMENT_INTELLIGENCE",
    "EVENT_DRIVEN_SYSTEM",
    "EXTENDED_TEMPLATES",
    "IMAGE_PROCESSING",
    "INCIDENT_RESPONSE",
    "INFRASTRUCTURE_PROVISIONING",
    "RECOMMENDATION_RANKING",
    "SCIENTIFIC_EXPERIMENT",
    "TIME_SERIES_FORECASTING",
    "WEB_AUTOMATION",
]
