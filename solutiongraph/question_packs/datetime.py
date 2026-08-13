"""Date, time, ordering, timezone, and point-in-time questions."""

from __future__ import annotations

from solutiongraph.question_packs.base import deterministic, human, llm, pack, q

TIME = (
    "concept.time.instant", "concept.time.date", "concept.time.start",
    "concept.time.end", "concept.time.timezone",
)

DATETIME_QUESTIONS = (
    q(
        "datetime", "parseability", "Date-time parseability",
        "Are date and time values unambiguous, parseable, and free of mixed implicit formats?",
        TIME, "datetime.unparseable-or-ambiguous", "high",
        (deterministic("quality.datetime-parse-check"),), scope="dataset",
        repairs=("repair.iso-date-when-unambiguous",),
    ),
    q(
        "datetime", "timezone", "Timezone and UTC semantics",
        "Is each timestamp's timezone explicit, or is the source's timezone contract documented?",
        ("concept.time.instant", "concept.time.timezone"),
        "datetime.timezone-ambiguous", "high",
        (deterministic("quality.timezone-check"),), scope="cross-field",
    ),
    q(
        "datetime", "ordering", "Start and end ordering",
        "Are start, end, effective-from, and effective-to values ordered consistently?",
        ("concept.time.start", "concept.time.end"),
        "datetime.invalid-order", "high",
        (deterministic("quality.datetime-order-check"),), scope="row",
        preconditions=("precondition.records-available", "precondition.start-end-available"),
    ),
    q(
        "datetime", "future-values", "Unexpected future values",
        "Do event, creation, or effective timestamps occur implausibly in the future relative to the declared reference clock?",
        TIME, "datetime.unexpected-future", "medium",
        (deterministic("quality.future-time-check", cost_tier=2),), scope="dataset",
        preconditions=("precondition.records-available", "precondition.reference-clock-available"),
    ),
    q(
        "datetime", "daylight-saving", "Daylight-saving transitions",
        "Do local timestamps contain nonexistent or duplicated wall-clock times during timezone transitions?",
        ("concept.time.instant", "concept.time.timezone"),
        "datetime.dst-ambiguity", "medium",
        (deterministic("quality.dst-transition-check", cost_tier=3),
         human("quality.review-dst-ambiguity")), scope="row",
    ),
    q(
        "datetime", "granularity", "Granularity and precision",
        "Are date-only, second, millisecond, and rounded timestamps being compared under compatible precision?",
        TIME, "datetime.precision-conflict", "medium",
        (deterministic("quality.datetime-precision-check", cost_tier=2),), scope="dataset",
    ),
    q(
        "datetime", "point-in-time", "Point-in-time correctness",
        "Were features and enrichments available at the prediction or decision time rather than only afterward?",
        TIME, "datetime.future-leakage", "critical",
        (deterministic("quality.point-in-time-leakage-check", cost_tier=4),
         llm("quality.audit-point-in-time-lineage", cost_tier=7)), scope="pipeline",
    ),
    q(
        "datetime", "drift", "Temporal coverage and drift",
        "Are missing periods, duplicated intervals, irregular cadence, or source changes distorting trends?",
        TIME, "datetime.coverage-drift", "medium",
        (deterministic("quality.temporal-coverage-check", cost_tier=3),), scope="dataset",
    ),
)

DATETIME_PACK = pack(
    "datetime", "Date and time interrogation",
    "Date parsing, timezone, ordering, precision, leakage, transition, and coverage questions.",
    DATETIME_QUESTIONS,
)

__all__ = ["DATETIME_PACK", "DATETIME_QUESTIONS"]
