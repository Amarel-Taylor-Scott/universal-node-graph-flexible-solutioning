"""Paired uncertainty analysis for control versus SolutionGraph context."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from random import Random
from statistics import fmean, median
from typing import Any

from solutiongraph.agent_bench.model import (
    AgentBenchmarkSuite,
    AgentDecisionRecord,
    AgentTaskSpec,
    AgentTrialReceipt,
)
from solutiongraph.model import sha256_digest

ANALYSIS_MODEL_VERSION = "0.1"


def _quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot compute a quantile of empty values")
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


@dataclass(frozen=True)
class PairedAgentEffect:
    scope: str
    task_id: str | None
    harness_id: str
    model_id: str
    metric: str
    direction: str
    pairs: int
    control_mean: float
    solutiongraph_mean: float
    raw_mean_delta: float
    oriented_mean_delta: float
    oriented_median_delta: float
    confidence_lower: float
    confidence_upper: float
    win_rate: float
    tie_rate: float
    practical_effect: float
    inference: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "task_id": self.task_id,
            "harness_id": self.harness_id,
            "model_id": self.model_id,
            "metric": self.metric,
            "direction": self.direction,
            "pairs": self.pairs,
            "control_mean": self.control_mean,
            "solutiongraph_mean": self.solutiongraph_mean,
            "raw_mean_delta": self.raw_mean_delta,
            "oriented_mean_delta": self.oriented_mean_delta,
            "oriented_median_delta": self.oriented_median_delta,
            "confidence_lower": self.confidence_lower,
            "confidence_upper": self.confidence_upper,
            "win_rate": self.win_rate,
            "tie_rate": self.tie_rate,
            "practical_effect": self.practical_effect,
            "inference": self.inference,
        }


@dataclass(frozen=True)
class AgentBenchmarkReport:
    suite: AgentBenchmarkSuite
    receipts: tuple[AgentTrialReceipt, ...]
    effects: tuple[PairedAgentEffect, ...]
    decisions: tuple[AgentDecisionRecord, ...]
    planned_trials: int
    executed_trials: int
    skipped_trials: int
    unmatched_receipt_ids: tuple[str, ...]
    evidence_digest: str
    limitations: tuple[str, ...]

    @property
    def status(self) -> str:
        return "benchmark.completed" if self.executed_trials == self.planned_trials else "benchmark.completed-partial"

    @property
    def accepted_trials(self) -> int:
        return sum(receipt.accepted for receipt in self.receipts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_model_version": ANALYSIS_MODEL_VERSION,
            "status": self.status,
            "suite": self.suite.to_dict(),
            "suite_digest": self.suite.digest,
            "claim_scope": self.suite.claim_scope,
            "planned_trials": self.planned_trials,
            "executed_trials": self.executed_trials,
            "skipped_trials": self.skipped_trials,
            "accepted_trials": self.accepted_trials,
            "unmatched_receipt_ids": list(self.unmatched_receipt_ids),
            "evidence_digest": self.evidence_digest,
            "receipts": [receipt.to_dict() for receipt in self.receipts],
            "effects": [effect.to_dict() for effect in self.effects],
            "decisions": [decision.to_dict() for decision in self.decisions],
            "limitations": list(self.limitations),
        }


def _metric_effect(
    *,
    scope: str,
    task_id: str | None,
    harness_id: str,
    model_id: str,
    metric: str,
    direction: str,
    values: list[tuple[float, float]],
    suite: AgentBenchmarkSuite,
    seed_salt: str,
) -> PairedAgentEffect:
    sign = 1.0 if direction == "maximize" else -1.0
    raw = [right - left for left, right in values]
    oriented = [sign * value for value in raw]
    rng = Random(int(sha256_digest(f"{suite.digest}:{seed_salt}")[-16:], 16))
    bootstrap: list[float] = []
    for _ in range(suite.bootstrap_resamples):
        sample = [oriented[rng.randrange(len(oriented))] for _ in oriented]
        bootstrap.append(fmean(sample))
    alpha = (1.0 - suite.confidence_level) / 2.0
    lower = _quantile(bootstrap, alpha)
    upper = _quantile(bootstrap, 1.0 - alpha)
    practical = suite.practical_effect_for(metric)
    if lower > practical:
        inference = "solutiongraph-superior"
    elif upper < -practical:
        inference = "control-superior"
    elif lower >= -practical and upper <= practical:
        inference = "practically-equivalent"
    else:
        inference = "inconclusive"
    return PairedAgentEffect(
        scope,
        task_id,
        harness_id,
        model_id,
        metric,
        direction,
        len(values),
        fmean(left for left, _ in values),
        fmean(right for _, right in values),
        fmean(raw),
        fmean(oriented),
        median(oriented),
        lower,
        upper,
        sum(value > practical for value in oriented) / len(oriented),
        sum(abs(value) <= practical for value in oriented) / len(oriented),
        practical,
        inference,
    )


def _paired(
    receipts: tuple[AgentTrialReceipt, ...],
) -> tuple[list[tuple[AgentTrialReceipt, AgentTrialReceipt]], tuple[str, ...]]:
    by_key: dict[tuple[str, str, str, int, int], dict[str, AgentTrialReceipt]] = defaultdict(dict)
    for receipt in receipts:
        key = receipt.plan.pairing_key
        if receipt.plan.condition in by_key[key]:
            raise ValueError(f"duplicate condition receipt for paired key {key}")
        by_key[key][receipt.plan.condition] = receipt
    pairs: list[tuple[AgentTrialReceipt, AgentTrialReceipt]] = []
    unmatched: list[str] = []
    for conditions in by_key.values():
        if set(conditions) == {"control", "solutiongraph"}:
            pairs.append((conditions["control"], conditions["solutiongraph"]))
        else:
            unmatched.extend(receipt.id for receipt in conditions.values())
    pairs.sort(key=lambda pair: pair[0].plan.pairing_key)
    return pairs, tuple(sorted(unmatched))


def _decisions(
    suite: AgentBenchmarkSuite,
    effects: tuple[PairedAgentEffect, ...],
    receipts: tuple[AgentTrialReceipt, ...],
) -> tuple[AgentDecisionRecord, ...]:
    decisions: list[AgentDecisionRecord] = []
    grouped: dict[tuple[str, str], dict[str, PairedAgentEffect]] = defaultdict(dict)
    for effect in effects:
        if effect.scope == "overall":
            grouped[(effect.harness_id, effect.model_id)][effect.metric] = effect
    for (harness_id, model_id), metrics in sorted(grouped.items()):
        quality = metrics.get("oracle_score")
        acceptance = metrics.get("accepted_rate")
        if not quality or not acceptance:
            continue
        acceptance_floor = -suite.acceptance_noninferiority_margin
        winner = (
            quality.inference == "solutiongraph-superior"
            and acceptance.confidence_lower >= acceptance_floor
        )
        if not winner:
            continue
        supporting = tuple(
            receipt.id
            for receipt in receipts
            if receipt.plan.harness_id == harness_id
            and receipt.plan.model_id == model_id
            and receipt.plan.condition == "solutiongraph"
        )
        suffix = sha256_digest([harness_id, model_id])[-16:]
        decisions.append(
            AgentDecisionRecord(
                id=f"agent-decision.selected-{suffix}",
                state="SELECTED",
                trial_receipt_ids=supporting,
                reason=(
                    "SolutionGraph-condition receipts passed the predeclared paired "
                    "quality and acceptance gates and were selected for winner review."
                ),
            )
        )
        decisions.append(
            AgentDecisionRecord(
                id=f"agent-decision.winner-{suffix}",
                state="WINNER",
                trial_receipt_ids=supporting,
                reason="Paired quality interval exceeds the practical-effect gate without acceptance inferiority.",
            )
        )
        enforcing = all(
            receipt.isolation in ("microvm", "remote")
            for receipt in receipts
            if receipt.id in supporting
        )
        if suite.allow_promotion and enforcing and suite.claim_scope != "mechanism-fixture":
            decisions.append(
                AgentDecisionRecord(
                    id=f"agent-decision.promoted-{suffix}",
                    state="PROMOTED",
                    trial_receipt_ids=supporting,
                    reason="Suite-authorized promotion passed paired effects and enforcing isolation gates.",
                    authorized=True,
                )
            )
    return tuple(decisions)


def analyze_agent_benchmark(
    suite: AgentBenchmarkSuite,
    receipts: tuple[AgentTrialReceipt, ...],
    *,
    planned_trials: int | None = None,
    task_specs: tuple[AgentTaskSpec, ...] = (),
) -> AgentBenchmarkReport:
    """Pair identical task/harness/model/seed/repetition cells across conditions."""
    problems = suite.validate()
    if problems:
        raise ValueError("invalid agent benchmark suite: " + "; ".join(problems))
    if any(receipt.plan.suite_digest != suite.digest for receipt in receipts):
        raise ValueError("every receipt must bind the analyzed suite digest")
    pairs, unmatched = _paired(receipts)
    effects: list[PairedAgentEffect] = []
    task_groups: dict[tuple[str, str, str], list[tuple[AgentTrialReceipt, AgentTrialReceipt]]] = defaultdict(list)
    overall_groups: dict[tuple[str, str], list[tuple[AgentTrialReceipt, AgentTrialReceipt]]] = defaultdict(list)
    for pair in pairs:
        control, _ = pair
        task_groups[(control.plan.task_id, control.plan.harness_id, control.plan.model_id)].append(pair)
        overall_groups[(control.plan.harness_id, control.plan.model_id)].append(pair)
    default_metrics = (
        ("accepted_rate", "maximize"),
        ("oracle_score", "maximize"),
        ("wall_seconds", "minimize"),
    )
    metric_by_task = {
        spec.id: (
            default_metrics
            if spec.score_metric == "oracle_score"
            else (*default_metrics, (spec.score_metric, spec.score_direction))
        )
        for spec in task_specs
    }
    for (task_id, harness_id, model_id), group in sorted(task_groups.items()):
        for metric, direction in metric_by_task.get(task_id, default_metrics):
            values = [
                (
                    float(control.accepted) if metric == "accepted_rate" else (control.wall_seconds if metric == "wall_seconds" else control.metric_map.get(metric, 0.0)),
                    float(treatment.accepted) if metric == "accepted_rate" else (treatment.wall_seconds if metric == "wall_seconds" else treatment.metric_map.get(metric, 0.0)),
                )
                for control, treatment in group
            ]
            effects.append(
                _metric_effect(
                    scope="task",
                    task_id=task_id,
                    harness_id=harness_id,
                    model_id=model_id,
                    metric=metric,
                    direction=direction,
                    values=values,
                    suite=suite,
                    seed_salt=f"task:{task_id}:{harness_id}:{model_id}:{metric}",
                )
            )
    for (harness_id, model_id), group in sorted(overall_groups.items()):
        for metric, direction in default_metrics:
            values = [
                (
                    float(control.accepted) if metric == "accepted_rate" else (control.wall_seconds if metric == "wall_seconds" else control.metric_map.get(metric, 0.0)),
                    float(treatment.accepted) if metric == "accepted_rate" else (treatment.wall_seconds if metric == "wall_seconds" else treatment.metric_map.get(metric, 0.0)),
                )
                for control, treatment in group
            ]
            effects.append(
                _metric_effect(
                    scope="overall",
                    task_id=None,
                    harness_id=harness_id,
                    model_id=model_id,
                    metric=metric,
                    direction=direction,
                    values=values,
                    suite=suite,
                    seed_salt=f"overall:{harness_id}:{model_id}:{metric}",
                )
            )
    effect_tuple = tuple(effects)
    decisions = _decisions(suite, effect_tuple, receipts)
    planned = suite.total_trials if planned_trials is None else planned_trials
    limitations = (
        "Effects are paired within exact task, harness, model, seed, repetition, and budget cells.",
        "Bootstrap intervals characterize this receipt sample and do not establish universal or causal transfer.",
        "Context bytes are measured; provider token/cost limits are claims only when the harness supplies usage evidence and enforcement.",
        "Repository fixture evaluators are candidate-unreadable by workspace construction but not confidential from a hostile process on the same host.",
        "Generated diagrams are explanatory projections and never substitute for compiler or oracle evidence.",
        *suite.limitations,
    )
    return AgentBenchmarkReport(
        suite=suite,
        receipts=receipts,
        effects=effect_tuple,
        decisions=decisions,
        planned_trials=planned,
        executed_trials=len(receipts),
        skipped_trials=max(0, planned - len(receipts)),
        unmatched_receipt_ids=unmatched,
        evidence_digest=sha256_digest([receipt.to_dict() for receipt in receipts]),
        limitations=tuple(dict.fromkeys(limitations)),
    )


__all__ = [
    "ANALYSIS_MODEL_VERSION",
    "AgentBenchmarkReport",
    "PairedAgentEffect",
    "analyze_agent_benchmark",
]
