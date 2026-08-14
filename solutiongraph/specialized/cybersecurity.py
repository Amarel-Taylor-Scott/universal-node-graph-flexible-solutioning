"""Specialized package for authorized defensive cybersecurity workflows."""

from solutiongraph.specialized._builders import (
    embedding_feature,
    feature,
    gate,
    metric,
    recipe,
    specialized_pack,
)

NAMESPACE = "cybersecurity"

FEATURES = (
    feature(
        NAMESPACE,
        "authority-scope",
        "Defensive authority scope",
        "Profile approved systems, identities, time windows, telemetry, effects, secrets, and escalation boundaries.",
        "mapping",
    ),
    feature(
        NAMESPACE,
        "asset-attack-surface",
        "Asset and attack surface",
        "Count assets, services, identities, dependencies, exposures, criticality, ownership, and trust boundaries.",
        "mapping",
    ),
    feature(
        NAMESPACE,
        "telemetry-coverage",
        "Telemetry coverage",
        "Measure source, event-time, retention, schema, identity, and detection coverage gaps.",
        "mapping",
    ),
    embedding_feature(
        NAMESPACE,
        "case-embedding",
        "Defensive case embedding",
        "Optional redacted case-pattern embedding for historical retrieval under an exact embedding-space identity.",
    ),
)

METRICS = (
    metric(
        NAMESPACE,
        "detection-coverage",
        "Detection coverage",
        "Coverage of predeclared defensive behaviors, assets, and telemetry slices.",
        "maximize",
        "ratio",
        scope="scope.stress",
    ),
    metric(
        NAMESPACE,
        "false-positive",
        "False-positive rate",
        "Benign scenarios incorrectly promoted to actionable findings.",
        "minimize",
        "ratio",
        scope="scope.evaluation",
    ),
    metric(
        NAMESPACE,
        "evidence-integrity",
        "Evidence integrity",
        "Findings with complete source identity, timeline, chain, and disconfirming evidence.",
        "maximize",
        "ratio",
        scope="scope.finding",
    ),
    metric(
        NAMESPACE,
        "recovery",
        "Verified recovery",
        "Incidents with independently verified containment, eradication, recovery, and rollback evidence.",
        "maximize",
        "ratio",
        scope="scope.incident",
    ),
)

GATES = (
    gate(
        NAMESPACE,
        "finding",
        "Defensive finding gate",
        "Reject findings without authority, evidence integrity, hypothesis testing, and a bounded claim.",
        (METRICS[1].id, METRICS[2].id),
        oracle_kind="cross-implementation",
    ),
    gate(
        NAMESPACE,
        "response",
        "Response authority gate",
        "Escalate consequential containment and recovery actions for independent authorization and verification.",
        (METRICS[0].id, METRICS[3].id),
        oracle_kind="human",
        decision="escalate",
    ),
)

RECIPES = (
    recipe(
        NAMESPACE,
        "threat-model",
        "Asset inventory and threat model",
        "Resolve assets, identities, dependencies, trust boundaries, abuse cases, controls, and accountable mitigations.",
        ("artifact.system-inventory",),
        ("artifact.threat-model",),
        ("cyber.scope", "cyber.asset-graph", "cyber.threat-model", "cyber.control-map"),
        ("dag.govern.security", "dag.integrate.enrich.identity", "dag.generate.report"),
        ("template.login-system", "template.cybersecurity-investigation"),
        node_packs=("example.extended-arena-node-pack",),
        design_packs=("design-pack.fairness-risk", "design-pack.reproducibility-governance"),
        arena_tasks=("arena.dependency-assurance",),
    ),
    recipe(
        NAMESPACE,
        "investigation",
        "Defensive investigation",
        "Scope authority, normalize telemetry, correlate activity, test benign and malicious hypotheses, and publish evidence-bounded findings.",
        ("artifact.security-telemetry",),
        ("artifact.security-findings",),
        ("cyber.scope", "cyber.normalize", "cyber.correlate", "cyber.hypothesis", "cyber.report"),
        ("dag.operate.incident", "dag.govern.security", "dag.evaluate.safety"),
        ("template.cybersecurity-investigation",),
        node_packs=("example.frontier-domain-node-pack",),
        examples=("defensive-cyber-investigation",),
        arena_tasks=("arena.defensive-cyber-investigation",),
        limitations=(
            "The executable example is read-only synthetic telemetry and performs no containment.",
        ),
    ),
    recipe(
        NAMESPACE,
        "incident-recovery",
        "Incident containment and recovery",
        "Triage verified findings, select reversible containment, preserve evidence, recover services, and independently verify absence of recurrence.",
        ("artifact.security-findings",),
        ("artifact.recovery-evidence",),
        ("cyber.triage", "cyber.contain", "cyber.recover", "cyber.verify-recovery", "cyber.learn"),
        ("dag.operate.incident", "dag.govern.security", "dag.govern.provenance"),
        ("template.incident-response", "template.observability-sre"),
        node_packs=("example.extended-arena-node-pack",),
        examples=("incident-triage",),
        arena_tasks=("arena.incident-triage",),
        effects=("system.write",),
        permissions=("system.write",),
        limitations=(
            "Production response requires scoped effect adapters, approvals, idempotency, compensation, and tested rollback.",
        ),
    ),
)

PACK = specialized_pack(
    NAMESPACE,
    "Cybersecurity",
    "Authorized defensive security assurance, threat modeling, telemetry investigation, incident recovery, and evidence packaging.",
    domain_packs=(
        "domain-pack.security-compliance",
        "domain-pack.sre-incident",
        "domain-pack.platform-release",
    ),
    categories=tuple(dict.fromkeys(category for item in RECIPES for category in item.category_ids)),
    signals=(
        "cybersecurity",
        "security",
        "threat model",
        "incident response",
        "telemetry",
        "detection",
        "forensics",
        "vulnerability",
        "supply chain security",
    ),
    recipes=RECIPES,
    features=FEATURES,
    metrics=METRICS,
    gates=GATES,
    limitations=(
        "Only explicitly authorized defensive workflows are in scope.",
        "Local fixtures prove graph mechanics, not detection quality or production containment.",
    ),
)

__all__ = ["FEATURES", "GATES", "METRICS", "PACK", "RECIPES"]
