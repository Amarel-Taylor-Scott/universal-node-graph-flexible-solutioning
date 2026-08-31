from __future__ import annotations

from sourceloop.domain import CaseKind, CaseRecord, Direction, Interaction
from sourceloop.extraction import extract_reply_payload


def test_quote_extraction_ignores_dates_and_preserves_price_units() -> None:
    case = CaseRecord(
        title="Extraction test",
        kind=CaseKind.QUOTE_INTELLIGENCE,
        objective="Extract a comparable quote.",
        requester_name="Test Buyer",
    )
    interaction = Interaction(
        thread_id="thread_test",
        direction=Direction.INBOUND,
        endpoint="quotes@example.test",
        subject="Re: quote request",
        body=(
            "Budgetary pricing is $125 per visit. Monthly preventive service is $890 per month. "
            "Setup is $250 one-time. Taxes are excluded. Valid through 2026-10-15."
        ),
    )

    payload = extract_reply_payload(case, interaction)
    quote = payload["quote"]

    assert quote is not None
    assert [item["unit_price"] for item in quote["line_items"]] == [125.0, 890.0, 250.0]
    assert [item["unit"] for item in quote["line_items"]] == ["visit", "month", "one_time"]
    assert quote["valid_until"].startswith("2026-10-15")
    assert all(item["unit_price"] != 2026 for item in quote["line_items"])
    assert "taxes" not in quote["unresolved_fields"]
