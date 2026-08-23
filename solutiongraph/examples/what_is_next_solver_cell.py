"""Dependency-free demonstration of the What-Is-Next Solver Cell.

The example deliberately performs no network, model, package, or Kaggle action.
A deterministic strategy first proposes a validation probe.  The reference
executor returns new evidence, and the same Solver Cell asks What-Is-Next again.
Once the delegated unknown is resolved, the strategy proposes a stop action.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from solutiongraph.model import sha256_digest
from solutiongraph.nexting import (
    ActionResult,
    DeterministicRuleStrategy,
    KnowledgeFact,
    KnowledgeReference,
    KnowledgeState,
    NextBudget,
    Rule,
    SolverCell,
    StrategyManifest,
    StrategyRegistry,
    StrategySelectionPolicy,
    Unknown,
    WhatIsNextEngine,
)


def _reference(reference_id: str, summary: str) -> KnowledgeReference:
    return KnowledgeReference(
        id=reference_id,
        kind="knowledge.demo-artifact",
        digest=sha256_digest({"id": reference_id, "summary": summary}),
        summary=summary,
        tags=("knowledge.demo",),
    )


@dataclass
class DemoExecutor:
    """Translate one selected probe proposal into append-only evidence."""

    def execute(self, proposal, state: KnowledgeState) -> ActionResult:
        if proposal.action_kind != "next.run-probe":
            return ActionResult(proposal.id, "skipped")
        validation = _reference(
            "knowledge.validation-result",
            "Grouped cross-validation is stable and prevents entity leakage.",
        )
        fact = KnowledgeFact(
            id="fact.validation-selected",
            subject="task.demo",
            predicate="ml.validation-selected",
            value="grouped-cross-validation",
            evidence_refs=(validation.id,),
        )
        return ActionResult(
            proposal_id=proposal.id,
            outcome="succeeded",
            produced_references=(validation,),
            produced_facts=(fact,),
            resolved_unknown_ids=("unknown.validation-design",),
            metrics={"validation_stability": 0.91},
        )


def build_demo_cell() -> SolverCell:
    strategy = DeterministicRuleStrategy(
        StrategyManifest(
            id="strategy.demo-what-is-next",
            version="1.0.0",
            family="strategy.deterministic-rules",
            description="Probe unresolved validation design, then stop.",
            deterministic=True,
        ),
        (
            Rule(
                id="rule.probe-validation",
                predicate=lambda context: bool(context.state.unknowns),
                action_kind="next.run-probe",
                title="Test validation alternatives",
                rationale=(
                    "Model and feature choices should not be optimized until the "
                    "validation boundary is credible."
                ),
                payload_factory=lambda _: {
                    "probe_kind": "probe.validation-design",
                    "alternatives": [
                        "random-kfold",
                        "grouped-cross-validation",
                        "time-aware-cross-validation",
                    ],
                },
                information_gain=1.0,
                utility=0.95,
                confidence=1.0,
            ),
            Rule(
                id="rule.stop-after-validation",
                predicate=lambda context: any(
                    fact.predicate == "ml.validation-selected"
                    for fact in context.state.facts
                ),
                action_kind="next.stop",
                title="Close the delegated Solver Cell",
                rationale="The delegated validation-design uncertainty is resolved.",
                payload_factory=lambda _: {"reason": "delegated-goal-satisfied"},
                utility=1.0,
                confidence=1.0,
            ),
        ),
        first_match_only=True,
    )
    return SolverCell(
        WhatIsNextEngine(StrategyRegistry((strategy,))),
        DemoExecutor(),
    )


def run_demo() -> dict[str, Any]:
    initial = KnowledgeState(
        id="state.demo-validation",
        revision="1",
        goal="Select a trustworthy validation design before model search.",
        references=(
            _reference(
                "knowledge.task-contract",
                "Grouped tabular regression with repeated entities.",
            ),
        ),
        unknowns=(
            Unknown(
                id="unknown.validation-design",
                question="Which split design measures generalization without leakage?",
                importance=1.0,
                suggested_probe_kinds=("probe.validation-design",),
            ),
        ),
    )
    result = build_demo_cell().run(
        initial,
        budget=NextBudget(
            max_strategy_calls=1,
            max_iterations=4,
            max_no_progress=2,
        ),
        selection_policy=StrategySelectionPolicy(
            include_strategy_ids=("strategy.demo-what-is-next",),
        ),
        original_task="Build a competitive tabular regression solution.",
        simplified_task="Predict a continuous target without entity leakage.",
    )
    return {
        "terminal_disposition": result.receipt.terminal_disposition,
        "reason": result.receipt.reason,
        "decision_count": len(result.decision_receipts),
        "executed_iteration_count": len(result.receipt.iteration_receipts),
        "remaining_unknowns": [item.id for item in result.state.unknowns],
        "knowledge_references": [item.id for item in result.state.references],
        "knowledge_facts": [item.to_dict() for item in result.state.facts],
        "receipt_digest": result.receipt.digest,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2, sort_keys=True))
