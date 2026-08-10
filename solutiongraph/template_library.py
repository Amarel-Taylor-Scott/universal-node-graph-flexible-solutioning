"""Reference semantic templates spanning unrelated software domains.

The catalogue is intentionally implementation-free. Each atomic slot names an
obligation and required capability; node registries independently supply every
compatible implementation. Task authors should refine the schematic state
types into domain schemas when instantiating a production program.
"""

from __future__ import annotations

from solutiongraph.model import (
    Edge,
    GraphInput,
    GraphOutput,
    Port,
    ProgramGraph,
    SemanticSlot,
    ValueType,
)
from solutiongraph.templates import (
    RefinementPolicy,
    SolutionTemplate,
    TemplateCatalog,
    TemplateStage,
)


def _template(
    *,
    template_id: str,
    title: str,
    description: str,
    domains: tuple[str, ...],
    tags: tuple[str, ...],
    stages: tuple[tuple[str, str, str, tuple[tuple[str, str], ...]], ...],
) -> SolutionTemplate:
    flat_slots = [slot for _, _, _, stage_slots in stages for slot in stage_slots]
    state_types = tuple(
        ValueType(f"{template_id}.state-{index}") for index in range(len(flat_slots) + 1)
    )
    slots: list[SemanticSlot] = []
    edges: list[Edge] = []
    stage_records: list[TemplateStage] = []
    slot_index = 0
    for stage_id, stage_title, stage_description, stage_slots in stages:
        stage_slot_ids: list[str] = []
        for slot_id, purpose in stage_slots:
            input_type = state_types[slot_index]
            output_type = state_types[slot_index + 1]
            slots.append(
                SemanticSlot(
                    id=slot_id,
                    purpose=purpose,
                    inputs=(Port("state", input_type),),
                    outputs=(Port("state", output_type),),
                    success_contract=(
                        f"{purpose.rstrip('.')} and preserve every invariant required by later slots."
                    ),
                    group=(stage_id,),
                    required_capabilities=(f"{template_id}.{slot_id}.perform",),
                )
            )
            stage_slot_ids.append(slot_id)
            if slot_index:
                edges.append(
                    Edge(
                        flat_slots[slot_index - 1][0],
                        "state",
                        slot_id,
                        "state",
                    )
                )
            slot_index += 1
        stage_records.append(
            TemplateStage(
                stage_id,
                stage_title,
                stage_description,
                tuple(stage_slot_ids),
            )
        )

    first_slot = flat_slots[0][0]
    last_slot = flat_slots[-1][0]
    program = ProgramGraph(
        id=f"template.{template_id}",
        version="1.0.0",
        task=f"Instantiate the {title} obligations for a task-specific contract.",
        success_contract=(
            "A task-specific independent acceptance oracle accepts the final result."
        ),
        slots=tuple(slots),
        edges=tuple(edges),
        inputs=(GraphInput("input", state_types[0], first_slot, "state"),),
        outputs=(GraphOutput("result", state_types[-1], last_slot, "state"),),
    )
    return SolutionTemplate(
        id=template_id,
        version="1.0.0",
        title=title,
        description=description,
        program=program,
        stages=tuple(stage_records),
        refinements=(
            RefinementPolicy(
                id=f"{template_id}.repair-rejected-route",
                trigger="outcome.rejected",
                scopes=("program",),
                proposal_strategy="search.sprout",
                evaluation_contract=(
                    "Compile the proposal and re-run the task's independent acceptance oracle."
                ),
                stop_contract=(
                    "Stop at acceptance, explicit experiment exhaustion, or eight proposals."
                ),
                max_iterations=8,
                retain_history=True,
            ),
            RefinementPolicy(
                id=f"{template_id}.revisit-registry",
                trigger="registry.coverage-gap",
                scopes=("program",),
                proposal_strategy="discovery.refresh",
                evaluation_contract=(
                    "Negotiate again, preserve a new discovery receipt, then recompile."
                ),
                stop_contract="Stop after one new closed-world snapshot is admitted.",
                max_iterations=1,
                refresh_registry_snapshot=True,
            ),
        ),
        domains=domains,
        tags=tags,
        extensions=(("universal.template-state", "schematic; refine before execution"),),
    )


KAGGLE_TABULAR = _template(
    template_id="template.kaggle-tabular",
    title="Kaggle tabular supervised learning",
    description=(
        "A 27-obligation experiment scaffold from data acquisition through an audited "
        "submission, with EDA, leakage controls, model diversity, and ensembling visible."
    ),
    domains=("machine-learning.tabular", "competition.kaggle"),
    tags=("supervised-learning", "experimentation", "ensemble"),
    stages=(
        (
            "stage.acquire",
            "Acquire",
            "Load and establish the competition contract.",
            (
                ("load_data", "Load train, test, metadata, and sample submission assets."),
                (
                    "identify_target_metric",
                    "Identify target, evaluation metric, and submission schema.",
                ),
                ("schema_profile", "Profile columns, types, cardinalities, and missingness."),
            ),
        ),
        (
            "stage.investigate",
            "Investigate",
            "Produce evidence before changing data.",
            (
                ("split_strategy", "Define a leakage-safe validation and resampling strategy."),
                ("leakage_audit", "Audit temporal, entity, target, and duplicate leakage."),
                ("quality_profile", "Measure duplicates, invalid values, drift, and anomalies."),
                ("eda_distributions", "Analyze univariate target and feature distributions."),
                ("eda_relationships", "Analyze feature relationships and target associations."),
            ),
        ),
        (
            "stage.prepare",
            "Prepare",
            "Apply isolated, testable data transformations.",
            (
                ("deduplicate", "Resolve duplicate rows and conflicting entities."),
                ("type_repair", "Repair semantic types and parse malformed values."),
                ("missingness_policy", "Represent or impute missing values without leakage."),
                ("outlier_policy", "Detect and handle outliers under an explicit policy."),
                ("encode_categories", "Encode categorical values with fold-safe fitting."),
                (
                    "scale_numeric",
                    "Transform numeric values when the downstream model requires it.",
                ),
            ),
        ),
        (
            "stage.features",
            "Features",
            "Generate and select reproducible predictors.",
            (
                (
                    "generate_features",
                    "Generate domain, interaction, aggregate, and temporal features.",
                ),
                ("select_features", "Select a stable feature set using training-only evidence."),
            ),
        ),
        (
            "stage.model",
            "Model",
            "Fit, compare, calibrate, and combine model candidates.",
            (
                ("baseline_model", "Fit a simple reproducible baseline and establish a floor."),
                ("candidate_model_pool", "Fit a diverse pool of admitted model families."),
                ("cross_validate", "Evaluate each route using the declared validation protocol."),
                ("out_of_fold_predictions", "Produce complete out-of-fold predictions."),
                ("calibrate", "Calibrate predictions when the metric or use case requires it."),
                ("ensemble_select", "Select complementary models using holdout-safe evidence."),
                ("ensemble_fit", "Fit ensemble weights or stacker without validation leakage."),
            ),
        ),
        (
            "stage.deliver",
            "Deliver",
            "Validate and preserve a replayable submission.",
            (
                ("validate_holdout", "Run the independent holdout and robustness checks."),
                ("postprocess", "Apply contract-preserving prediction postprocessing."),
                ("package_submission", "Create and schema-check the submission artifact."),
                ("audit_receipt", "Record code, data, seed, environment, route, and metrics."),
            ),
        ),
    ),
)


DATA_QUALITY = _template(
    template_id="template.data-quality",
    title="Entity and address data quality",
    description="A reusable entity cleaning, validation, enrichment, and reconciliation scaffold.",
    domains=("data-engineering.quality", "data-management.entity"),
    tags=("cleaning", "validation", "external-reference"),
    stages=(
        (
            "stage.profile",
            "Profile",
            "Establish source and quality contracts.",
            (
                ("load_sources", "Load all source tables with immutable source identities."),
                ("infer_schema", "Infer and then confirm the semantic schema."),
                ("profile_quality", "Measure completeness, validity, uniqueness, and drift."),
            ),
        ),
        (
            "stage.normalize",
            "Normalize",
            "Apply field-local transformations.",
            (
                ("normalize_names", "Normalize person and business names."),
                ("parse_compound_names", "Separate compound and household names when justified."),
                ("normalize_address", "Normalize address text and locality conventions."),
                ("parse_street_components", "Parse street components into typed fields."),
                ("normalize_contact", "Normalize phone and electronic contact fields."),
            ),
        ),
        (
            "stage.resolve",
            "Resolve",
            "Validate and reconcile entities.",
            (
                (
                    "validate_postal",
                    "Validate deliverability against an admitted postal reference.",
                ),
                (
                    "validate_geography",
                    "Validate geographic components against an admitted census reference.",
                ),
                ("geocode", "Resolve coordinates with declared confidence and provenance."),
                ("match_entities", "Generate and score candidate entity matches."),
                ("merge_entities", "Merge accepted matches under a reversible policy."),
            ),
        ),
        (
            "stage.publish",
            "Publish",
            "Verify, report, and publish clean data.",
            (
                ("verify_constraints", "Run schema, referential, and business-rule checks."),
                ("publish_dataset", "Publish versioned outputs, rejects, and lineage receipts."),
            ),
        ),
    ),
)


QA_ENGINEERING = _template(
    template_id="template.qa-engineering",
    title="Software quality assurance",
    description="A test-planning, execution, diagnosis, and release-evidence scaffold.",
    domains=("software.quality",),
    tags=("testing", "verification", "release"),
    stages=(
        (
            "stage.understand",
            "Understand",
            "Convert change intent into testable obligations.",
            (
                ("load_change", "Load the change, ticket, contracts, and affected artifacts."),
                ("impact_analysis", "Identify affected components, interfaces, and risks."),
                ("derive_oracles", "Derive independent acceptance and regression oracles."),
            ),
        ),
        (
            "stage.design",
            "Design",
            "Create bounded, diverse test assets.",
            (
                (
                    "select_test_layers",
                    "Select unit, integration, contract, system, and property layers.",
                ),
                (
                    "generate_cases",
                    "Generate nominal, boundary, adversarial, and metamorphic cases.",
                ),
                ("prepare_fixtures", "Prepare isolated, deterministic fixtures and environments."),
            ),
        ),
        (
            "stage.execute",
            "Execute",
            "Run tests and gather typed observations.",
            (
                ("static_checks", "Run syntax, type, lint, policy, and security checks."),
                ("run_tests", "Execute the admitted test suites with recorded configuration."),
                ("collect_coverage", "Collect structural and requirements coverage evidence."),
                ("detect_flakes", "Repeat and classify unstable outcomes."),
            ),
        ),
        (
            "stage.decide",
            "Decide",
            "Diagnose and gate release independently.",
            (
                ("diagnose_failures", "Cluster failures and identify minimal reproducible causes."),
                ("verify_fixes", "Re-run focused and regression oracles after repair."),
                ("release_gate", "Apply the declared release policy and publish evidence."),
            ),
        ),
    ),
)


LOGIN_SYSTEM = _template(
    template_id="template.login-system",
    title="Authentication and login system",
    description="A security-conscious service implementation scaffold, not a fixed provider recipe.",
    domains=("software.application", "security.identity"),
    tags=("authentication", "authorization", "service"),
    stages=(
        (
            "stage.contract",
            "Contract",
            "Define identity boundaries and threats.",
            (
                (
                    "define_identity_contract",
                    "Define actors, credentials, sessions, and assurance levels.",
                ),
                (
                    "threat_model",
                    "Model abuse, disclosure, replay, enumeration, and recovery threats.",
                ),
                (
                    "select_protocol",
                    "Select an admitted authentication protocol and trust boundary.",
                ),
            ),
        ),
        (
            "stage.implement",
            "Implement",
            "Build atomic identity operations.",
            (
                ("account_storage", "Implement protected identity and credential storage."),
                ("registration", "Implement registration and proofing under policy."),
                ("credential_verification", "Verify credentials without leaking sensitive state."),
                ("session_issue", "Issue bounded, revocable sessions."),
                ("session_verify", "Verify session integrity, expiry, audience, and revocation."),
                ("logout_revoke", "Revoke sessions and propagate logout semantics."),
                ("account_recovery", "Implement abuse-resistant account recovery."),
            ),
        ),
        (
            "stage.protect",
            "Protect",
            "Add cross-cutting abuse and observability controls.",
            (
                ("rate_limit", "Apply privacy-preserving rate and abuse limits."),
                ("security_events", "Emit redacted, auditable identity security events."),
            ),
        ),
        (
            "stage.assure",
            "Assure",
            "Verify security and operational behavior.",
            (
                ("security_tests", "Run protocol, authorization, session, and abuse tests."),
                (
                    "deployment_gate",
                    "Gate deployment on independent security and reliability checks.",
                ),
            ),
        ),
    ),
)


DEPLOYMENT_RELEASE = _template(
    template_id="template.deployment-release",
    title="Deployment and release",
    description="A build, supply-chain, staged rollout, verification, and rollback scaffold.",
    domains=("software.delivery", "operations.deployment"),
    tags=("deployment", "supply-chain", "rollback"),
    stages=(
        (
            "stage.prepare",
            "Prepare",
            "Freeze intent and prove the build inputs.",
            (
                (
                    "load_release_intent",
                    "Load approved change intent, policy, and target environment.",
                ),
                ("resolve_dependencies", "Resolve immutable source and dependency identities."),
                ("build_artifact", "Build an isolated, reproducible release artifact."),
                ("generate_provenance", "Generate signed build and dependency provenance."),
            ),
        ),
        (
            "stage.qualify",
            "Qualify",
            "Run pre-release assurance.",
            (
                ("test_artifact", "Test the exact artifact that will be deployed."),
                ("scan_artifact", "Scan policy, vulnerabilities, licenses, and secrets."),
                ("approve_release", "Record an authorized release decision."),
            ),
        ),
        (
            "stage.rollout",
            "Roll out",
            "Change environments through bounded stages.",
            (
                ("provision_target", "Prepare target resources through an idempotent plan."),
                ("deploy_canary", "Deploy to a bounded canary population."),
                ("verify_canary", "Evaluate canary health against independent SLOs."),
                ("progressive_rollout", "Increase exposure under explicit promotion gates."),
            ),
        ),
        (
            "stage.close",
            "Close",
            "Verify, recover if needed, and preserve evidence.",
            (
                ("verify_production", "Verify production behavior and user-visible outcomes."),
                ("rollback_or_finalize", "Rollback safely or finalize the release state."),
                (
                    "publish_release_receipt",
                    "Publish artifact, approvals, observations, and decisions.",
                ),
            ),
        ),
    ),
)


SHIPPING_NOTIFICATIONS = _template(
    template_id="template.shipping-notifications",
    title="Shipping logistics notifications",
    description="An event ingestion, reconciliation, policy, delivery, and feedback scaffold.",
    domains=("logistics.shipping", "software.event-driven"),
    tags=("notifications", "integration", "workflow"),
    stages=(
        (
            "stage.ingest",
            "Ingest",
            "Accept and identify logistics events.",
            (
                ("receive_events", "Receive carrier, warehouse, and order events idempotently."),
                ("authenticate_source", "Authenticate event sources and verify integrity."),
                ("normalize_event", "Normalize provider payloads into a versioned event schema."),
                ("deduplicate_event", "Detect replayed or semantically duplicate events."),
            ),
        ),
        (
            "stage.reconcile",
            "Reconcile",
            "Build trustworthy shipment state.",
            (
                ("resolve_shipment", "Resolve event identifiers to the correct shipment."),
                ("order_events", "Order late and out-of-order events under declared semantics."),
                ("derive_status", "Derive the current shipment status and confidence."),
                ("detect_exception", "Detect delay, damage, address, and delivery exceptions."),
            ),
        ),
        (
            "stage.decide",
            "Decide",
            "Determine whether and how to notify.",
            (
                ("select_policy", "Apply customer, jurisdiction, urgency, and suppression policy."),
                ("select_recipient", "Resolve an authorized recipient and channel preference."),
                ("render_message", "Render localized, privacy-safe notification content."),
            ),
        ),
        (
            "stage.deliver",
            "Deliver",
            "Send and learn from typed outcomes.",
            (
                ("dispatch_notification", "Dispatch through an admitted delivery provider."),
                ("verify_delivery", "Observe provider and downstream delivery state."),
                ("handle_failure", "Retry, fail over, suppress, or escalate by failure class."),
                ("record_feedback", "Record delivery, engagement, and policy evidence."),
            ),
        ),
    ),
)


REFERENCE_TEMPLATES = TemplateCatalog(
    (
        DATA_QUALITY,
        DEPLOYMENT_RELEASE,
        KAGGLE_TABULAR,
        LOGIN_SYSTEM,
        QA_ENGINEERING,
        SHIPPING_NOTIFICATIONS,
    )
)


__all__ = [
    "DATA_QUALITY",
    "DEPLOYMENT_RELEASE",
    "KAGGLE_TABULAR",
    "LOGIN_SYSTEM",
    "QA_ENGINEERING",
    "REFERENCE_TEMPLATES",
    "SHIPPING_NOTIFICATIONS",
]
