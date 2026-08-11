"""Additional atomic templates for broadly reusable graph-shaped systems."""

from __future__ import annotations

from solutiongraph.template_authoring import build_reference_linear_template as _template

KNOWLEDGE_RETRIEVAL = _template(
    template_id="template.knowledge-retrieval",
    title="Grounded knowledge ingestion and retrieval",
    description="A source-governance, indexing, retrieval, grounding, and feedback scaffold.",
    domains=("ai.knowledge-systems", "data-engineering.documents"),
    tags=("retrieval", "grounding", "rag"),
    stages=(
        ("stage.contract", "Contract", "Bound the corpus and answer contract.", (
            ("define_corpus", "Define admitted sources, ownership, freshness, and access policy."),
            ("define_queries", "Define query classes, answer schema, and abstention behavior."),
            ("define_grounding_oracle", "Define citation, coverage, and unsupported-claim checks."),
        )),
        ("stage.ingest", "Ingest", "Create source-grounded units.", (
            ("acquire_sources", "Acquire immutable source snapshots with provenance."),
            ("decode_sources", "Decode text, layout, metadata, and structured regions."),
            ("segment_units", "Segment semantically coherent units with stable source spans."),
            ("enrich_units", "Add authorized metadata, entities, and topic descriptors."),
        )),
        ("stage.index", "Index", "Build independently replaceable indexes.", (
            ("select_representations", "Select lexical, dense, sparse, graph, or hybrid representations."),
            ("build_indexes", "Build content-addressed indexes under a declared version."),
            ("verify_index", "Verify coverage, freshness, access filtering, and retrievability."),
        )),
        ("stage.retrieve", "Retrieve", "Produce a bounded evidence set.", (
            ("rewrite_query", "Normalize or decompose the query without changing user intent."),
            ("retrieve_candidates", "Retrieve candidates through admitted index strategies."),
            ("rerank_evidence", "Rerank for relevance, diversity, permissions, and source quality."),
            ("assemble_context", "Assemble a token- and evidence-bounded context."),
        )),
        ("stage.answer", "Answer", "Generate and independently verify grounded output.", (
            ("produce_answer", "Produce the requested typed answer or abstention."),
            ("ground_claims", "Bind claims to exact source spans and evidence digests."),
            ("verify_answer", "Check entailment, completeness, policy, and citation validity."),
            ("record_feedback", "Record queries, outcomes, corrections, and index revision evidence."),
        )),
    ),
)


CLAIMS_PROCESSING = _template(
    template_id="template.claims-processing",
    title="Insurance and benefits claims processing",
    description="An intake, evidence, adjudication, exception, and settlement scaffold.",
    domains=("business.claims", "software.workflow"),
    tags=("adjudication", "documents", "human-review"),
    stages=(
        ("stage.intake", "Intake", "Identify and validate the claim package.", (
            ("receive_claim", "Receive a source-identified claim and attachments idempotently."),
            ("authenticate_claimant", "Authenticate authorized parties and consent scope."),
            ("validate_submission", "Validate required forms, dates, signatures, and schemas."),
        )),
        ("stage.evidence", "Evidence", "Build a traceable evidence record.", (
            ("extract_claim_facts", "Extract typed facts with exact document grounding."),
            ("retrieve_policy", "Retrieve the applicable policy and versioned coverage terms."),
            ("corroborate_evidence", "Corroborate providers, events, amounts, and prior claims."),
            ("detect_conflicts", "Identify missing, inconsistent, or potentially fraudulent evidence."),
        )),
        ("stage.adjudicate", "Adjudicate", "Apply rules and admitted decision models.", (
            ("determine_eligibility", "Evaluate eligibility and coverage prerequisites."),
            ("calculate_benefit", "Calculate covered amount, limits, deductibles, and coordination."),
            ("explain_decision", "Produce rule-level reasons and source evidence."),
        )),
        ("stage.review", "Review", "Resolve uncertainty and consequential exceptions.", (
            ("triage_exception", "Classify uncertainty, missing evidence, fraud, and policy exceptions."),
            ("request_information", "Request only the missing authorized information."),
            ("conduct_human_review", "Route consequential or ambiguous decisions for accountable review."),
        )),
        ("stage.settle", "Settle", "Execute and verify the approved outcome.", (
            ("authorize_settlement", "Authorize payment or denial under separation-of-duties policy."),
            ("execute_settlement", "Execute the frozen settlement with idempotency controls."),
            ("notify_parties", "Deliver privacy-safe decision and appeal information."),
            ("audit_claim", "Publish a replayable evidence, decision, and action receipt."),
        )),
    ),
)


FRAUD_RISK = _template(
    template_id="template.fraud-risk",
    title="Fraud detection and risk decisioning",
    description="A streaming/batch feature, detection, investigation, decision, and learning scaffold.",
    domains=("risk.fraud", "machine-learning.classification"),
    tags=("risk", "anomaly", "decisioning"),
    stages=(
        ("stage.observe", "Observe", "Create an event and identity contract.", (
            ("receive_event", "Receive the exact event with source and event-time identity."),
            ("resolve_identity", "Resolve account, device, merchant, and related entities."),
            ("validate_event", "Validate event schema, integrity, duplication, and lateness."),
        )),
        ("stage.features", "Features", "Produce leakage-safe risk evidence.", (
            ("retrieve_history", "Retrieve only causally available historical observations."),
            ("derive_velocity", "Derive time-windowed frequency and amount features."),
            ("derive_graph_features", "Derive relationship, community, and novelty features."),
            ("verify_feature_freshness", "Verify point-in-time correctness and feature freshness."),
        )),
        ("stage.detect", "Detect", "Combine diverse admitted detectors.", (
            ("apply_rules", "Apply versioned deterministic risk and compliance rules."),
            ("score_anomaly", "Measure deviation from peer and historical behavior."),
            ("score_model", "Apply a calibrated supervised or representation model."),
            ("combine_signals", "Combine signals with explicit missingness and confidence semantics."),
        )),
        ("stage.decide", "Decide", "Choose a proportionate action.", (
            ("estimate_consequence", "Estimate loss, customer harm, and intervention cost."),
            ("select_action", "Select allow, challenge, hold, block, or review under policy."),
            ("explain_risk", "Produce reviewable reasons without exposing protected controls."),
        )),
        ("stage.learn", "Learn", "Verify outcomes and update safely.", (
            ("observe_outcome", "Capture confirmed fraud, disputes, reviews, and false positives."),
            ("audit_bias", "Audit performance, drift, and disparate impact."),
            ("revise_beliefs", "Revise route priors without changing task or policy semantics."),
            ("publish_receipt", "Publish event, features, route, decision, and outcome provenance."),
        )),
    ),
)


CYBERSECURITY_INVESTIGATION = _template(
    template_id="template.cybersecurity-investigation",
    title="Defensive cybersecurity investigation",
    description="A scoped collection, enrichment, hypothesis, verification, and response scaffold.",
    domains=("security.defensive", "operations.investigation"),
    tags=("incident", "forensics", "threat-detection"),
    stages=(
        ("stage.scope", "Scope", "Establish defensive authority and preservation rules.", (
            ("authorize_investigation", "Record defensive scope, systems, time window, and approvals."),
            ("define_hypotheses", "Define testable benign and malicious hypotheses."),
            ("preserve_evidence", "Define evidence integrity, retention, and chain-of-custody controls."),
        )),
        ("stage.collect", "Collect", "Acquire relevant defensive telemetry.", (
            ("collect_events", "Collect admitted endpoint, identity, network, cloud, and application events."),
            ("normalize_events", "Normalize events while preserving raw source references."),
            ("order_timeline", "Order event-time observations and represent clock uncertainty."),
        )),
        ("stage.enrich", "Enrich", "Resolve context and relationships.", (
            ("resolve_assets", "Resolve devices, users, services, and ownership."),
            ("enrich_indicators", "Enrich indicators from admitted internal and external intelligence."),
            ("build_activity_graph", "Build entity, process, network, and credential relationships."),
            ("baseline_behavior", "Compare activity to asset- and role-specific baselines."),
        )),
        ("stage.analyze", "Analyze", "Test hypotheses with independent checks.", (
            ("detect_techniques", "Map supported observations to versioned defensive technique taxonomies."),
            ("correlate_evidence", "Correlate temporally and causally related observations."),
            ("test_hypotheses", "Seek confirming and disconfirming evidence for each hypothesis."),
            ("estimate_confidence", "Estimate confidence, impact, and remaining uncertainty."),
        )),
        ("stage.respond", "Respond", "Contain safely and preserve learning.", (
            ("select_response", "Select proportionate reversible defensive actions."),
            ("execute_containment", "Execute authorized containment with rollback and blast-radius controls."),
            ("verify_recovery", "Verify eradication, recovery, and absence of recurrence signals."),
            ("publish_case", "Publish findings, evidence, actions, and lessons with access controls."),
        )),
    ),
)


COMPLIANCE_EVIDENCE = _template(
    template_id="template.compliance-evidence",
    title="Compliance control evidence",
    description="A requirement mapping, evidence collection, testing, exception, and attestation scaffold.",
    domains=("governance.compliance", "software.assurance"),
    tags=("controls", "audit", "evidence"),
    stages=(
        ("stage.map", "Map", "Translate obligations into testable controls.", (
            ("load_requirements", "Load authoritative requirement versions and applicability."),
            ("map_controls", "Map requirements to owners, systems, controls, and evidence expectations."),
            ("define_tests", "Define independent design and operating-effectiveness tests."),
        )),
        ("stage.collect", "Collect", "Acquire immutable control evidence.", (
            ("request_evidence", "Request minimally sufficient evidence from authorized systems and owners."),
            ("authenticate_evidence", "Verify evidence source, time range, completeness, and integrity."),
            ("normalize_evidence", "Normalize evidence into typed control observations."),
        )),
        ("stage.test", "Test", "Evaluate controls reproducibly.", (
            ("test_design", "Test whether control design addresses the mapped obligation."),
            ("sample_operation", "Select reproducible, bias-aware operating samples."),
            ("test_operation", "Test observed operation against exact control criteria."),
            ("cross_check_findings", "Cross-check material findings through an independent source or method."),
        )),
        ("stage.resolve", "Resolve", "Manage failures without rewriting evidence.", (
            ("classify_exception", "Classify severity, scope, recurrence, and compensating controls."),
            ("assign_remediation", "Assign accountable remediation, deadline, and verification plan."),
            ("verify_remediation", "Verify the changed control on new evidence."),
        )),
        ("stage.attest", "Attest", "Publish bounded conclusions.", (
            ("aggregate_control_status", "Aggregate findings without hiding population or sample limits."),
            ("review_attestation", "Require accountable review for material conclusions."),
            ("publish_evidence_pack", "Publish requirements, evidence, tests, exceptions, and signed receipts."),
        )),
    ),
)


GEOSPATIAL_ANALYTICS = _template(
    template_id="template.geospatial-analytics",
    title="Geospatial data integration and analysis",
    description="A coordinate, topology, enrichment, analysis, and map-product scaffold.",
    domains=("data.geospatial", "analytics.spatial"),
    tags=("gis", "coordinates", "spatial-analysis"),
    stages=(
        ("stage.ingest", "Ingest", "Identify spatial sources and reference systems.", (
            ("load_spatial_sources", "Load geometry, raster, tabular, and temporal sources by digest."),
            ("detect_crs", "Detect or require coordinate reference systems and axis order."),
            ("validate_geometry", "Validate geometry encoding, bounds, and dimensionality."),
        )),
        ("stage.normalize", "Normalize", "Create compatible spatial representations.", (
            ("repair_geometry", "Repair or quarantine invalid geometry under a declared policy."),
            ("transform_crs", "Transform coordinates with an exact operation and datum provenance."),
            ("normalize_resolution", "Normalize raster resolution, extent, and nodata semantics."),
            ("index_space", "Build admitted spatial indexes or tiling structures."),
        )),
        ("stage.integrate", "Integrate", "Relate sources with loss accounting.", (
            ("geocode_entities", "Resolve entities to locations with candidates and confidence."),
            ("spatial_join", "Join by an explicit predicate, tolerance, and multiplicity contract."),
            ("reconcile_boundaries", "Reconcile administrative or temporal boundary versions."),
        )),
        ("stage.analyze", "Analyze", "Compute spatial evidence.", (
            ("derive_spatial_features", "Derive distance, density, adjacency, accessibility, and terrain features."),
            ("run_spatial_model", "Run admitted interpolation, clustering, routing, or prediction methods."),
            ("quantify_uncertainty", "Quantify coordinate, boundary, sampling, and model uncertainty."),
        )),
        ("stage.publish", "Publish", "Verify and publish reusable products.", (
            ("verify_spatial_output", "Verify CRS, geometry, coverage, topology, and numerical invariants."),
            ("render_map_product", "Render accessible map or tile products under a declared style."),
            ("publish_spatial_data", "Publish versioned data, metadata, rejects, and lineage."),
        )),
    ),
)


AUDIO_SPEECH = _template(
    template_id="template.audio-speech",
    title="Audio and speech processing",
    description="An audio decode, enhancement, segmentation, recognition, and assurance scaffold.",
    domains=("media.audio", "ai.speech"),
    tags=("audio", "speech", "transcription"),
    stages=(
        ("stage.ingest", "Ingest", "Decode and identify exact audio content.", (
            ("load_audio", "Load exact audio bytes and source metadata."),
            ("decode_audio", "Decode channels, sample format, rate, duration, and container."),
            ("validate_audio", "Detect truncation, clipping, silence, and unsupported structure."),
        )),
        ("stage.prepare", "Prepare", "Produce analysis-ready signals.", (
            ("normalize_channels", "Select, mix, or preserve channels under an explicit policy."),
            ("resample_audio", "Resample with declared filter and rate provenance."),
            ("enhance_audio", "Denoise, dereverberate, or level audio without hiding transformations."),
        )),
        ("stage.segment", "Segment", "Identify meaningful temporal regions.", (
            ("detect_activity", "Detect speech, music, silence, and relevant sound activity."),
            ("segment_speakers", "Segment and cluster speakers with uncertainty."),
            ("align_timestamps", "Establish stable segment and word time boundaries."),
        )),
        ("stage.interpret", "Interpret", "Produce typed content observations.", (
            ("transcribe_speech", "Transcribe speech with language and token confidence."),
            ("classify_audio", "Classify requested acoustic events or properties."),
            ("extract_audio_features", "Extract admitted spectral, prosodic, or embedding features."),
            ("reconcile_transcripts", "Reconcile model candidates against timestamps and dictionaries."),
        )),
        ("stage.deliver", "Deliver", "Verify and publish temporal evidence.", (
            ("verify_transcript", "Check alignment, terminology, formatting, and sampled accuracy."),
            ("apply_redaction", "Apply policy-bound audio and transcript redaction."),
            ("publish_audio_report", "Publish outputs, segments, confidence, and transformation receipts."),
        )),
    ),
)


SUPPLY_CHAIN_PLANNING = _template(
    template_id="template.supply-chain-planning",
    title="Supply-chain planning and fulfillment",
    description="A demand, inventory, network, plan, execution, and replanning scaffold.",
    domains=("operations.supply-chain", "optimization.planning"),
    tags=("inventory", "forecasting", "planning"),
    stages=(
        ("stage.state", "State", "Build a trustworthy planning state.", (
            ("ingest_demand", "Ingest orders, forecasts, promotions, and causal demand signals."),
            ("ingest_supply", "Ingest inventory, capacity, lead time, purchase, and production state."),
            ("reconcile_state", "Reconcile units, calendars, locations, products, and stale observations."),
        )),
        ("stage.predict", "Predict", "Represent uncertain future conditions.", (
            ("forecast_demand", "Forecast demand distributions at the required hierarchy and horizon."),
            ("forecast_lead_time", "Forecast supplier, production, and transport lead-time distributions."),
            ("generate_scenarios", "Generate coherent demand, disruption, and capacity scenarios."),
        )),
        ("stage.optimize", "Optimize", "Generate feasible candidate plans.", (
            ("formulate_constraints", "Formulate service, capacity, flow, policy, and integrality constraints."),
            ("optimize_inventory", "Optimize safety stock, reorder, allocation, and substitution decisions."),
            ("optimize_network", "Optimize sourcing, production, routing, and fulfillment choices."),
            ("stress_plan", "Stress candidate plans across declared scenarios."),
        )),
        ("stage.decide", "Decide", "Select an accountable plan.", (
            ("compare_plans", "Compare cost, service, resilience, emissions, and execution risk."),
            ("resolve_exceptions", "Resolve infeasibility, shortages, and policy exceptions."),
            ("approve_plan", "Freeze the selected plan and accountable approvals."),
        )),
        ("stage.execute", "Execute", "Dispatch, observe, and replan.", (
            ("dispatch_orders", "Dispatch exact procurement, transfer, production, and fulfillment actions."),
            ("observe_execution", "Observe acknowledgements, deviations, and downstream state changes."),
            ("verify_outcomes", "Verify service, cost, inventory, and constraint outcomes."),
            ("trigger_replan", "Trigger bounded replanning from material state changes."),
        )),
    ),
)


OPTIMIZATION_SCHEDULING = _template(
    template_id="template.optimization-scheduling",
    title="Constraint optimization and scheduling",
    description="A formalization, decomposition, solve, verify, and operationalization scaffold.",
    domains=("optimization.operations-research", "software.scheduling"),
    tags=("constraints", "solver", "scheduling"),
    stages=(
        ("stage.formalize", "Formalize", "Create an exact decision model.", (
            ("define_variables", "Define decision variables, domains, indices, and units."),
            ("define_constraints", "Define hard constraints separately from preferences."),
            ("define_objectives", "Define ordered or weighted objectives and acceptable gaps."),
            ("validate_instance", "Validate data, bounds, feasibility prerequisites, and scale."),
        )),
        ("stage.transform", "Transform", "Generate equivalent admitted formulations.", (
            ("presolve_model", "Eliminate fixed variables and redundant constraints with a receipt."),
            ("decompose_problem", "Decompose by time, geography, resource, scenario, or coupling structure."),
            ("select_formulation", "Select alternative exact or approximate formulations."),
        )),
        ("stage.solve", "Solve", "Explore solver and parameter candidates.", (
            ("select_solver", "Select an admitted CP, LP, MILP, SAT, heuristic, or hybrid solver."),
            ("construct_incumbent", "Construct an initial feasible incumbent when useful."),
            ("run_search", "Run bounded optimization with checkpoints and solver evidence."),
            ("refine_solution", "Apply local search, repair, polishing, or decomposition iterations."),
        )),
        ("stage.verify", "Verify", "Establish feasibility and claim limits.", (
            ("verify_feasibility", "Independently check every hard constraint on the emitted solution."),
            ("recompute_objectives", "Recompute objective values outside the producing solver."),
            ("verify_bound", "Verify optimality gap or explicitly label heuristic-only status."),
        )),
        ("stage.deploy", "Deploy", "Turn a solution into safe operations.", (
            ("explain_schedule", "Explain assignments, binding constraints, and major tradeoffs."),
            ("publish_schedule", "Publish versioned decisions with stable entity identities."),
            ("monitor_deviation", "Monitor execution deviations and determine bounded repair versus re-solve."),
        )),
    ),
)


DATABASE_MIGRATION = _template(
    template_id="template.database-migration",
    title="Database migration and change-data capture",
    description="A schema, backfill, dual-run, cutover, and rollback scaffold.",
    domains=("data.database", "software.migration"),
    tags=("migration", "cdc", "reconciliation"),
    stages=(
        ("stage.assess", "Assess", "Define source, target, and compatibility contracts.", (
            ("inventory_schema", "Inventory schemas, constraints, volumes, dependencies, and workloads."),
            ("map_schema", "Map source to target types, semantics, keys, and unsupported constructs."),
            ("define_cutover_slo", "Define correctness, downtime, performance, rollback, and retention limits."),
        )),
        ("stage.prepare", "Prepare", "Create target structures and transformations.", (
            ("create_target_schema", "Create versioned target schema and constraints safely."),
            ("build_transformations", "Build explicit data and type transformations with rejects."),
            ("configure_change_capture", "Configure ordered, resumable change capture with source offsets."),
        )),
        ("stage.move", "Move", "Backfill and replicate without losing mutations.", (
            ("snapshot_source", "Establish a consistent source snapshot and starting offset."),
            ("backfill_data", "Backfill bounded partitions with checksums and checkpoints."),
            ("apply_changes", "Apply captured changes idempotently in source order."),
            ("handle_schema_drift", "Handle source schema changes under an explicit compatibility policy."),
        )),
        ("stage.verify", "Verify", "Compare source and target independently.", (
            ("reconcile_counts", "Reconcile counts, keys, partitions, and reject populations."),
            ("reconcile_values", "Compare checksums, sampled rows, aggregates, and invariants."),
            ("shadow_workload", "Replay or shadow representative reads and writes."),
            ("verify_lag", "Verify replication lag and offset completeness."),
        )),
        ("stage.cutover", "Cut over", "Switch traffic reversibly.", (
            ("freeze_cutover_plan", "Freeze traffic, ownership, communication, and rollback steps."),
            ("switch_traffic", "Switch bounded traffic through observable gates."),
            ("verify_cutover", "Verify correctness, performance, and downstream consumers."),
            ("retire_or_rollback", "Rollback or retire the source only under the declared policy."),
        )),
    ),
)


OBSERVABILITY_SRE = _template(
    template_id="template.observability-sre",
    title="Observability and SRE response",
    description="A telemetry, detection, diagnosis, mitigation, and learning scaffold.",
    domains=("operations.sre", "software.observability"),
    tags=("telemetry", "reliability", "incident"),
    stages=(
        ("stage.instrument", "Instrument", "Define observable service contracts.", (
            ("define_service_model", "Define services, dependencies, owners, critical paths, and user journeys."),
            ("define_slos", "Define indicators, objectives, error budgets, and measurement windows."),
            ("instrument_telemetry", "Instrument metrics, logs, traces, profiles, and events with privacy controls."),
        )),
        ("stage.collect", "Collect", "Create trustworthy telemetry streams.", (
            ("ingest_telemetry", "Ingest typed telemetry with event-time, source, and sampling metadata."),
            ("normalize_telemetry", "Normalize resource, service, trace, and error identities."),
            ("verify_telemetry", "Verify completeness, freshness, cardinality, and pipeline health."),
        )),
        ("stage.detect", "Detect", "Identify actionable service degradation.", (
            ("evaluate_slos", "Evaluate SLO windows and error-budget consumption."),
            ("detect_anomalies", "Detect changes relative to service-appropriate baselines."),
            ("correlate_alerts", "Correlate symptoms by topology, time, deployment, and causality."),
        )),
        ("stage.respond", "Respond", "Diagnose and mitigate safely.", (
            ("triage_incident", "Estimate impact, urgency, ownership, and affected users."),
            ("diagnose_cause", "Test causal hypotheses using cross-signal evidence."),
            ("select_mitigation", "Select reversible mitigation under blast-radius controls."),
            ("verify_recovery", "Verify SLO recovery and absence of hidden degradation."),
        )),
        ("stage.learn", "Learn", "Improve system and response quality.", (
            ("reconstruct_timeline", "Reconstruct a source-grounded incident timeline."),
            ("identify_actions", "Identify systemic prevention, detection, and response improvements."),
            ("verify_actions", "Verify completed actions against the original failure mode."),
            ("revise_routing", "Revise alert and mitigation route priors from observed outcomes."),
        )),
    ),
)


CONTENT_MODERATION = _template(
    template_id="template.content-moderation",
    title="Content moderation and policy enforcement",
    description="A policy, perception, classification, decision, review, and appeal scaffold.",
    domains=("trust-safety.moderation", "ai.classification"),
    tags=("policy", "safety", "human-review"),
    stages=(
        ("stage.policy", "Policy", "Bind content to an exact policy context.", (
            ("identify_context", "Identify surface, audience, jurisdiction, age, and product context."),
            ("load_policy", "Load the applicable policy version, thresholds, and exceptions."),
            ("define_harm_oracle", "Define category, severity, context, and appeal evaluation criteria."),
        )),
        ("stage.perceive", "Perceive", "Extract relevant multimodal evidence.", (
            ("decode_content", "Decode text, image, audio, video, metadata, and conversational context."),
            ("detect_language", "Detect language, dialect, code-switching, and obfuscation."),
            ("extract_signals", "Extract policy-relevant entities, spans, regions, audio, and relationships."),
        )),
        ("stage.classify", "Classify", "Apply diverse policy detectors.", (
            ("apply_rules", "Apply deterministic hashes, lists, syntax, and context rules."),
            ("apply_models", "Apply admitted calibrated content and context models."),
            ("cross_check_signals", "Cross-check conflicting modalities and detector families."),
            ("estimate_uncertainty", "Estimate category, severity, and contextual uncertainty."),
        )),
        ("stage.decide", "Decide", "Select a proportionate policy action.", (
            ("apply_policy", "Map evidence to policy categories and exceptions."),
            ("select_action", "Select allow, label, limit, remove, report, or review."),
            ("generate_reason", "Generate a policy-grounded reason and user-safe explanation."),
        )),
        ("stage.review", "Review", "Preserve accountability and learning.", (
            ("route_human_review", "Route uncertain or consequential cases to trained reviewers."),
            ("process_appeal", "Process appeals against preserved policy and evidence versions."),
            ("audit_performance", "Audit accuracy, calibration, drift, consistency, and disparate errors."),
            ("publish_receipt", "Publish access-controlled evidence, route, policy, action, and review receipts."),
        )),
    ),
)


MARKET_TEMPLATES = (
    AUDIO_SPEECH,
    CLAIMS_PROCESSING,
    COMPLIANCE_EVIDENCE,
    CONTENT_MODERATION,
    CYBERSECURITY_INVESTIGATION,
    DATABASE_MIGRATION,
    FRAUD_RISK,
    GEOSPATIAL_ANALYTICS,
    KNOWLEDGE_RETRIEVAL,
    OBSERVABILITY_SRE,
    OPTIMIZATION_SCHEDULING,
    SUPPLY_CHAIN_PLANNING,
)


__all__ = [
    "AUDIO_SPEECH",
    "CLAIMS_PROCESSING",
    "COMPLIANCE_EVIDENCE",
    "CONTENT_MODERATION",
    "CYBERSECURITY_INVESTIGATION",
    "DATABASE_MIGRATION",
    "FRAUD_RISK",
    "GEOSPATIAL_ANALYTICS",
    "KNOWLEDGE_RETRIEVAL",
    "MARKET_TEMPLATES",
    "OBSERVABILITY_SRE",
    "OPTIMIZATION_SCHEDULING",
    "SUPPLY_CHAIN_PLANNING",
]
