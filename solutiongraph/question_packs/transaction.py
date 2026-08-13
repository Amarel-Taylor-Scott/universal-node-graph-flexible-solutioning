"""Transaction, invoice, order, and monetary-field questions."""

from __future__ import annotations

from solutiongraph.question_packs.base import deterministic, human, llm, pack, q

TRANSACTION = (
    "concept.transaction.id", "concept.transaction.amount",
    "concept.transaction.currency", "concept.transaction.status",
)

TRANSACTION_QUESTIONS = (
    q(
        "transaction", "identifier", "Transaction identity",
        "Are transaction, invoice, order, and payment identifiers unique at their declared grain?",
        ("concept.transaction.id",), "transaction.identifier-conflict", "critical",
        (deterministic("quality.identifier-uniqueness-check"),), scope="dataset",
    ),
    q(
        "transaction", "amount-parse", "Monetary amount parsing",
        "Are signs, separators, parentheses, decimal precision, and nulls parsed without changing meaning?",
        ("concept.transaction.amount",), "transaction.amount-invalid", "high",
        (deterministic("quality.amount-parse-check"),),
    ),
    q(
        "transaction", "currency", "Currency presence and code",
        "Is every monetary amount paired with an explicit, plausible currency code?",
        ("concept.transaction.amount", "concept.transaction.currency"),
        "transaction.currency-missing-or-invalid", "critical",
        (deterministic("quality.currency-code-check"),), scope="cross-field",
    ),
    q(
        "transaction", "reconciliation", "Line, subtotal, tax, and total reconciliation",
        "Do line amounts, discounts, tax, fees, payments, and totals reconcile within declared rounding rules?",
        TRANSACTION, "transaction.reconciliation-failure", "critical",
        (deterministic("quality.transaction-reconcile-check", cost_tier=3),), scope="entity",
    ),
    q(
        "transaction", "status-flow", "Transaction status flow",
        "Do transaction statuses follow valid transitions without impossible reversals or missing events?",
        ("concept.transaction.id", "concept.transaction.status", "concept.time.instant"),
        "transaction.invalid-status-transition", "high",
        (deterministic("quality.status-transition-check", cost_tier=3),
         human("quality.review-status-transition")), scope="entity",
    ),
    q(
        "transaction", "duplicates", "Duplicate or replayed transactions",
        "Do repeated identifiers, amounts, timestamps, and actors indicate duplicate ingestion or legitimate retries?",
        TRANSACTION, "transaction.possible-duplicate", "critical",
        (deterministic("quality.transaction-duplicate-check", cost_tier=3),
         llm("quality.adjudicate-transaction-duplicate")), scope="dataset",
    ),
    q(
        "transaction", "temporal-leakage", "Transaction point-in-time correctness",
        "Do features or decisions use settlement, chargeback, or future status information unavailable at decision time?",
        TRANSACTION, "transaction.future-leakage", "critical",
        (deterministic("quality.point-in-time-leakage-check", cost_tier=4),), scope="pipeline",
    ),
)

TRANSACTION_PACK = pack(
    "transaction", "Transaction interrogation",
    "Identity, monetary parsing, reconciliation, status, duplicate, and leakage questions.",
    TRANSACTION_QUESTIONS,
)

__all__ = ["TRANSACTION_PACK", "TRANSACTION_QUESTIONS"]
