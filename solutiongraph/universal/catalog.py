"""Reference obligation, domain-pack, and engineering-question catalogs."""

from __future__ import annotations

from solutiongraph.universal.model import (
    CapabilityRequirement,
    DomainPack,
    EngineeringDesignQuestion,
    ObligationFamily,
)


def _obligation(
    suffix: str,
    title: str,
    description: str,
    prompt: str,
    examples: tuple[str, ...],
    categories: tuple[str, ...] = (),
) -> ObligationFamily:
    return ObligationFamily(
        id=f"obligation.{suffix}",
        title=title,
        description=description,
        design_prompt=prompt,
        capability_examples=examples,
        category_ids=categories,
    )


REFERENCE_OBLIGATIONS = (
    _obligation(
        "acquire",
        "Acquire",
        "Obtain authorized inputs while preserving source identity and boundaries.",
        "Which sources, snapshots, permissions, and freshness guarantees define acquisition?",
        ("batch ingest", "event consume", "authorized API fetch", "human submission"),
        ("dag.acquire",),
    ),
    _obligation(
        "decode",
        "Decode",
        "Turn transport or storage representations into explicit typed values.",
        "Which formats, versions, encodings, and malformed-input policies must be decoded?",
        ("parse JSON", "decode image", "extract document text", "deserialize event"),
        ("dag.prepare.parse",),
    ),
    _obligation(
        "validate",
        "Validate",
        "Check structural, semantic, policy, and authority preconditions.",
        "Which independent checks reject invalid inputs before consequential effects occur?",
        ("schema check", "contract test", "authorization check", "invariant check"),
        ("dag.prepare.verify", "dag.evaluate"),
    ),
    _obligation(
        "normalize",
        "Normalize",
        "Convert equivalent representations to a declared canonical form.",
        "What canonical representation, locale, units, and loss policy are required?",
        ("canonical names", "unit conversion", "date normalization", "identifier cleanup"),
        ("dag.prepare.normalize",),
    ),
    _obligation(
        "transform",
        "Transform",
        "Derive a new typed value without hiding material intermediate semantics.",
        "Which transformations are reversible, lossy, stateful, or dependent on training data?",
        ("feature construction", "document rendering", "code generation", "aggregation"),
        ("dag.prepare", "dag.generate"),
    ),
    _obligation(
        "enrich",
        "Enrich",
        "Join governed context, reference data, or derived knowledge to an input.",
        "Which authority, vintage, match policy, and provenance accompany enrichment?",
        ("geocode", "calendar join", "knowledge retrieval", "identity lookup"),
        ("dag.integrate.enrich",),
    ),
    _obligation(
        "reconcile",
        "Reconcile",
        "Resolve duplicates, conflicts, balances, or competing sources explicitly.",
        "Which precedence, tolerance, abstention, and escalation rules resolve conflict?",
        ("ledger balance", "entity merge", "three-way merge", "source adjudication"),
        ("dag.integrate.reconcile", "dag.prepare.conflict"),
    ),
    _obligation(
        "decide",
        "Decide",
        "Choose, rank, route, approve, or abstain under an explicit policy.",
        "Who or what may decide, on which evidence, with which abstention and appeal path?",
        ("policy gate", "route selection", "human approval", "resource allocation"),
        ("dag.learn.optimize", "dag.human.review"),
    ),
    _obligation(
        "persist",
        "Persist",
        "Store state or artifacts with identity, retention, and consistency semantics.",
        "Which consistency, idempotency, retention, encryption, and lineage rules apply?",
        ("database write", "artifact store", "checkpoint", "append-only ledger"),
        ("dag.operate.migrate", "dag.govern.provenance"),
    ),
    _obligation(
        "serve",
        "Serve",
        "Expose a result through a stable interface or delivery contract.",
        "Which API, event, UI, file, latency, and backward-compatibility contracts apply?",
        ("HTTP endpoint", "event publish", "report delivery", "frontend response"),
        ("dag.serve",),
    ),
    _obligation(
        "verify",
        "Verify",
        "Apply an independently identified oracle to outputs and effects.",
        "What exact evaluator can reject a plausible but wrong result independently?",
        ("property oracle", "holdout evaluator", "render comparison", "reconciliation check"),
        ("dag.evaluate",),
    ),
    _obligation(
        "observe",
        "Observe",
        "Emit enough telemetry and lineage to explain behavior and detect drift.",
        "Which traces, metrics, logs, lineage, alerts, and privacy filters are required?",
        ("trace span", "SLO metric", "audit event", "drift monitor"),
        ("dag.operate.observe",),
    ),
    _obligation(
        "recover",
        "Recover",
        "Retry, compensate, resume, roll back, or fail safely after disruption.",
        "Which failure classes are retryable, compensatable, resumable, or terminal?",
        ("bounded retry", "saga compensation", "checkpoint resume", "release rollback"),
        ("dag.operate.incident", "dag.serve.deploy"),
    ),
    _obligation(
        "govern",
        "Govern",
        "Constrain authority, privacy, compliance, provenance, and human accountability.",
        "Which policy, owner, approval, evidence, and retention boundary governs the work?",
        ("least privilege", "privacy review", "change approval", "audit evidence"),
        ("dag.govern",),
    ),
)

OBLIGATION_BY_ID = {item.id: item for item in REFERENCE_OBLIGATIONS}


def _cap(
    suffix: str,
    title: str,
    obligation: str,
    intent: str,
    *,
    templates: tuple[str, ...] = (),
    examples: tuple[str, ...] = (),
    benchmarks: tuple[str, ...] = (),
    agent_benchmarks: tuple[str, ...] = (),
    questions: tuple[str, ...] = (),
    adapters: tuple[str, ...] = (),
    blockers: tuple[str, ...] = (),
) -> CapabilityRequirement:
    return CapabilityRequirement(
        id=f"capability.{suffix}",
        title=title,
        obligation_id=f"obligation.{obligation}",
        intent=intent,
        template_ids=templates,
        example_ids=examples,
        benchmark_ids=benchmarks,
        agent_benchmark_ids=agent_benchmarks,
        question_pack_ids=questions,
        adapter_ids=adapters,
        blockers=blockers,
    )


def _domain(
    suffix: str,
    title: str,
    description: str,
    obligations: tuple[str, ...],
    capabilities: tuple[CapabilityRequirement, ...],
    *,
    standards: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
) -> DomainPack:
    return DomainPack(
        id=f"domain-pack.{suffix}",
        version="0.1",
        title=title,
        description=description,
        required_obligation_ids=tuple(f"obligation.{item}" for item in obligations),
        capabilities=capabilities,
        standard_ids=standards,
        limitations=limitations,
    )


REFERENCE_DOMAIN_PACKS = (
    _domain(
        "data-integration",
        "Data integration and quality",
        "Cleaning, contracts, entity resolution, geotemporal enrichment, and reconciliation.",
        ("validate", "enrich", "reconcile"),
        (
            _cap(
                "data.quality-validation",
                "Data quality validation",
                "validate",
                "Profile and reject structurally or semantically invalid records.",
                templates=("template.data-quality",),
                examples=("data-cleanup", "stdlib-data-quality"),
                benchmarks=("benchmark.data-cleaning", "benchmark.stdlib-data-quality"),
                questions=("question-pack.generic-tabular",),
            ),
            _cap(
                "data.reference-enrichment",
                "Reference and geotemporal enrichment",
                "enrich",
                "Attach versioned geographic, temporal, and identity context with provenance.",
                templates=("template.geospatial-analytics",),
                examples=("geotemporal-enrichment", "address-reference-verification"),
                questions=("question-pack.geography", "question-pack.datetime"),
            ),
            _cap(
                "data.multi-source-reconciliation",
                "Multi-source reconciliation",
                "reconcile",
                "Resolve conflicting or duplicated records without erasing source evidence.",
                templates=("template.batch-data-pipeline",),
                examples=("multi-feed-analytical-dataset", "transaction-reconciliation"),
                questions=("question-pack.transaction",),
            ),
        ),
        standards=("standard.cloudevents-1", "standard.openlineage"),
        limitations=("Bundled authority data is synthetic and not a production reference service.",),
    ),
    _domain(
        "backend-api",
        "Backend services and APIs",
        "Contract-safe request handling, idempotent effects, delivery, and rollback.",
        ("validate", "serve", "recover"),
        (
            _cap(
                "backend.api-contract",
                "API contract assurance",
                "validate",
                "Validate request, response, compatibility, and authorization contracts.",
                templates=("template.api-service",),
                examples=("idempotent-api-contract",),
                adapters=("adapter.openapi",),
            ),
            _cap(
                "backend.service-delivery",
                "Service delivery",
                "serve",
                "Expose typed, idempotent service behavior through a stable interface.",
                templates=("template.api-service",),
                examples=("idempotent-api-contract",),
                adapters=("adapter.orchestrator.kubernetes",),
            ),
            _cap(
                "backend.compensating-recovery",
                "Compensating recovery",
                "recover",
                "Retry or compensate partial service effects under explicit idempotency rules.",
                templates=("template.claims-processing",),
                examples=("transaction-reconciliation",),
                adapters=("adapter.orchestrator.temporal",),
            ),
        ),
        standards=("standard.openapi-3",),
    ),
    _domain(
        "event-stream",
        "Event and streaming systems",
        "Typed event ingestion, event-time decisions, observability, and replay boundaries.",
        ("acquire", "decide", "observe"),
        (
            _cap(
                "event.cloudevents-ingest",
                "CloudEvents ingestion",
                "acquire",
                "Normalize event envelope identity without claiming transport delivery semantics.",
                templates=("template.event-driven-system",),
                examples=("event-time-windowing",),
                adapters=("adapter.cloudevents",),
            ),
            _cap(
                "event.time-aware-routing",
                "Event-time routing",
                "decide",
                "Apply explicit windows, watermarks, lateness, and routing policies.",
                templates=("template.event-driven-system",),
                examples=("event-time-windowing", "user-journey-modeling"),
            ),
            _cap(
                "event.telemetry",
                "Producer/consumer telemetry",
                "observe",
                "Project graph execution into producer, consumer, trace, and lineage evidence.",
                templates=("template.observability-sre",),
                examples=("web-change-monitoring",),
            ),
        ),
        standards=("standard.cloudevents-1", "standard.opentelemetry"),
    ),
    _domain(
        "platform-release",
        "Platform and release engineering",
        "Build, dependency, migration, release-gate, and rollback graphs.",
        ("validate", "serve", "recover"),
        (
            _cap(
                "platform.release-gate",
                "Release gate",
                "validate",
                "Evaluate compatibility, security, quality, and policy evidence before promotion.",
                templates=("template.deployment-release",),
                examples=("frontend-release-journey", "dependency-assurance"),
            ),
            _cap(
                "platform.deployment",
                "Deployment projection",
                "serve",
                "Export a frozen plan to an external scheduler without changing its identity.",
                templates=("template.deployment-release",),
                adapters=("adapter.orchestrator.airflow", "adapter.orchestrator.kubernetes"),
                blockers=("An operator must provide an authenticated deployment runtime.",),
            ),
            _cap(
                "platform.rollback",
                "Release rollback",
                "recover",
                "Preserve promotion identity, health evidence, and a reversible rollback path.",
                templates=("template.deployment-release",),
                examples=("model-release-monitoring-and-rollback",),
            ),
        ),
        standards=("standard.in-toto-slsa", "standard.opentelemetry"),
    ),
    _domain(
        "sre-incident",
        "SRE and incident response",
        "Signal correlation, triage, mitigation, recovery, and post-incident evidence.",
        ("observe", "decide", "recover"),
        (
            _cap(
                "sre.signal-correlation",
                "Signal correlation",
                "observe",
                "Correlate traces, metrics, logs, changes, and dependency evidence.",
                templates=("template.observability-sre",),
                examples=("incident-triage", "web-change-monitoring"),
            ),
            _cap(
                "sre.incident-triage",
                "Incident triage",
                "decide",
                "Rank hypotheses and mitigations while preserving abstention and evidence.",
                templates=("template.incident-response",),
                examples=("incident-triage",),
            ),
            _cap(
                "sre.recovery",
                "Verified recovery",
                "recover",
                "Apply bounded retry, compensation, restore, or rollback and verify health.",
                templates=("template.incident-response",),
                examples=("model-release-monitoring-and-rollback",),
                adapters=("adapter.orchestrator.temporal",),
            ),
        ),
        standards=("standard.opentelemetry",),
    ),
    _domain(
        "security-compliance",
        "Security, privacy, and compliance",
        "Defensive assurance, evidence collection, redaction, policy gates, and recovery.",
        ("validate", "govern", "recover"),
        (
            _cap(
                "security.defensive-assurance",
                "Defensive assurance",
                "validate",
                "Inspect dependencies and artifacts using independently identified policies.",
                templates=("template.cybersecurity-investigation",),
                examples=("dependency-assurance", "pii-redaction"),
            ),
            _cap(
                "security.compliance-evidence",
                "Compliance evidence",
                "govern",
                "Bind controls, owners, evidence, exceptions, and review state.",
                templates=("template.compliance-evidence",),
                blockers=("Production certification requires an authorized external assessor.",),
            ),
            _cap(
                "security.hostile-runtime-recovery",
                "Hostile-runtime containment and recovery",
                "recover",
                "Contain, revoke, restore, and independently verify after adversarial execution.",
            ),
        ),
        standards=("standard.in-toto-slsa", "standard.opentelemetry"),
        limitations=("The repository does not provide a hostile-code sandbox or certification.",),
    ),
    _domain(
        "frontend-browser",
        "Frontend and browser systems",
        "Authorized acquisition, user-journey delivery, rendering, and independent checks.",
        ("acquire", "serve", "verify"),
        (
            _cap(
                "frontend.authorized-browser-acquire",
                "Authorized browser acquisition",
                "acquire",
                "Acquire pages through an explicit browser adapter and policy boundary.",
                templates=("template.web-automation",),
                examples=("browse-and-scrape", "verified-product-dataset"),
            ),
            _cap(
                "frontend.release-journey",
                "Frontend release journey",
                "serve",
                "Exercise a stable user journey and delivery contract before release.",
                templates=("template.qa-engineering",),
                examples=("frontend-release-journey",),
            ),
            _cap(
                "frontend.render-verification",
                "Render verification",
                "verify",
                "Verify layout, accessibility, content, and behavior through separate checks.",
                templates=("template.qa-engineering",),
                examples=("document-render-and-verify", "frontend-release-journey"),
            ),
        ),
    ),
    _domain(
        "database-storage",
        "Database and storage systems",
        "Schema migration, state persistence, reconciliation, and reversible cutover.",
        ("transform", "persist", "recover"),
        (
            _cap(
                "database.schema-migration",
                "Schema migration",
                "transform",
                "Plan and verify compatible schema and data transformations.",
                templates=("template.database-migration",),
                examples=("schema-migration",),
            ),
            _cap(
                "database.evidence-persistence",
                "Evidence persistence",
                "persist",
                "Content-address artifacts, checkpoints, and append-only receipts.",
                templates=("template.database-migration",),
                examples=("transaction-reconciliation",),
            ),
            _cap(
                "database.cutover-recovery",
                "Cutover recovery",
                "recover",
                "Resume or roll back migrations with explicit checkpoints and verification.",
                templates=("template.database-migration",),
                examples=("schema-migration",),
                adapters=("adapter.orchestrator.temporal",),
            ),
        ),
    ),
    _domain(
        "business-human-workflow",
        "Business and human workflows",
        "Cases, claims, approvals, escalations, auditability, and compensation.",
        ("decide", "govern", "recover"),
        (
            _cap(
                "business.authorized-approval",
                "Authorized human approval",
                "decide",
                "Collect an attributable decision without exposing sealed evaluator material.",
                templates=("template.claims-processing",),
                adapters=("adapter.bpmn",),
                blockers=("Execution requires an authenticated human task and delegation service.",),
            ),
            _cap(
                "business.case-governance",
                "Case governance",
                "govern",
                "Preserve policy version, evidence, ownership, deadlines, and appeal state.",
                templates=("template.claims-processing", "template.compliance-evidence"),
                adapters=("adapter.bpmn",),
                blockers=("Production case authority and retention policy are deployment-specific.",),
            ),
            # No recovery capability is declared: coverage reports this required
            # obligation as an explicit empty cell rather than silently omitting it.
        ),
        standards=("standard.bpmn-2",),
    ),
    _domain(
        "documents-media",
        "Documents, images, and media",
        "Decode, transform, ground, render, and independently verify rich artifacts.",
        ("decode", "transform", "verify"),
        (
            _cap(
                "media.document-decode",
                "Document decoding",
                "decode",
                "Decode document bytes and preserve page/layout evidence.",
                templates=("template.document-intelligence",),
                examples=("document-to-schema", "grounded-document-extraction"),
                benchmarks=("benchmark.document-extraction",),
                questions=("question-pack.document",),
            ),
            _cap(
                "media.image-transform",
                "Image transformation",
                "transform",
                "Orient, enhance, OCR, classify, and render images as visible substeps.",
                templates=("template.image-processing",),
                examples=("image-check-and-process", "document-render-and-verify"),
                benchmarks=("benchmark.image-assurance",),
            ),
            _cap(
                "media.grounded-verification",
                "Grounded media verification",
                "verify",
                "Check extracted claims and rendered artifacts against independent evidence.",
                templates=("template.document-intelligence",),
                examples=("grounded-document-extraction", "document-render-and-verify"),
                benchmarks=("benchmark.document-extraction",),
            ),
        ),
    ),
    _domain(
        "science-optimization",
        "Scientific computing and optimization",
        "Numerical transforms, controlled comparisons, optimization, simulation, and verification.",
        ("transform", "decide", "verify"),
        (
            _cap(
                "science.numerical-transform",
                "Numerical transform",
                "transform",
                "Qualify numerical preconditions before factorization or solving.",
                templates=("template.numerical-linear-system",),
                examples=("numerical-linear-system",),
            ),
            _cap(
                "science.experimental-decision",
                "Experimental decision",
                "decide",
                "Compare controlled alternatives under a frozen protocol and uncertainty.",
                templates=("template.scientific-experiment", "template.optimization-scheduling"),
                examples=("scientific-experiment", "reinforcement-learning-loop"),
            ),
            _cap(
                "science.residual-verification",
                "Residual and property verification",
                "verify",
                "Reject outputs that fail numerical, physical, or experimental invariants.",
                templates=("template.numerical-linear-system",),
                examples=("numerical-linear-system", "scientific-experiment"),
            ),
        ),
    ),
    _domain(
        "ai-ml",
        "AI and machine learning",
        "Leakage-safe preparation, model/search alternatives, evaluation, release, and monitoring.",
        ("normalize", "transform", "verify"),
        (
            _cap(
                "ml.leakage-safe-preparation",
                "Leakage-safe preparation",
                "normalize",
                "Fit preprocessing only inside the declared evaluation boundary.",
                templates=("template.kaggle-tabular",),
                examples=("tabular-regression", "tabular-classification"),
                benchmarks=("benchmark.tabular-regression", "benchmark.tabular-classification"),
                questions=("question-pack.ml-dataset",),
            ),
            _cap(
                "ml.model-and-feature-search",
                "Model and feature search",
                "transform",
                "Expose feature, model, calibration, and ensemble choices as visible candidates.",
                templates=("template.kaggle-tabular", "template.time-series-forecasting"),
                examples=(
                    "wide-table-feature-reduction",
                    "robust-regression-and-conformal",
                    "ensemble-selection-and-stacking",
                ),
                benchmarks=("benchmark.tabular-regression",),
            ),
            _cap(
                "ml.holdout-verification",
                "Holdout verification",
                "verify",
                "Separate development, validation, holdout, and operational evidence.",
                templates=("template.kaggle-tabular",),
                examples=(
                    "imbalanced-classification-and-calibration",
                    "model-release-monitoring-and-rollback",
                ),
                benchmarks=("benchmark.tabular-classification",),
            ),
        ),
        limitations=("Mechanism fixtures do not reproduce Taedri's external campaign results.",),
    ),
    _domain(
        "llm-agent",
        "LLM and agent systems",
        "Retrieval, tool use, synthetic curricula, multi-judge harnesses, red teams, and promotion.",
        ("enrich", "decide", "verify"),
        (
            _cap(
                "llm.grounded-context",
                "Grounded context assembly",
                "enrich",
                "Retrieve and cite context through an explicit authority and visibility boundary.",
                templates=("template.knowledge-retrieval",),
                examples=("grounded-document-extraction", "synthetic-llm-curriculum"),
            ),
            _cap(
                "llm.panel-decision",
                "Blinded panel decision",
                "decide",
                "Aggregate atomic judgments without leaking sealed case or evaluator material.",
                examples=("duecare-llm-evaluation-harness",),
                agent_benchmarks=("agent-benchmark.reference-smoke",),
                blockers=("External model claims require pinned, authorized model harnesses.",),
            ),
            _cap(
                "llm.adversarial-verification",
                "Adversarial verification",
                "verify",
                "Run red-team, holdout, judge-calibration, and human-promotion checks separately.",
                examples=("duecare-llm-evaluation-harness",),
                agent_benchmarks=("agent-benchmark.reference-smoke",),
            ),
        ),
        limitations=("The reference agent benchmark is a model-free transport mechanism test.",),
    ),
)

DOMAIN_PACK_BY_ID = {item.id: item for item in REFERENCE_DOMAIN_PACKS}


_QUESTION_BLUEPRINTS = {
    "acquire": (
        ("contract", "Which exact sources, snapshots, licenses, and owners are authorized?", "Unpinned or unauthorized inputs invalidate replay and governance.", ("source manifest", "authorization record"), ("digest every source", "reject undeclared sources"), 10, 1),
        ("freshness", "What freshness, completeness, ordering, and backpressure guarantees are required?", "Acquisition can silently succeed with stale or incomplete inputs.", ("freshness SLO", "completeness baseline"), ("simulate stale input", "test partial delivery"), 7, 2),
        ("failure", "How should unavailable, duplicated, delayed, or malicious inputs be handled?", "Input failures need explicit retry, quarantine, and abstention semantics.", ("failure taxonomy", "retry policy"), ("inject duplicates", "inject unavailable source"), 8, 3),
    ),
    "decode": (
        ("formats", "Which exact formats, versions, encodings, and compression layers are accepted?", "Ambiguous decoding creates hidden coercions and inconsistent results.", ("format registry", "schema digests"), ("round-trip fixtures", "reject unknown versions"), 9, 1),
        ("malformed", "Which malformed, oversized, recursive, or adversarial payloads must fail closed?", "Parsers are a common reliability and security boundary.", ("invalid fixture corpus", "size limits"), ("fuzz parser boundary", "test decompression limits"), 9, 3),
        ("provenance", "How are byte offsets, pages, fields, and source identity preserved through decoding?", "Grounding and audits require a path back to original evidence.", ("source map", "artifact digest"), ("verify source locations", "replay decoded artifact"), 7, 2),
    ),
    "validate": (
        ("contracts", "Which structural, semantic, policy, and authority checks are hard gates?", "Softening a hard gate lets optimization trade away correctness.", ("task contract", "policy version"), ("positive and negative fixtures", "mutation tests"), 10, 1),
        ("oracle", "Which independent oracle can reject plausible but wrong outputs?", "Candidate self-reports are not independent acceptance evidence.", ("oracle digest", "trust-boundary diagram"), ("cross-implementation test", "sealed-case test"), 10, 2),
        ("compatibility", "Which schema, unit, cardinality, state, and authority mismatches must fail before execution?", "Compatibility failures should not be discovered after effects occur.", ("port contracts", "compatibility catalog"), ("compile invalid edges", "test missing permission"), 9, 2),
    ),
    "normalize": (
        ("canonical", "What canonical form, units, locale, case, and identifier policy is required?", "Multiple canonical forms create false duplicates and unstable joins.", ("canonicalization specification",), ("idempotence test", "locale fixtures"), 8, 1),
        ("loss", "Which distinctions may normalization discard, and how is original evidence retained?", "Lossy cleanup can erase legally or analytically meaningful differences.", ("loss register", "raw artifact reference"), ("round-trip comparison", "collision analysis"), 9, 2),
        ("drift", "How will new values, units, locales, or branding conventions be detected?", "Canonicalization rules age and can silently damage new inputs.", ("unknown-value report", "rule version"), ("novelty fixture", "shadow comparison"), 6, 3),
    ),
    "transform": (
        ("semantics", "What invariant connects each transform input to its output?", "Opaque transformations make correctness and substitution untestable.", ("pre/postconditions", "intermediate schemas"), ("property tests", "golden fixtures"), 9, 1),
        ("alternatives", "Which genuinely interchangeable algorithms or implementations should remain visible?", "Hidden choices prevent controlled search and failure diversity.", ("candidate manifests", "admission decisions"), ("compile every candidate", "compare fallback failures"), 8, 2),
        ("state", "Which transforms are fitted, stateful, stochastic, lossy, or externally dependent?", "Undeclared state and randomness break replay and leakage boundaries.", ("state digest", "seed policy"), ("replay test", "train-boundary test"), 9, 3),
    ),
    "enrich": (
        ("authority", "Which reference authority, license, version, and effective date governs enrichment?", "Current or untrusted reference data can create point-in-time errors.", ("authority manifest", "vintage digest"), ("as-of fixture", "authority outage test"), 10, 2),
        ("matching", "Which exact, fuzzy, spatial, temporal, or semantic match policy is allowed?", "Aggressive matching can create confident false enrichment.", ("match policy", "abstention thresholds"), ("hard-negative fixtures", "boundary cases"), 9, 3),
        ("provenance", "Can every enriched field be traced to a source, match, time, and confidence?", "Field-level provenance is needed for correction and audit.", ("field lineage", "confidence calibration"), ("lineage completeness test", "source withdrawal test"), 8, 2),
    ),
    "reconcile": (
        ("identity", "What defines record, entity, transaction, or version identity?", "Wrong grain makes deduplication and balancing irrecoverably ambiguous.", ("identity contract", "key analysis"), ("duplicate fixtures", "split-entity fixtures"), 10, 1),
        ("conflict", "Which precedence, tolerance, abstention, and escalation rules resolve conflict?", "Silent last-write-wins policies erase disagreements and evidence.", ("conflict matrix", "source priorities"), ("tie fixture", "tolerance-boundary test"), 9, 2),
        ("balance", "Which conservation, balance, completeness, or referential invariants must hold?", "A merged result can look valid while losing or duplicating value.", ("reconciliation equation", "exception ledger"), ("conservation property", "orphan detection"), 9, 2),
    ),
    "decide": (
        ("authority", "Who or what may decide, approve, rank, route, or abstain?", "Decision authority must not be inferred from implementation capability.", ("decision-rights matrix", "delegation record"), ("unauthorized-decision test", "abstention test"), 10, 1),
        ("policy", "Which evidence, thresholds, objectives, and hard constraints govern the decision?", "A single score can hide hard failures and conflicting objectives.", ("policy digest", "objective vector"), ("threshold-boundary fixtures", "Pareto comparison"), 10, 2),
        ("appeal", "How can a decision be explained, challenged, overridden, or reversed?", "Consequential decisions need attributable review and recovery paths.", ("explanation record", "appeal workflow"), ("override authorization test", "reversal replay"), 8, 3),
    ),
    "persist": (
        ("identity", "Which state, artifacts, versions, and lineage must be persisted by digest?", "Mutable or ambiguous identity prevents exact replay.", ("artifact manifest", "schema version"), ("digest verification", "round-trip load"), 9, 1),
        ("consistency", "Which atomicity, consistency, idempotency, ordering, and concurrency guarantees apply?", "Storage semantics determine whether retries duplicate or corrupt effects.", ("consistency contract", "idempotency keys"), ("concurrent-write test", "retry test"), 10, 3),
        ("lifecycle", "Which retention, encryption, access, residency, backup, and deletion rules apply?", "Content identity alone does not provide data governance.", ("retention schedule", "access policy"), ("restore drill", "retention enforcement test"), 9, 3),
    ),
    "serve": (
        ("interface", "Which versioned API, event, UI, file, or report contract is promised?", "Serving contracts are external compatibility boundaries.", ("interface specification", "consumer inventory"), ("contract tests", "backward-compatibility diff"), 10, 1),
        ("slo", "Which latency, availability, throughput, freshness, and degradation objectives apply?", "A correct result can still fail its operational promise.", ("SLO definition", "capacity model"), ("load fixture", "degradation test"), 8, 3),
        ("safety", "How are authentication, authorization, rate limits, privacy, and output validation enforced?", "Serving turns internal computation into an attack and policy surface.", ("threat model", "authorization policy"), ("negative authorization tests", "output schema test"), 10, 3),
    ),
    "verify": (
        ("acceptance", "What exact property, metric, tolerance, and evaluator identity determine acceptance?", "Vague success criteria cannot support controlled experiments.", ("oracle manifest", "acceptance thresholds"), ("known-pass fixture", "known-fail fixture"), 10, 1),
        ("holdout", "Which development, validation, holdout, stress, and production-shadow boundaries apply?", "Repeated exposure turns a holdout into training data.", ("case split manifest", "visibility matrix"), ("digest split cases", "candidate-readability test"), 10, 2),
        ("uncertainty", "Which repetitions, seeds, slices, uncertainty intervals, and practical effects are required?", "One successful run does not establish robustness or superiority.", ("experiment design", "slice registry"), ("multi-seed run", "paired comparison"), 8, 3),
    ),
    "observe": (
        ("signals", "Which traces, metrics, logs, events, profiles, and lineage reconstruct a run?", "Missing signals make failures and regressions unactionable.", ("telemetry schema", "trace topology"), ("receipt-to-trace test", "missing-span test"), 8, 2),
        ("alerts", "Which SLO, drift, integrity, security, and business conditions should alert?", "Alerting needs actionable thresholds and ownership, not raw volume.", ("alert policy", "owner schedule"), ("synthetic alert", "false-positive review"), 8, 3),
        ("privacy", "Which sensitive fields must be redacted, aggregated, sampled, or access-controlled?", "Observability can become a secondary data leak.", ("telemetry data classification",), ("redaction test", "cardinality budget test"), 9, 3),
    ),
    "recover": (
        ("taxonomy", "Which failure classes are retryable, compensatable, resumable, degradable, or terminal?", "One recovery policy cannot safely fit every effect and failure.", ("failure taxonomy", "idempotency contract"), ("failure injection", "retry exhaustion"), 10, 1),
        ("state", "Which exact checkpoint, history, lease, or compensation state is required?", "Recovery against stale or mismatched state can compound damage.", ("checkpoint identity", "compensation manifest"), ("identity mismatch test", "partial-prefix resume"), 9, 3),
        ("drill", "How will rollback, restore, failover, reconciliation, and post-recovery verification be exercised?", "Untested recovery instructions are not operational evidence.", ("recovery runbook", "drill receipt"), ("restore drill", "independent health check"), 9, 4),
    ),
    "govern": (
        ("authority", "Which owner, policy, permission, and segregation-of-duties boundary applies?", "Optimization and implementation must never self-grant authority.", ("RACI or decision-rights record", "permission manifest"), ("least-privilege test", "self-approval test"), 10, 1),
        ("risk", "Which security, privacy, legal, fairness, safety, and compliance risks require gates?", "Different risks need explicit evidence and accountable acceptance.", ("risk register", "control mapping"), ("policy-negative fixtures", "exception expiry test"), 10, 3),
        ("change", "How are versions reviewed, promoted, monitored, rolled back, deprecated, and audited?", "Governance must cover the full lifecycle, not only initial approval.", ("change record", "promotion receipt"), ("rollback authorization test", "deprecation consumer scan"), 8, 3),
    ),
}


def _questions() -> tuple[EngineeringDesignQuestion, ...]:
    questions: list[EngineeringDesignQuestion] = []
    for obligation, blueprints in _QUESTION_BLUEPRINTS.items():
        for suffix, prompt, why, evidence, checks, priority, cost in blueprints:
            modes = (
                ("deterministic", "human")
                if suffix in {"contract", "formats", "canonical", "identity", "interface", "acceptance", "signals", "taxonomy", "authority"}
                else ("human", "llm", "external")
            )
            questions.append(
                EngineeringDesignQuestion(
                    id=f"engineering-question.{obligation}.{suffix}",
                    obligation_id=f"obligation.{obligation}",
                    prompt=prompt,
                    why_it_matters=why,
                    evidence_requests=evidence,
                    suggested_checks=checks,
                    response_modes=modes,
                    priority=priority,
                    effort_cost=cost,
                )
            )
    return tuple(questions)


REFERENCE_ENGINEERING_QUESTIONS = _questions()
ENGINEERING_QUESTION_BY_ID = {item.id: item for item in REFERENCE_ENGINEERING_QUESTIONS}


def validate_universal_catalog() -> list[str]:
    problems: list[str] = []
    obligation_ids = tuple(item.id for item in REFERENCE_OBLIGATIONS)
    if len(obligation_ids) != len(set(obligation_ids)):
        problems.append("reference obligation ids must be unique")
    for index, obligation in enumerate(REFERENCE_OBLIGATIONS):
        problems.extend(obligation.validate(f"obligations[{index}]"))
    domain_ids = [item.id for item in REFERENCE_DOMAIN_PACKS]
    if len(domain_ids) != len(set(domain_ids)):
        problems.append("reference domain pack ids must be unique")
    capability_ids = [
        capability.id for pack in REFERENCE_DOMAIN_PACKS for capability in pack.capabilities
    ]
    if len(capability_ids) != len(set(capability_ids)):
        problems.append("reference domain capability ids must be globally unique")
    for index, pack in enumerate(REFERENCE_DOMAIN_PACKS):
        problems.extend(pack.validate(obligation_ids, f"domain_packs[{index}]"))
    question_ids = [item.id for item in REFERENCE_ENGINEERING_QUESTIONS]
    if len(question_ids) != len(set(question_ids)):
        problems.append("reference engineering question ids must be unique")
    for index, question in enumerate(REFERENCE_ENGINEERING_QUESTIONS):
        problems.extend(question.validate(f"engineering_questions[{index}]"))
        if question.obligation_id not in obligation_ids:
            problems.append(f"engineering_questions[{index}] references unknown obligation")
    return problems


__all__ = [
    "DOMAIN_PACK_BY_ID",
    "ENGINEERING_QUESTION_BY_ID",
    "OBLIGATION_BY_ID",
    "REFERENCE_DOMAIN_PACKS",
    "REFERENCE_ENGINEERING_QUESTIONS",
    "REFERENCE_OBLIGATIONS",
    "validate_universal_catalog",
]
