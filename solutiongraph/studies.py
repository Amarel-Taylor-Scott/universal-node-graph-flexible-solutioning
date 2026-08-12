"""Paired, uncertainty-aware analysis over immutable experiment receipts.

The ordinary experiment runner allocates and executes plans.  This module does
not rerun or rewrite that evidence.  It pairs comparable observations, reports
bootstrap confidence intervals, and makes a conservative promote/reject/
continue recommendation under an explicit study design.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from random import Random
from statistics import fmean, median
from typing import Any

from solutiongraph.evidence import EvidenceLedger, Objective, RunReceipt
from solutiongraph.model import DIGEST_RE, ID_RE, sha256_digest

STUDY_MODEL_VERSION = "0.1"
STUDY_VERDICTS = ("study.promote", "study.reject", "study.continue")


def _objective_dict(objective: Objective) -> dict[str, Any]:
    return {
        "metric": objective.metric,
        "direction": objective.direction,
        "weight": objective.weight,
        "hard_minimum": objective.hard_minimum,
        "hard_maximum": objective.hard_maximum,
    }


def _quantile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot compute a quantile of empty values")
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


@dataclass(frozen=True)
class StudyDesign:
    """Frozen comparison, pairing, uncertainty, and promotion policy."""

    id: str
    control_plan_digest: str
    candidate_plan_digests: tuple[str, ...]
    objectives: tuple[Objective, ...]
    task_case_ids: tuple[str, ...]
    confidence_level: float = 0.95
    bootstrap_resamples: int = 2_000
    random_seed: int = 0
    minimum_pairs: int = 2
    practical_effect_thresholds: tuple[tuple[str, float], ...] = ()
    acceptance_noninferiority_margin: float = 0.0
    minimum_acceptance_rate: float = 1.0

    @property
    def digest(self) -> str:
        return sha256_digest(self.to_dict())

    @property
    def threshold_map(self) -> dict[str, float]:
        return dict(self.practical_effect_thresholds)

    def validate(self, ledger: EvidenceLedger | None = None) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id):
            problems.append("study id must be a namespaced identifier")
        if not DIGEST_RE.fullmatch(self.control_plan_digest):
            problems.append("study control_plan_digest must be a sha256 digest")
        if (
            not self.candidate_plan_digests
            or len(self.candidate_plan_digests) != len(set(self.candidate_plan_digests))
            or any(not DIGEST_RE.fullmatch(item) for item in self.candidate_plan_digests)
        ):
            problems.append("study candidates must contain unique plan digests")
        if self.control_plan_digest in self.candidate_plan_digests:
            problems.append("study control cannot also be a candidate")
        if not self.objectives:
            problems.append("study objectives must not be empty")
        metric_ids = [objective.metric for objective in self.objectives]
        if len(metric_ids) != len(set(metric_ids)):
            problems.append("study objective metrics must be unique")
        for objective in self.objectives:
            problems.extend(objective.validate())
        if (
            not self.task_case_ids
            or len(self.task_case_ids) != len(set(self.task_case_ids))
            or any(not ID_RE.fullmatch(item) for item in self.task_case_ids)
        ):
            problems.append("study task_case_ids must contain unique namespaced ids")
        if not isfinite(self.confidence_level) or not 0.0 < self.confidence_level < 1.0:
            problems.append("study confidence_level must be between zero and one")
        if self.bootstrap_resamples <= 0:
            problems.append("study bootstrap_resamples must be positive")
        if isinstance(self.random_seed, bool) or not isinstance(self.random_seed, int):
            problems.append("study random_seed must be an integer")
        if self.minimum_pairs <= 0:
            problems.append("study minimum_pairs must be positive")
        threshold_metrics = [metric for metric, _ in self.practical_effect_thresholds]
        if len(threshold_metrics) != len(set(threshold_metrics)):
            problems.append("study practical effect metrics must be unique")
        if set(threshold_metrics) - set(metric_ids):
            problems.append("study practical effects must reference objective metrics")
        if any(not isfinite(value) or value < 0 for _, value in self.practical_effect_thresholds):
            problems.append("study practical effects must be finite and non-negative")
        if (
            not isfinite(self.acceptance_noninferiority_margin)
            or self.acceptance_noninferiority_margin < 0
            or self.acceptance_noninferiority_margin > 1
        ):
            problems.append("acceptance_noninferiority_margin must be in [0,1]")
        if not isfinite(self.minimum_acceptance_rate) or not (
            0.0 <= self.minimum_acceptance_rate <= 1.0
        ):
            problems.append("minimum_acceptance_rate must be in [0,1]")
        if ledger is not None:
            known_plans = {receipt.plan_digest for receipt in ledger.receipts}
            missing = sorted(
                {
                    self.control_plan_digest,
                    *self.candidate_plan_digests,
                }
                - known_plans
            )
            if missing:
                problems.append("study plans are absent from evidence: " + ", ".join(missing))
            known_cases = {receipt.task_case_id for receipt in ledger.receipts}
            missing_cases = sorted(set(self.task_case_ids) - known_cases)
            if missing_cases:
                problems.append(
                    "study task cases are absent from evidence: " + ", ".join(missing_cases)
                )
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "study_model_version": STUDY_MODEL_VERSION,
            "id": self.id,
            "control_plan_digest": self.control_plan_digest,
            "candidate_plan_digests": list(self.candidate_plan_digests),
            "objectives": [_objective_dict(item) for item in self.objectives],
            "task_case_ids": list(self.task_case_ids),
            "confidence_level": self.confidence_level,
            "bootstrap_resamples": self.bootstrap_resamples,
            "random_seed": self.random_seed,
            "minimum_pairs": self.minimum_pairs,
            "practical_effect_thresholds": dict(self.practical_effect_thresholds),
            "acceptance_noninferiority_margin": self.acceptance_noninferiority_margin,
            "minimum_acceptance_rate": self.minimum_acceptance_rate,
        }


@dataclass(frozen=True)
class PairedMetricResult:
    metric: str
    direction: str
    pairs: int
    control_mean: float
    candidate_mean: float
    raw_mean_delta: float
    oriented_mean_delta: float
    oriented_median_delta: float
    confidence_lower: float
    confidence_upper: float
    win_rate: float
    tie_rate: float
    practical_effect_threshold: float
    inference: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "direction": self.direction,
            "pairs": self.pairs,
            "control_mean": self.control_mean,
            "candidate_mean": self.candidate_mean,
            "raw_mean_delta": self.raw_mean_delta,
            "oriented_mean_delta": self.oriented_mean_delta,
            "oriented_median_delta": self.oriented_median_delta,
            "confidence_lower": self.confidence_lower,
            "confidence_upper": self.confidence_upper,
            "win_rate": self.win_rate,
            "tie_rate": self.tie_rate,
            "practical_effect_threshold": self.practical_effect_threshold,
            "inference": self.inference,
        }


@dataclass(frozen=True)
class StudyArmResult:
    candidate_plan_digest: str
    verdict: str
    stopping_recommendation: str
    paired_observations: int
    unmatched_receipts: int
    acceptance: PairedMetricResult
    objectives: tuple[PairedMetricResult, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_plan_digest": self.candidate_plan_digest,
            "verdict": self.verdict,
            "stopping_recommendation": self.stopping_recommendation,
            "paired_observations": self.paired_observations,
            "unmatched_receipts": self.unmatched_receipts,
            "acceptance": self.acceptance.to_dict(),
            "objectives": [item.to_dict() for item in self.objectives],
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ExperimentStudyReport:
    design: StudyDesign
    evidence_digest: str
    receipt_ids: tuple[str, ...]
    arms: tuple[StudyArmResult, ...]
    limitations: tuple[str, ...]

    @property
    def status(self) -> str:
        return "study.completed" if self.arms else "study.completed-no-candidates"

    @property
    def recommended_plan_digests(self) -> tuple[str, ...]:
        return tuple(
            arm.candidate_plan_digest for arm in self.arms if arm.verdict == "study.promote"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "study_model_version": STUDY_MODEL_VERSION,
            "status": self.status,
            "study_id": self.design.id,
            "design_digest": self.design.digest,
            "evidence_digest": self.evidence_digest,
            "receipt_ids": list(self.receipt_ids),
            "recommended_plan_digests": list(self.recommended_plan_digests),
            "configuration": self.design.to_dict(),
            "arms": [arm.to_dict() for arm in self.arms],
            "limitations": list(self.limitations),
        }


class ExperimentStudyRunner:
    """Compare each candidate with one fixed control on matched observations."""

    def analyze(self, design: StudyDesign, ledger: EvidenceLedger) -> ExperimentStudyReport:
        problems = design.validate(ledger)
        if problems:
            raise ValueError("invalid experiment study: " + "; ".join(problems))
        selected_plans = {design.control_plan_digest, *design.candidate_plan_digests}
        receipts = tuple(
            receipt
            for receipt in ledger.receipts
            if receipt.plan_digest in selected_plans
            and receipt.task_case_id in design.task_case_ids
        )
        arms = tuple(
            self._compare_candidate(design, receipts, candidate)
            for candidate in design.candidate_plan_digests
        )
        evidence_digest = sha256_digest([receipt.to_dict() for receipt in receipts])
        limitations = (
            "Bootstrap intervals describe this paired receipt sample; they are not a portable causal claim.",
            "Promotion still requires the declared task oracle, holdout policy, runtime trust boundary, and operational review.",
        )
        return ExperimentStudyReport(
            design,
            evidence_digest,
            tuple(receipt.id for receipt in receipts),
            arms,
            limitations,
        )

    def _compare_candidate(
        self,
        design: StudyDesign,
        receipts: tuple[RunReceipt, ...],
        candidate_digest: str,
    ) -> StudyArmResult:
        control = tuple(
            receipt for receipt in receipts if receipt.plan_digest == design.control_plan_digest
        )
        candidate = tuple(
            receipt for receipt in receipts if receipt.plan_digest == candidate_digest
        )
        paired, unmatched = self._pairs(control, candidate)
        acceptance = self._metric_result(
            metric="acceptance_rate",
            direction="maximize",
            values=tuple(
                (float(left.accepted is True), float(right.accepted is True))
                for left, right in paired
            ),
            threshold=0.0,
            design=design,
            seed_salt=f"{candidate_digest}:acceptance_rate",
        )
        objective_results: list[PairedMetricResult] = []
        missing_metrics: list[str] = []
        for objective in design.objectives:
            values = tuple(
                (float(left.metrics[objective.metric]), float(right.metrics[objective.metric]))
                for left, right in paired
                if objective.metric in left.metrics and objective.metric in right.metrics
            )
            if len(values) != len(paired):
                missing_metrics.append(objective.metric)
            objective_results.append(
                self._metric_result(
                    metric=objective.metric,
                    direction=objective.direction,
                    values=values,
                    threshold=design.threshold_map.get(objective.metric, 0.0),
                    design=design,
                    seed_salt=f"{candidate_digest}:{objective.metric}",
                )
            )

        sufficient = (
            len(paired) >= design.minimum_pairs
            and not unmatched
            and not missing_metrics
            and all(item.pairs >= design.minimum_pairs for item in objective_results)
        )
        acceptance_worse = (
            acceptance.confidence_upper < -design.acceptance_noninferiority_margin
        )
        acceptance_noninferior = (
            acceptance.confidence_lower >= -design.acceptance_noninferiority_margin
        )
        acceptance_eligible = acceptance.candidate_mean >= design.minimum_acceptance_rate
        hard_constraints_met = all(
            self._meets_hard_constraints(objective, result.candidate_mean)
            for objective, result in zip(
                design.objectives, objective_results, strict=True
            )
        )
        clearly_worse = tuple(item for item in objective_results if item.inference == "worse")
        clearly_better = tuple(item for item in objective_results if item.inference == "better")
        reasons: list[str] = []
        if unmatched:
            reasons.append(f"{unmatched} receipts could not be paired under the fixed boundary.")
        if missing_metrics:
            reasons.append(
                "Objective metrics were missing from one or more pairs: "
                + ", ".join(sorted(set(missing_metrics)))
                + "."
            )
        if len(paired) < design.minimum_pairs:
            reasons.append(
                f"Only {len(paired)} paired observations are available; "
                f"the design requires {design.minimum_pairs}."
            )

        if sufficient and (
            acceptance_worse
            or clearly_worse
            or not acceptance_eligible
            or not hard_constraints_met
        ):
            verdict = "study.reject"
            stopping = "study.stop-for-futility-or-harm"
            if acceptance_worse:
                reasons.append("The paired acceptance interval crosses the declared harm boundary.")
            if clearly_worse:
                reasons.append(
                    "Clear adverse objective evidence: "
                    + ", ".join(item.metric for item in clearly_worse)
                    + "."
                )
            if not acceptance_eligible:
                reasons.append(
                    "Candidate acceptance does not meet the declared promotion gate."
                )
            if not hard_constraints_met:
                reasons.append("Candidate objective means violate a hard constraint.")
        elif (
            sufficient
            and acceptance_noninferior
            and acceptance_eligible
            and hard_constraints_met
            and clearly_better
            and not clearly_worse
        ):
            verdict = "study.promote"
            stopping = "study.stop-for-promotion"
            reasons.append(
                "Acceptance is non-inferior and at least one objective clears its practical effect threshold."
            )
        else:
            verdict = "study.continue"
            stopping = "study.collect-more-paired-evidence"
            if sufficient:
                reasons.append("Current intervals do not justify promotion or rejection.")

        return StudyArmResult(
            candidate_digest,
            verdict,
            stopping,
            len(paired),
            unmatched,
            acceptance,
            tuple(objective_results),
            tuple(reasons),
        )

    @staticmethod
    def _meets_hard_constraints(objective: Objective, value: float) -> bool:
        if objective.hard_minimum is not None and value < objective.hard_minimum:
            return False
        return objective.hard_maximum is None or value <= objective.hard_maximum

    @staticmethod
    def _pair_key(receipt: RunReceipt) -> tuple[Any, ...]:
        return (
            receipt.task_case_id,
            receipt.seed,
            receipt.input_digest,
            receipt.verifier_digest,
            receipt.environment_digest,
        )

    @classmethod
    def _pairs(
        cls,
        control: tuple[RunReceipt, ...],
        candidate: tuple[RunReceipt, ...],
    ) -> tuple[tuple[tuple[RunReceipt, RunReceipt], ...], int]:
        controls: dict[tuple[Any, ...], list[RunReceipt]] = defaultdict(list)
        candidates: dict[tuple[Any, ...], list[RunReceipt]] = defaultdict(list)
        for receipt in control:
            controls[cls._pair_key(receipt)].append(receipt)
        for receipt in candidate:
            candidates[cls._pair_key(receipt)].append(receipt)
        pairs: list[tuple[RunReceipt, RunReceipt]] = []
        unmatched = 0
        for key in sorted(set(controls) | set(candidates), key=repr):
            left = sorted(controls.get(key, ()), key=lambda item: item.id)
            right = sorted(candidates.get(key, ()), key=lambda item: item.id)
            pairs.extend(zip(left, right, strict=False))
            unmatched += abs(len(left) - len(right))
        return tuple(pairs), unmatched

    @staticmethod
    def _metric_result(
        *,
        metric: str,
        direction: str,
        values: tuple[tuple[float, float], ...],
        threshold: float,
        design: StudyDesign,
        seed_salt: str,
    ) -> PairedMetricResult:
        if not values:
            return PairedMetricResult(
                metric,
                direction,
                0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                threshold,
                "insufficient",
            )
        raw = tuple(candidate - control for control, candidate in values)
        oriented = raw if direction == "maximize" else tuple(-value for value in raw)
        bootstrap_seed = int(
            sha256_digest({"seed": design.random_seed, "salt": seed_salt})[-16:], 16
        )
        random = Random(bootstrap_seed)
        bootstrap = tuple(
            fmean(oriented[random.randrange(len(oriented))] for _ in oriented)
            for _ in range(design.bootstrap_resamples)
        )
        tail = (1.0 - design.confidence_level) / 2.0
        lower = _quantile(bootstrap, tail)
        upper = _quantile(bootstrap, 1.0 - tail)
        if len(values) < design.minimum_pairs:
            inference = "insufficient"
        elif lower > threshold:
            inference = "better"
        elif upper < -threshold:
            inference = "worse"
        else:
            inference = "inconclusive"
        return PairedMetricResult(
            metric,
            direction,
            len(values),
            fmean(item[0] for item in values),
            fmean(item[1] for item in values),
            fmean(raw),
            fmean(oriented),
            median(oriented),
            lower,
            upper,
            sum(value > threshold for value in oriented) / len(oriented),
            sum(abs(value) <= threshold for value in oriented) / len(oriented),
            threshold,
            inference,
        )


__all__ = [
    "STUDY_MODEL_VERSION",
    "STUDY_VERDICTS",
    "ExperimentStudyReport",
    "ExperimentStudyRunner",
    "PairedMetricResult",
    "StudyArmResult",
    "StudyDesign",
]
