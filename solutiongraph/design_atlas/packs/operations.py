"""LLM harness, deployment, monitoring, governance, and handoff packs."""

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


LLM_HARNESS = make_pack(
    "llm-harness",
    "LLM, agent, evaluation, and red-team harnesses",
    "Freeze scenarios, prompts, tools, authority, judges, attacks, transcripts, costs, and promotion boundaries.",
    "stage.specialized",
    _questions("llm-harness", (
        (
            "scenario-matrix", "Scenario and model matrix",
            "Which tasks, personas, languages, turns, contexts, modalities, models, sizes, settings, and tool configurations form the declared evaluation matrix?",
            "A model leaderboard without a shared scenario contract does not isolate model or infrastructure effects.",
            "Build a representative factorial scenario matrix", "Run one fixed scenario suite across models", 5, 0.9,
            ("evidence.scenario-manifest", "evidence.model-configurations"),
            ("task.llm-evaluation", "task.llm-red-teaming", "task.agent-harness"),
            ("source.stanford.helm",),
        ),
        (
            "tools-authority", "Tools, context, and authority",
            "Which tools, data, memory, network, files, secrets, users, and side effects may each model or agent access, and how are calls intercepted?",
            "Prompt instructions and retrieved content cannot grant runtime authority.",
            "Exercise least-authority and injection cases", "Use a read-only no-secret tool baseline", 6, 1.0,
            ("evidence.authority-manifest", "evidence.tool-call-transcripts"),
            ("task.llm-evaluation", "task.llm-red-teaming", "task.agent-harness"),
            ("source.nist.adversarial-ml",),
        ),
        (
            "judges", "Oracle, judges, and disagreement",
            "Which deterministic checks, reference answers, humans, model judges, panels, rubrics, calibrations, blindings, and appeals determine acceptance?",
            "An LLM judge is a fallible measured component and should not be the sole self-grader of consequential output.",
            "Calibrate judges against independent labels", "Combine deterministic gates with blinded review", 6, 1.0,
            ("evidence.judge-calibration", "evidence.oracle-independence"),
            ("task.llm-evaluation", "task.llm-red-teaming", "task.agent-harness"),
            ("source.stanford.helm", "source.mlcommons.safety-methodology"),
        ),
        (
            "red-team-coverage", "Red-team taxonomy and coverage",
            "Which misuse, evasion, injection, poisoning, privacy, extraction, reliability, bias, overreliance, and multi-step attacks match the use case and attacker model?",
            "A bag of prompts does not disclose threat coverage, personas, evaluator uncertainty, or missed space.",
            "Generate and retain taxonomy-linked adversarial cases", "Run the declared high-risk abuse suite", 7, 1.0,
            ("evidence.threat-model", "evidence.red-team-case-manifest", "evidence.coverage-report"),
            ("task.llm-red-teaming", "risk.high", "risk.critical"),
            ("source.nist.adversarial-ml", "source.mlcommons.safety-methodology"),
        ),
    )),
    ("source.stanford.helm", "source.nist.adversarial-ml", "source.mlcommons.safety-methodology"),
)


DEPLOYMENT_SERVING = make_pack(
    "deployment-serving",
    "Packaging, serving, release, and rollback",
    "Define immutable artifacts, environment parity, release gates, rollout, fallbacks, and recovery before promotion.",
    "stage.operations",
    _questions("deployment-serving", (
        (
            "artifact-closure", "Artifact and dependency closure",
            "Are model, code, graph, schema, features, environment, dependencies, licenses, configuration, and data references content-addressed and complete?",
            "A serialized model alone is not a reproducible deployable system.",
            "Rebuild and verify the artifact closure", "Package one immutable closed release", 4, 0.95,
            ("evidence.release-manifest", "evidence.clean-rebuild"),
            ("lifecycle.release", "lifecycle.production"),
            ("source.breck.ml-test-score",),
        ),
        (
            "serving-contract", "Serving interface and parity",
            "What batch, online, streaming, asynchronous, edge, or embedded interface guarantees schema, latency, throughput, freshness, ordering, and idempotency?",
            "Serving behavior and preprocessing must match the evaluated contract.",
            "Replay production-shaped serving cases", "Use a versioned batch interface", 5, 0.9,
            ("evidence.serving-contract", "evidence.training-serving-parity"),
            ("lifecycle.release", "lifecycle.production"),
            ("source.tensorflow.data-validation", "source.breck.ml-test-score"),
        ),
        (
            "rollout", "Shadow, canary, and promotion",
            "Which offline, replay, shadow, canary, A/B, phased, or manual gates promote a release, under what sample and time thresholds?",
            "A release needs predeclared evidence gates and cannot promote itself on one favorable metric.",
            "Compare release strategies with fixed gates", "Use shadow then guarded canary", 6, 1.0,
            ("evidence.release-policy", "evidence.shadow-receipts"),
            ("lifecycle.release", "lifecycle.production"),
            ("source.nist.ai-rmf-1",),
        ),
        (
            "rollback", "Rollback, degradation, and recovery",
            "Can the system detect failure, stop effects, restore prior artifacts, reconcile state, replay work, and verify recovery within the required objective?",
            "A rollback plan is unproven until its state and recovery path have been tested.",
            "Exercise rollback and dependency-failure drills", "Retain last-known-good plus fail-closed path", 6, 1.0,
            ("evidence.rollback-receipt", "evidence.recovery-objective"),
            ("lifecycle.release", "lifecycle.production"),
            ("source.breck.ml-test-score",),
        ),
    )),
)


MONITORING_FEEDBACK = make_pack(
    "monitoring-feedback",
    "Monitoring, delayed feedback, and controlled improvement",
    "Observe input, output, performance, drift, cost, incidents, labels, and retraining without contaminating protected evaluation.",
    "stage.operations",
    _questions("monitoring-feedback", (
        (
            "telemetry", "Operational and quality telemetry",
            "Which schemas, distributions, missingness, freshness, predictions, confidence, abstentions, latency, cost, failures, and policy events are observable?",
            "A system cannot govern failures or drift it does not measure.",
            "Verify telemetry completeness and privacy", "Emit minimum typed health and quality telemetry", 4, 0.9,
            ("evidence.telemetry-schema", "evidence.telemetry-test"),
            ("lifecycle.production",), ("source.breck.ml-test-score",),
        ),
        (
            "drift-performance", "Drift versus performance",
            "Which reference windows, thresholds, slices, tests, and label-delayed performance signals distinguish harmless change from degraded utility?",
            "Input drift is neither necessary nor sufficient evidence of model failure.",
            "Backtest drift and performance alerts", "Monitor schema plus delayed outcome quality", 5, 0.9,
            ("evidence.drift-policy", "evidence.alert-backtest"),
            ("lifecycle.production",), ("source.tensorflow.data-validation",),
        ),
        (
            "feedback-lineage", "Feedback and correction lineage",
            "How do delayed outcomes, appeals, human corrections, incidents, and edits link to the exact prediction, model, input, policy, and exposure?",
            "Unlinked feedback cannot support reliable learning or root-cause analysis.",
            "Trace representative outcomes end to end", "Use immutable prediction-to-outcome identifiers", 5, 0.95,
            ("evidence.feedback-lineage",), ("lifecycle.production",), (),
        ),
        (
            "retrain-policy", "Retraining and champion/challenger policy",
            "What trigger, data window, exclusion, validation, holdout, approval, and rollback policy governs retraining or graph mutation?",
            "Automatic retraining without fixed gates can amplify corruption or repeatedly tune on the same protected evidence.",
            "Simulate trigger and promotion policies", "Require a fresh evaluation closure for every challenger", 6, 1.0,
            ("evidence.retraining-policy", "evidence.champion-challenger-receipts"),
            ("lifecycle.production",), ("source.nist.ai-rmf-1", "source.breck.ml-test-score"),
        ),
    )),
)


REPRODUCIBILITY_GOVERNANCE = make_pack(
    "reproducibility-governance",
    "Reproducibility, documentation, ownership, and governance",
    "Preserve data/model cards, receipts, owners, approvals, incidents, security, and lifecycle controls.",
    "stage.governance",
    _questions("reproducibility-governance", (
        (
            "receipts", "Run receipts and clean replay",
            "Can another authorized environment reproduce the graph, code, inputs, splits, seeds, dependencies, artifacts, metrics, and acceptance result?",
            "A notebook output or final score is not an executable evidence trail.",
            "Perform clean-environment replay", "Retain complete content-addressed receipts", 5, 0.95,
            ("evidence.run-receipts", "evidence.clean-replay"), (),
            ("source.breck.ml-test-score",),
        ),
        (
            "data-model-cards", "Dataset and model documentation",
            "Are motivation, composition, collection, processing, intended use, evaluation, limitations, maintenance, and owners documented for each release?",
            "Structured documentation makes hidden assumptions reviewable across teams and time.",
            "Audit data and model cards with intended readers", "Require versioned data and model cards", 4, 0.9,
            ("evidence.data-card", "evidence.model-card"), (),
            ("source.gebru.datasheets", "source.pushkarna.data-cards", "source.mitchell.model-cards"),
        ),
        (
            "roles-approvals", "Roles, authority, and approvals",
            "Who owns data, model, evaluation, security, privacy, domain review, release, monitoring, incidents, and retirement, and which approvals are mandatory?",
            "Undefined ownership turns high-risk decisions into accidental defaults.",
            "Exercise the responsibility and approval matrix", "Require named owners for every gate", 4, 1.0,
            ("evidence.responsibility-matrix", "evidence.approval-records"), (),
            ("source.nist.ai-rmf-1", "source.nist.ai-rmf-playbook"),
        ),
        (
            "lifecycle", "Incidents, change, and retirement",
            "How are vulnerabilities, data/model changes, incidents, deprecations, retention expiry, downstream consumers, and retirement handled?",
            "Operational governance continues after first release and must include safe decommissioning.",
            "Run change, incident, and retirement tabletop tests", "Adopt versioned change and retirement gates", 5, 0.95,
            ("evidence.incident-plan", "evidence.retirement-plan"), (),
            ("source.nist.ai-rmf-1",),
        ),
    )),
    (
        "source.nist.ai-rmf-1",
        "source.gebru.datasheets",
        "source.pushkarna.data-cards",
        "source.mitchell.model-cards",
        "source.breck.ml-test-score",
    ),
)


DECISION_HANDOFF = make_pack(
    "decision-handoff",
    "Decision dossier and graph handoff",
    "Convert explored questions into typed obligations, candidate experiments, unresolved assumptions, and explicit stop conditions.",
    "stage.handoff",
    _questions("decision-handoff", (
        (
            "resolved-unresolved", "Resolved and unresolved decisions",
            "Which decisions are evidence-backed, provisional, abstained, blocked, or still unanswered, and who owns each next action?",
            "A polished plan should not conceal materially unresolved assumptions.",
            "Review the evidence state of every selected question", "Block compilation on critical unknowns", 3, 0.95,
            ("evidence.decision-records", "evidence.blocker-owners"), (), (),
        ),
        (
            "semantic-graph", "Semantic graph decomposition",
            "Which obligations, typed inputs/outputs, branches, loops, maps, reductions, barriers, and adapters express the solution without naming implementations?",
            "Task meaning must remain stable while candidate implementations and search policies vary.",
            "Review alternative semantic decompositions", "Compile the smallest complete semantic graph", 5, 0.9,
            ("evidence.program-graph", "evidence.task-contract"), (), (),
        ),
        (
            "experiment-grid", "Control, mutations, and experiment grid",
            "Which fixed control graph, explicit topology variants, compatible node routes, cases, seeds, budgets, objectives, and holdouts will be compared?",
            "A valid experiment holds task and evaluation meaning constant while varying declared solution choices.",
            "Compile and account for the full declared grid", "Compare one control with bounded diverse mutations", 5, 0.9,
            ("evidence.experiment-spec", "evidence.route-accounting"), (), (),
        ),
        (
            "claim-scope", "Claim scope and exit criteria",
            "What may be claimed from this dataset, protocol, environment, coverage, and uncertainty, and what evidence ends or reopens the work?",
            "Mechanism fixtures, internal datasets, public benchmarks, and production shadows support different claims.",
            "Challenge claim language against evidence", "Use the narrowest evidence-supported claim", 3, 1.0,
            ("evidence.claim-scope", "evidence.exit-criteria"), (),
            ("source.nist.ai-rmf-1",),
        ),
    )),
)


OPERATIONS_PACKS = (
    LLM_HARNESS,
    DEPLOYMENT_SERVING,
    MONITORING_FEEDBACK,
    REPRODUCIBILITY_GOVERNANCE,
    DECISION_HANDOFF,
)

__all__ = ["OPERATIONS_PACKS"]
