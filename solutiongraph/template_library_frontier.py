"""Frontier-domain templates for modalities, simulation, safety, and human systems.

These templates describe reusable semantic obligations.  Engine, provider,
model, library, and device choices belong in candidates and runtime adapters,
never in the template stages themselves.
"""

from __future__ import annotations

from solutiongraph.template_authoring import build_reference_linear_template as _template

LLM_EVALUATION_HARNESS = _template(
    template_id="template.llm-evaluation-harness",
    title="Independent LLM and agent evaluation harness",
    description=(
        "A scenario, oracle, blinded execution, adjudication, red-team, failure-learning, "
        "and sealed-promotion scaffold with explicit feedback firewalls."
    ),
    domains=("ai.llm-evaluation", "trust-safety.assurance"),
    tags=("llm-evaluation", "agent-evaluation", "red-team", "sealed-holdout"),
    stages=(
        (
            "stage.contract",
            "Contract",
            "Freeze evaluation meaning and authority.",
            (
                (
                    "define_system_boundary",
                    "Bind the exact system, model, prompt, tools, authority, and environment under evaluation.",
                ),
                (
                    "define_criteria",
                    "Define atomic criteria, slice definitions, hard gates, and objective metrics.",
                ),
                (
                    "define_oracles",
                    "Identify deterministic, model, panel, human, and external oracles independently of the producer.",
                ),
                (
                    "freeze_feedback_boundary",
                    "Separate development feedback, promotion evidence, and candidate-unreadable outer evaluation.",
                ),
            ),
        ),
        (
            "stage.scenarios",
            "Scenarios",
            "Create a traceable, diverse evaluation surface.",
            (
                (
                    "acquire_scenarios",
                    "Acquire versioned normal, boundary, multilingual, long-context, and tool-use scenarios.",
                ),
                (
                    "generate_adversarial_scenarios",
                    "Generate lineage-bound adversarial variants without exposing sealed cases.",
                ),
                (
                    "deduplicate_scenarios",
                    "Detect semantic duplicates, contamination, and family overlap.",
                ),
                (
                    "partition_scenarios",
                    "Create development, validation, stress, and sealed partitions with family isolation.",
                ),
            ),
        ),
        (
            "stage.execute",
            "Execute",
            "Run comparable systems under controlled conditions.",
            (
                (
                    "allocate_cells",
                    "Allocate compatible system, harness, model, scenario, seed, and repetition cells.",
                ),
                (
                    "invoke_system",
                    "Invoke the frozen system while recording prompts, tools, effects, outputs, cost, and latency.",
                ),
                (
                    "validate_outputs",
                    "Validate structured outputs, citations, tool traces, refusals, and declared invariants.",
                ),
            ),
        ),
        (
            "stage.judge",
            "Judge",
            "Produce criterion-level evidence and accountable disagreement.",
            (
                (
                    "apply_deterministic_oracles",
                    "Apply exact, property, policy, and source-grounding checks first.",
                ),
                (
                    "apply_independent_judges",
                    "Run blinded independent judges with exact identities and calibration evidence.",
                ),
                (
                    "adjudicate_disagreement",
                    "Route material disagreement and sampled judgments to accountable human review.",
                ),
                (
                    "calibrate_judges",
                    "Measure agreement, bias, sensitivity, specificity, and correlated judge failure.",
                ),
            ),
        ),
        (
            "stage.improve",
            "Improve",
            "Learn from development failures without contaminating promotion.",
            (
                (
                    "cluster_failures",
                    "Cluster failures by criterion, scenario family, cause, and severity while retaining atomic evidence.",
                ),
                (
                    "propose_improvements",
                    "Propose bounded system, prompt, tool, data, or topology changes outside the evaluator.",
                ),
                (
                    "build_regression_suite",
                    "Promote sanitized failure families into lineage-bound regression scenarios.",
                ),
            ),
        ),
        (
            "stage.promote",
            "Promote",
            "Make a bounded evidence-backed release decision.",
            (
                (
                    "run_sealed_evaluation",
                    "Evaluate the frozen shortlist on candidate-unreadable cases and evaluator infrastructure.",
                ),
                (
                    "compare_pareto_front",
                    "Compare quality, safety, calibration, cost, latency, reliability, and policy without hiding tradeoffs.",
                ),
                (
                    "approve_promotion",
                    "Require declared accountable approval and preserve rollback identity.",
                ),
                (
                    "publish_evaluation_receipt",
                    "Publish criteria, panels, failures, aggregate outer evidence, limitations, and exact identities.",
                ),
            ),
        ),
    ),
)


VIDEO_MEDIA_PIPELINE = _template(
    template_id="template.video-media-pipeline",
    title="Video and multimodal media pipeline",
    description="A source, timeline, transformation, interpretation, assurance, and publication scaffold.",
    domains=("media.video", "media.multimodal"),
    tags=("video", "audio", "captions", "transcoding", "media-assurance"),
    stages=(
        (
            "stage.ingest",
            "Ingest",
            "Identify and decode exact media assets.",
            (
                ("load_media", "Load source bytes, sidecars, rights, and provenance by digest."),
                (
                    "probe_streams",
                    "Identify containers, codecs, tracks, durations, rates, channels, and color metadata.",
                ),
                (
                    "validate_integrity",
                    "Detect truncation, corrupt packets, missing tracks, and unsupported structure.",
                ),
            ),
        ),
        (
            "stage.timeline",
            "Timeline",
            "Create a coherent audiovisual timeline.",
            (
                (
                    "normalize_timestamps",
                    "Normalize presentation and decode timestamps under an explicit time base.",
                ),
                (
                    "segment_scenes",
                    "Segment scenes, shots, speech, music, silence, and requested events.",
                ),
                (
                    "align_modalities",
                    "Align video, audio, captions, metadata, and externally supplied events.",
                ),
            ),
        ),
        (
            "stage.transform",
            "Transform",
            "Produce declared media variants.",
            (
                (
                    "select_regions",
                    "Select or assemble source-grounded clips under editorial constraints.",
                ),
                (
                    "transform_picture",
                    "Crop, resize, stabilize, grade, or reframe while recording every transformation.",
                ),
                (
                    "transform_audio",
                    "Mix, denoise, level, or separate audio under a declared policy.",
                ),
                (
                    "encode_variants",
                    "Encode exact delivery variants with content and configuration identity.",
                ),
            ),
        ),
        (
            "stage.interpret",
            "Interpret",
            "Generate typed multimodal observations.",
            (
                (
                    "transcribe_speech",
                    "Transcribe and time-align speech with language and confidence.",
                ),
                (
                    "describe_visuals",
                    "Detect requested objects, text, actions, scenes, and visual properties.",
                ),
                (
                    "author_captions",
                    "Create, translate, and format accessible captions or subtitles.",
                ),
            ),
        ),
        (
            "stage.assure",
            "Assure",
            "Independently verify media quality and policy.",
            (
                ("verify_sync", "Measure audiovisual and caption synchronization."),
                (
                    "verify_quality",
                    "Measure picture, audio, continuity, and encoding quality against fixed references or properties.",
                ),
                (
                    "verify_safety_rights",
                    "Check declared content policy, privacy, licensing, and release constraints.",
                ),
                (
                    "publish_media",
                    "Publish variants, manifests, rejects, measurements, and provenance receipts.",
                ),
            ),
        ),
    ),
)


THREE_D_ASSET_PIPELINE = _template(
    template_id="template.three-d-asset-pipeline",
    title="3D asset validation and optimization",
    description="A geometry, material, collision, optimization, rendering, and export scaffold.",
    domains=("media.three-d", "simulation.assets"),
    tags=("three-d", "mesh", "materials", "lod", "rendering"),
    stages=(
        (
            "stage.ingest",
            "Ingest",
            "Decode spatial assets with exact coordinate semantics.",
            (
                (
                    "load_assets",
                    "Load meshes, scenes, materials, textures, skeletons, and metadata by digest.",
                ),
                (
                    "detect_coordinate_system",
                    "Identify handedness, axes, units, transforms, and scene hierarchy.",
                ),
                (
                    "normalize_formats",
                    "Convert formats only through explicit typed adapters with loss accounting.",
                ),
            ),
        ),
        (
            "stage.geometry",
            "Geometry",
            "Validate and repair geometric structure.",
            (
                (
                    "validate_topology",
                    "Detect non-manifold edges, holes, degenerates, inverted normals, and disconnected components.",
                ),
                (
                    "repair_geometry",
                    "Apply bounded reversible repairs and quarantine unresolved defects.",
                ),
                ("validate_uvs", "Validate UV coverage, overlap policy, seams, and texel density."),
            ),
        ),
        (
            "stage.scene",
            "Scene",
            "Validate appearance and interaction contracts.",
            (
                (
                    "validate_materials",
                    "Resolve material and texture references, channels, color spaces, and licenses.",
                ),
                (
                    "validate_rigging",
                    "Validate skeleton hierarchy, weights, animations, and deformation invariants.",
                ),
                (
                    "validate_collisions",
                    "Validate collision geometry, layers, bounds, and intended physical semantics.",
                ),
            ),
        ),
        (
            "stage.optimize",
            "Optimize",
            "Meet explicit runtime and visual budgets.",
            (
                (
                    "generate_lods",
                    "Generate or validate level-of-detail variants with visual-error evidence.",
                ),
                (
                    "optimize_geometry",
                    "Reduce geometry and draw overhead without violating declared shape tolerances.",
                ),
                (
                    "optimize_textures",
                    "Resize, pack, compress, and stream textures under memory and quality budgets.",
                ),
            ),
        ),
        (
            "stage.verify",
            "Verify",
            "Render, simulate, and export independently checked assets.",
            (
                (
                    "render_regression",
                    "Render fixed cameras and compare silhouettes, materials, lighting, and artifacts.",
                ),
                (
                    "profile_asset",
                    "Measure triangles, draw calls, memory, load time, and representative frame cost.",
                ),
                (
                    "export_asset",
                    "Export versioned bundles and verify round-trip structure and references.",
                ),
                (
                    "publish_asset_receipt",
                    "Publish defects, repairs, budgets, renders, exports, and source lineage.",
                ),
            ),
        ),
    ),
)


GAME_BUILD_PLAYTEST = _template(
    template_id="template.game-build-playtest",
    title="Game build, simulation, and playtest assurance",
    description="A rules, content, deterministic simulation, automated playtest, quality, and release scaffold.",
    domains=("software.games", "simulation.interactive"),
    tags=("game", "playtest", "replay", "balance", "release"),
    stages=(
        (
            "stage.contract",
            "Contract",
            "Define player-visible rules and release criteria.",
            (
                (
                    "define_game_state",
                    "Define versioned state, actions, transitions, persistence, and networking semantics.",
                ),
                (
                    "define_invariants",
                    "Define rule, economy, progression, fairness, accessibility, and safety invariants.",
                ),
                (
                    "define_playtest_oracles",
                    "Define deterministic, statistical, performance, accessibility, and human playtest oracles.",
                ),
            ),
        ),
        (
            "stage.build",
            "Build",
            "Create reproducible game and content artifacts.",
            (
                (
                    "assemble_content",
                    "Resolve code, levels, assets, localization, configuration, and rights.",
                ),
                (
                    "build_targets",
                    "Build declared platform targets with dependency and environment identity.",
                ),
                (
                    "validate_save_migrations",
                    "Validate save, replay, schema, and content-version migrations.",
                ),
            ),
        ),
        (
            "stage.simulate",
            "Simulate",
            "Exercise rules and state transitions reproducibly.",
            (
                (
                    "run_deterministic_replays",
                    "Replay fixed actions and verify state hashes, outcomes, and desynchronization.",
                ),
                (
                    "run_agent_playtests",
                    "Run bounded bots or policies across levels, roles, and difficulty slices.",
                ),
                (
                    "simulate_economy",
                    "Simulate rewards, sinks, progression, matchmaking, and exploit pressure.",
                ),
                (
                    "generate_edge_cases",
                    "Generate reachable boundary and adversarial state sequences with lineage.",
                ),
            ),
        ),
        (
            "stage.assure",
            "Assure",
            "Evaluate functional and experiential constraints.",
            (
                (
                    "run_regression_tests",
                    "Run functional, integration, multiplayer, save, and content regression suites.",
                ),
                (
                    "profile_runtime",
                    "Measure frame time, input latency, memory, loading, network, and crash behavior.",
                ),
                (
                    "audit_balance",
                    "Measure outcome distributions, matchup fairness, economy stability, and exploit rates.",
                ),
                (
                    "audit_accessibility",
                    "Evaluate controls, presentation, assistive support, and documented accessibility criteria.",
                ),
                (
                    "conduct_human_playtest",
                    "Collect structured human evidence for subjective qualities that automation cannot establish.",
                ),
            ),
        ),
        (
            "stage.release",
            "Release",
            "Gate and monitor a reversible release.",
            (
                (
                    "compare_builds",
                    "Compare control and candidate builds on identical tests, replays, devices, and seeds.",
                ),
                (
                    "approve_release",
                    "Apply hard gates and accountable human approval for the declared target.",
                ),
                (
                    "monitor_telemetry",
                    "Monitor crashes, performance, progression, economy, safety, and player-impact slices.",
                ),
                (
                    "prepare_rollback",
                    "Preserve a tested rollback target and compatible state migration path.",
                ),
            ),
        ),
    ),
)


ROBOTICS_CONTROL = _template(
    template_id="template.robotics-control",
    title="Robotics planning and control assurance",
    description="A model, perception, planning, simulation, safety, deployment, and monitoring scaffold.",
    domains=("robotics.control", "simulation.physical"),
    tags=("robotics", "planning", "control", "safety", "simulation"),
    stages=(
        (
            "stage.contract",
            "Contract",
            "Bound the robot, environment, task, and safety authority.",
            (
                (
                    "define_robot_model",
                    "Define kinematics, dynamics, limits, sensors, actuators, frames, and calibration.",
                ),
                (
                    "define_environment",
                    "Define operating domain, obstacles, uncertainty, humans, and prohibited regions.",
                ),
                (
                    "define_safety_envelope",
                    "Define independent collision, force, speed, fail-safe, and human-approval criteria.",
                ),
            ),
        ),
        (
            "stage.perceive",
            "Perceive",
            "Construct a time-bounded world estimate.",
            (
                (
                    "ingest_sensors",
                    "Ingest synchronized sensor observations with calibration and event-time provenance.",
                ),
                ("estimate_state", "Estimate robot and environment state with uncertainty."),
                (
                    "detect_hazards",
                    "Detect obstacles, people, degraded sensors, and out-of-distribution conditions.",
                ),
            ),
        ),
        (
            "stage.plan",
            "Plan",
            "Produce a feasible bounded action plan.",
            (
                ("generate_plans", "Generate candidate task, motion, and recovery plans."),
                (
                    "check_feasibility",
                    "Check kinematic, dynamic, collision, timing, energy, and authority constraints.",
                ),
                (
                    "select_plan",
                    "Select an eligible plan across safety, quality, robustness, and resource objectives.",
                ),
            ),
        ),
        (
            "stage.validate",
            "Validate",
            "Test the plan before physical effects.",
            (
                (
                    "simulate_plan",
                    "Simulate nominal, perturbation, sensor-failure, and interruption scenarios.",
                ),
                (
                    "verify_safety",
                    "Apply an independent safety monitor or formally bounded property check where available.",
                ),
                (
                    "approve_execution",
                    "Require declared human or system approval for consequential physical effects.",
                ),
            ),
        ),
        (
            "stage.execute",
            "Execute",
            "Run through an enforcing controller and preserve evidence.",
            (
                (
                    "execute_plan",
                    "Execute through a bounded controller with emergency-stop and idempotency semantics.",
                ),
                (
                    "monitor_execution",
                    "Monitor state divergence, hazards, limits, progress, and stop conditions.",
                ),
                (
                    "recover_safely",
                    "Enter a verified safe state or bounded recovery behavior after failure.",
                ),
                (
                    "publish_run_receipt",
                    "Publish model, plan, simulation, approvals, telemetry, interventions, and outcomes.",
                ),
            ),
        ),
    ),
)


DIGITAL_TWIN_SIMULATION = _template(
    template_id="template.digital-twin-simulation",
    title="Digital twin calibration and decision support",
    description="A system-identity, data assimilation, calibration, simulation, validation, and decision scaffold.",
    domains=("simulation.digital-twin", "science.modeling"),
    tags=("digital-twin", "simulation", "calibration", "sensitivity"),
    stages=(
        (
            "stage.scope",
            "Scope",
            "Bind the real system and model claim.",
            (
                (
                    "identify_system",
                    "Identify assets, boundaries, topology, versions, operating modes, and ownership.",
                ),
                (
                    "define_model_claim",
                    "Define which observables and decisions the twin is permitted to represent.",
                ),
                (
                    "define_validation",
                    "Define calibration, validation, extrapolation, uncertainty, and decision oracles.",
                ),
            ),
        ),
        (
            "stage.assimilate",
            "Assimilate",
            "Create a trustworthy state estimate.",
            (
                (
                    "ingest_observations",
                    "Ingest aligned sensor, event, maintenance, and environmental observations.",
                ),
                (
                    "reconcile_state",
                    "Resolve conflicting observations, missingness, latency, and uncertainty.",
                ),
                ("estimate_parameters", "Estimate model parameters on calibration-only evidence."),
            ),
        ),
        (
            "stage.simulate",
            "Simulate",
            "Run declared scenarios and alternatives.",
            (
                (
                    "generate_scenarios",
                    "Generate nominal, stress, intervention, and counterfactual scenarios.",
                ),
                (
                    "execute_simulation",
                    "Execute the exact model and solver under recorded initial and boundary conditions.",
                ),
                (
                    "quantify_uncertainty",
                    "Propagate parameter, measurement, structural, and stochastic uncertainty.",
                ),
                (
                    "analyze_sensitivity",
                    "Measure output sensitivity and identify fragile assumptions.",
                ),
            ),
        ),
        (
            "stage.validate",
            "Validate",
            "Test fidelity and decision usefulness.",
            (
                (
                    "compare_observations",
                    "Compare untouched observations with simulated values across regimes and slices.",
                ),
                (
                    "diagnose_residuals",
                    "Diagnose bias, drift, autocorrelation, regime failure, and unmodeled effects.",
                ),
                (
                    "bound_applicability",
                    "Declare validated regions, abstention conditions, and extrapolation limits.",
                ),
            ),
        ),
        (
            "stage.decide",
            "Decide",
            "Use the twin without overstating authority.",
            (
                (
                    "compare_interventions",
                    "Compare eligible interventions across outcomes, uncertainty, cost, and risk.",
                ),
                (
                    "require_decision_review",
                    "Require accountable review for consequential recommendations.",
                ),
                (
                    "publish_twin_receipt",
                    "Publish data, model, calibration, scenarios, validation, recommendation, and limitations.",
                ),
            ),
        ),
    ),
)


EMBEDDED_IOT_SYSTEM = _template(
    template_id="template.embedded-iot-system",
    title="Embedded and IoT telemetry system",
    description="A device contract, firmware, telemetry, state, command, assurance, and fleet-operations scaffold.",
    domains=("software.embedded", "systems.iot"),
    tags=("embedded", "iot", "telemetry", "firmware", "device-security"),
    stages=(
        (
            "stage.contract",
            "Contract",
            "Define device and fleet boundaries.",
            (
                (
                    "define_device_identity",
                    "Define hardware, firmware, keys, capabilities, ownership, and lifecycle identity.",
                ),
                (
                    "define_telemetry_contract",
                    "Define event schemas, time semantics, units, frequency, retention, and privacy.",
                ),
                (
                    "define_command_authority",
                    "Define command authentication, authorization, idempotency, safety, and expiry.",
                ),
            ),
        ),
        (
            "stage.firmware",
            "Firmware",
            "Build and qualify immutable firmware.",
            (
                (
                    "build_firmware",
                    "Build exact target binaries with dependency, compiler, configuration, and provenance identity.",
                ),
                (
                    "static_firmware_checks",
                    "Check memory, interfaces, unsafe operations, secrets, and supply-chain policy.",
                ),
                (
                    "hardware_fixture_tests",
                    "Run deterministic host, emulator, or hardware-in-loop fixtures under an honest boundary.",
                ),
            ),
        ),
        (
            "stage.telemetry",
            "Telemetry",
            "Ingest and reconcile fleet observations.",
            (
                (
                    "authenticate_events",
                    "Authenticate device identity, integrity, sequence, and replay state.",
                ),
                (
                    "normalize_events",
                    "Normalize schemas, units, event time, and firmware-version context.",
                ),
                (
                    "derive_device_state",
                    "Derive current state, health, connectivity, and uncertainty.",
                ),
                (
                    "detect_fleet_anomalies",
                    "Detect device, cohort, location, version, and fleet anomalies.",
                ),
            ),
        ),
        (
            "stage.command",
            "Command",
            "Execute bounded remote actions.",
            (
                (
                    "plan_command",
                    "Create a target, precondition, expiry, rollout, and rollback-bound command plan.",
                ),
                (
                    "authorize_command",
                    "Apply least privilege and accountable approval to physical or fleet effects.",
                ),
                (
                    "execute_command",
                    "Execute idempotently through an authenticated delivery adapter.",
                ),
                (
                    "verify_command",
                    "Verify acknowledgement, resulting state, partial failures, and rollback readiness.",
                ),
            ),
        ),
        (
            "stage.operate",
            "Operate",
            "Release and maintain the fleet safely.",
            (
                (
                    "stage_firmware_release",
                    "Roll out through canary cohorts with compatibility and recovery gates.",
                ),
                (
                    "monitor_fleet",
                    "Monitor health, security, energy, connectivity, drift, and support impact.",
                ),
                (
                    "retire_device",
                    "Revoke authority, erase governed data, and preserve lifecycle evidence.",
                ),
            ),
        ),
    ),
)


HEALTHCARE_EVIDENCE = _template(
    template_id="template.healthcare-evidence",
    title="Healthcare data and decision-support evidence",
    description="A consent, terminology, longitudinal record, model, clinical review, and monitoring scaffold.",
    domains=("healthcare.data", "healthcare.decision-support"),
    tags=("healthcare", "clinical-data", "human-review", "privacy"),
    stages=(
        (
            "stage.govern",
            "Govern",
            "Establish purpose, consent, and accountable use.",
            (
                (
                    "define_intended_use",
                    "Define population, setting, decision, exclusions, users, and non-use cases.",
                ),
                (
                    "verify_consent_authority",
                    "Verify consent, legal basis, minimum necessary access, and retention.",
                ),
                (
                    "define_clinical_oracle",
                    "Define independent clinical, safety, subgroup, and workflow acceptance.",
                ),
            ),
        ),
        (
            "stage.integrate",
            "Integrate",
            "Construct an evidence-preserving longitudinal record.",
            (
                (
                    "normalize_health_formats",
                    "Normalize admitted healthcare messages, documents, images, and measurements.",
                ),
                (
                    "map_terminology",
                    "Map codes and concepts with exact terminology versions and uncertainty.",
                ),
                (
                    "resolve_patient",
                    "Resolve identity under privacy, error, and human-review controls.",
                ),
                (
                    "reconcile_timeline",
                    "Reconcile event time, amendments, provenance, and conflicting observations.",
                ),
            ),
        ),
        (
            "stage.analyze",
            "Analyze",
            "Produce bounded analytical or decision-support evidence.",
            (
                (
                    "derive_clinical_features",
                    "Derive point-in-time features with missingness and provenance.",
                ),
                (
                    "apply_decision_support",
                    "Apply rules or models only within the declared intended-use boundary.",
                ),
                (
                    "quantify_uncertainty",
                    "Quantify uncertainty, abstention, applicability, and subgroup behavior.",
                ),
            ),
        ),
        (
            "stage.review",
            "Review",
            "Keep consequential interpretation accountable.",
            (
                (
                    "explain_evidence",
                    "Present source-grounded factors, limitations, alternatives, and uncertainty.",
                ),
                (
                    "conduct_clinical_review",
                    "Require qualified human review and preserve amendments or disagreement.",
                ),
                (
                    "verify_workflow_fit",
                    "Verify that presentation, timing, escalation, and override behavior fit the real workflow.",
                ),
            ),
        ),
        (
            "stage.monitor",
            "Monitor",
            "Detect harm, drift, and misuse after release.",
            (
                (
                    "monitor_safety_quality",
                    "Monitor errors, overrides, delays, subgroup performance, drift, and adverse events.",
                ),
                ("audit_access", "Audit access, disclosure, retention, and downstream reuse."),
                (
                    "publish_healthcare_receipt",
                    "Publish governed evidence and limitations without exposing protected data.",
                ),
            ),
        ),
    ),
)


PRODUCT_EXPERIMENTATION = _template(
    template_id="template.product-experimentation",
    title="Product experimentation and causal learning",
    description="A hypothesis, instrumentation, allocation, analysis, decision, and rollout scaffold.",
    domains=("product.experimentation", "analytics.causal"),
    tags=("experiment", "ab-test", "causal", "product-analytics"),
    stages=(
        (
            "stage.design",
            "Design",
            "Predeclare the product question and decision rule.",
            (
                (
                    "define_hypothesis",
                    "Define intervention, estimand, population, mechanism, and decision consequence.",
                ),
                (
                    "define_metrics",
                    "Define primary, guardrail, diagnostic, long-term, and data-quality metrics.",
                ),
                (
                    "design_allocation",
                    "Define unit, randomization, stratification, duration, power, and interference assumptions.",
                ),
            ),
        ),
        (
            "stage.instrument",
            "Instrument",
            "Create trustworthy exposure and outcome data.",
            (
                (
                    "define_events",
                    "Define versioned exposure, assignment, outcome, eligibility, and context events.",
                ),
                (
                    "verify_instrumentation",
                    "Verify event semantics, loss, duplication, latency, and cross-platform identity.",
                ),
                (
                    "audit_pre_experiment",
                    "Audit sample-ratio, covariate, historical, novelty, and seasonality risks.",
                ),
            ),
        ),
        (
            "stage.run",
            "Run",
            "Operate the experiment under fixed governance.",
            (
                (
                    "assign_units",
                    "Assign eligible units reproducibly and preserve intention-to-treat identity.",
                ),
                (
                    "monitor_guardrails",
                    "Monitor safety and operational guardrails without optional-stopping abuse.",
                ),
                (
                    "record_deviations",
                    "Record contamination, outages, changes, exclusions, and protocol deviations.",
                ),
            ),
        ),
        (
            "stage.analyze",
            "Analyze",
            "Estimate effects and uncertainty robustly.",
            (
                (
                    "validate_experiment",
                    "Validate assignment, exposure, attrition, interference, and metric integrity.",
                ),
                (
                    "estimate_effects",
                    "Estimate declared effects, uncertainty, multiplicity, and practical significance.",
                ),
                (
                    "analyze_heterogeneity",
                    "Analyze predeclared slices and bounded exploratory heterogeneity.",
                ),
                (
                    "run_sensitivity",
                    "Test robustness to missingness, noncompliance, novelty, duration, and estimator choice.",
                ),
            ),
        ),
        (
            "stage.decide",
            "Decide",
            "Turn evidence into a reversible product decision.",
            (
                (
                    "compare_decision_options",
                    "Compare ship, iterate, stop, extend, or segment under value and risk.",
                ),
                (
                    "approve_rollout",
                    "Require accountable review for the declared consequence and uncertainty.",
                ),
                (
                    "monitor_rollout",
                    "Monitor long-term effects, drift, regressions, and rollback triggers.",
                ),
                (
                    "publish_experiment_receipt",
                    "Publish preregistration, data, deviations, analysis, decision, and limitations.",
                ),
            ),
        ),
    ),
)


EDUCATION_ASSESSMENT = _template(
    template_id="template.education-assessment",
    title="Educational content and assessment assurance",
    description="A standards, content, assessment, accessibility, scoring, review, and learning scaffold.",
    domains=("education.assessment", "education.content"),
    tags=("education", "assessment", "rubric", "accessibility"),
    stages=(
        (
            "stage.contract",
            "Contract",
            "Define learning and fairness obligations.",
            (
                (
                    "define_learning_objectives",
                    "Bind learning objectives, prerequisite knowledge, level, population, and setting.",
                ),
                (
                    "define_assessment_claims",
                    "Define what evidence supports each proficiency claim and what it cannot establish.",
                ),
                (
                    "define_fairness_accessibility",
                    "Define accessibility, accommodation, cultural, language, privacy, and fairness criteria.",
                ),
            ),
        ),
        (
            "stage.author",
            "Author",
            "Create traceable content and assessment assets.",
            (
                (
                    "retrieve_source_material",
                    "Retrieve authoritative source material and exact standards.",
                ),
                (
                    "author_content",
                    "Author explanations, examples, activities, and alternate representations.",
                ),
                (
                    "author_items",
                    "Author assessment items, rubrics, distractors, rationales, and metadata.",
                ),
            ),
        ),
        (
            "stage.assure",
            "Assure",
            "Validate content before learner exposure.",
            (
                (
                    "verify_accuracy",
                    "Verify claims, calculations, citations, and answer keys independently.",
                ),
                (
                    "verify_alignment",
                    "Verify objective, item, rubric, difficulty, and cognitive-demand alignment.",
                ),
                (
                    "audit_accessibility",
                    "Audit structure, presentation, alternatives, accommodations, and assistive compatibility.",
                ),
                (
                    "audit_bias",
                    "Review language, context, differential difficulty, stereotype, and subgroup risks.",
                ),
            ),
        ),
        (
            "stage.score",
            "Score",
            "Produce accountable learner evidence.",
            (
                (
                    "deliver_assessment",
                    "Deliver under declared identity, timing, assistance, and integrity policy.",
                ),
                (
                    "score_responses",
                    "Score deterministically or with calibrated graders and retain criterion evidence.",
                ),
                (
                    "adjudicate_scores",
                    "Route ambiguous or consequential scores for trained human review.",
                ),
            ),
        ),
        (
            "stage.learn",
            "Learn",
            "Improve without compromising learners.",
            (
                (
                    "analyze_items",
                    "Analyze reliability, difficulty, discrimination, validity, and subgroup behavior.",
                ),
                (
                    "recommend_support",
                    "Recommend source-grounded next learning actions without overclaiming diagnosis.",
                ),
                (
                    "publish_assessment_receipt",
                    "Publish content, versions, administration, scoring, review, and limitations.",
                ),
            ),
        ),
    ),
)


CREATIVE_CONTENT_PRODUCTION = _template(
    template_id="template.creative-content-production",
    title="Creative content production and campaign variants",
    description="A brief, rights, generation, edit, quality, experimentation, and publication scaffold.",
    domains=("creative.production", "media.campaign"),
    tags=("creative", "campaign", "image", "video", "audio"),
    stages=(
        (
            "stage.brief",
            "Brief",
            "Translate intent into testable creative constraints.",
            (
                (
                    "define_audience_goal",
                    "Define audience, channel, action, message, tone, and success evidence.",
                ),
                (
                    "define_brand_constraints",
                    "Define brand, factual, accessibility, format, and policy constraints.",
                ),
                (
                    "verify_rights",
                    "Verify source, likeness, music, trademark, license, disclosure, and retention rights.",
                ),
            ),
        ),
        (
            "stage.concept",
            "Concept",
            "Develop diverse traceable directions.",
            (
                (
                    "research_context",
                    "Retrieve authorized product, audience, cultural, competitive, and campaign context.",
                ),
                (
                    "generate_concepts",
                    "Generate diverse concept families with source and prompt lineage.",
                ),
                (
                    "select_concepts",
                    "Select concepts across relevance, novelty, feasibility, risk, and diversity.",
                ),
            ),
        ),
        (
            "stage.produce",
            "Produce",
            "Create and edit media variants.",
            (
                (
                    "generate_assets",
                    "Generate or acquire text, image, audio, video, animation, or 3D components.",
                ),
                (
                    "assemble_variants",
                    "Assemble channel-, aspect-, duration-, language-, and audience-specific variants.",
                ),
                (
                    "edit_assets",
                    "Apply disclosed composition, timing, color, sound, typography, and localization edits.",
                ),
            ),
        ),
        (
            "stage.assure",
            "Assure",
            "Verify objective and policy constraints.",
            (
                (
                    "verify_factuality",
                    "Verify material product and contextual claims against authorized sources.",
                ),
                (
                    "verify_brand_quality",
                    "Verify brand, technical, continuity, legibility, loudness, and accessibility criteria.",
                ),
                (
                    "verify_safety_rights",
                    "Verify content policy, disclosures, privacy, likeness, and license coverage.",
                ),
                (
                    "conduct_human_review",
                    "Require accountable creative and risk review where declared.",
                ),
            ),
        ),
        (
            "stage.publish",
            "Publish",
            "Experiment and release with lineage.",
            (
                (
                    "package_channels",
                    "Package exact variants, metadata, captions, thumbnails, and delivery manifests.",
                ),
                (
                    "run_creative_experiment",
                    "Compare eligible variants under a preregistered audience and metric protocol.",
                ),
                (
                    "monitor_campaign",
                    "Monitor delivery, fatigue, negative feedback, policy, and outcome drift.",
                ),
                (
                    "publish_creative_receipt",
                    "Publish brief, sources, rights, prompts, edits, reviews, variants, and outcomes.",
                ),
            ),
        ),
    ),
)


FRONTIER_TEMPLATES = (
    CREATIVE_CONTENT_PRODUCTION,
    DIGITAL_TWIN_SIMULATION,
    EDUCATION_ASSESSMENT,
    EMBEDDED_IOT_SYSTEM,
    GAME_BUILD_PLAYTEST,
    HEALTHCARE_EVIDENCE,
    LLM_EVALUATION_HARNESS,
    PRODUCT_EXPERIMENTATION,
    ROBOTICS_CONTROL,
    THREE_D_ASSET_PIPELINE,
    VIDEO_MEDIA_PIPELINE,
)


__all__ = [
    "CREATIVE_CONTENT_PRODUCTION",
    "DIGITAL_TWIN_SIMULATION",
    "EDUCATION_ASSESSMENT",
    "EMBEDDED_IOT_SYSTEM",
    "FRONTIER_TEMPLATES",
    "GAME_BUILD_PLAYTEST",
    "HEALTHCARE_EVIDENCE",
    "LLM_EVALUATION_HARNESS",
    "PRODUCT_EXPERIMENTATION",
    "ROBOTICS_CONTROL",
    "THREE_D_ASSET_PIPELINE",
    "VIDEO_MEDIA_PIPELINE",
]
