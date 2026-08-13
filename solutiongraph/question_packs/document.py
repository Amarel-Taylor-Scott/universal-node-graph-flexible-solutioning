"""Document identity, extraction, grounding, and OCR questions."""

from __future__ import annotations

from solutiongraph.question_packs.base import deterministic, human, llm, pack, q

DOCUMENT = (
    "concept.document.identifier", "concept.document.text", "concept.document.url",
)

DOCUMENT_QUESTIONS = (
    q(
        "document", "identity", "Document identity and deduplication",
        "Are document identities content-addressed, stable across filenames, and free of accidental duplicates?",
        DOCUMENT, "document.identity-conflict", "high",
        (deterministic("quality.document-identity-check"),), scope="dataset",
    ),
    q(
        "document", "url", "Document URL validity",
        "Are source URLs syntactically valid, permitted, and associated with a capture timestamp and content digest?",
        ("concept.document.url",), "document.url-invalid", "high",
        (deterministic("quality.url-syntax-check"),), scope="pipeline",
    ),
    q(
        "document", "text-quality", "Extracted-text quality",
        "Does extracted or OCR text contain empty pages, mojibake, repeated headers, or suspicious character distributions?",
        ("concept.document.text",), "document.text-quality", "medium",
        (deterministic("quality.document-text-check", cost_tier=2),), scope="dataset",
    ),
    q(
        "document", "grounding", "Extraction grounding",
        "Can every extracted field or assertion be traced to page, region, span, and source digest evidence?",
        DOCUMENT, "document.ungrounded-extraction", "critical",
        (deterministic("quality.document-grounding-check", cost_tier=3),
         llm("quality.audit-document-grounding", cost_tier=7)), scope="pipeline",
    ),
    q(
        "document", "conflicts", "Conflicting document evidence",
        "When multiple document sections or versions disagree, is the conflict preserved and adjudicated explicitly?",
        DOCUMENT, "document.evidence-conflict", "high",
        (deterministic("quality.document-conflict-check", cost_tier=3),
         human("quality.review-document-conflict")), scope="entity",
    ),
    q(
        "document", "prompt-injection", "Untrusted document instructions",
        "Is document content treated as data rather than trusted instructions to an LLM or tool-using agent?",
        ("concept.document.text",), "document.prompt-injection-risk", "critical",
        (deterministic("quality.document-injection-pattern-check", cost_tier=3),
         human("quality.review-document-injection")), scope="pipeline",
        privacy_class="privacy.untrusted-content",
    ),
)

DOCUMENT_PACK = pack(
    "document", "Document interrogation",
    "Document identity, source, OCR quality, grounding, conflicts, and untrusted-content questions.",
    DOCUMENT_QUESTIONS,
)

__all__ = ["DOCUMENT_PACK", "DOCUMENT_QUESTIONS"]
