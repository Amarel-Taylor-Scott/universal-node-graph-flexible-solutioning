"""Data cleaning, conflict validation, and geotemporal enrichment tasks."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from solutiongraph.agent_bench.tasks.common import TaskCaseData, make_bundle

_MISSING = {"", "n/a", "na", "null", "none", "unknown"}


def _clean_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        value = " ".join(value.strip().split())
        if value.casefold() in _MISSING:
            return None
    return value


def solve_clean_customer_records(payload: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, dict[str, Any]] = {}
    quarantine: list[dict[str, Any]] = []
    duplicates = 0
    missing_cells = 0
    for index, raw in enumerate(payload["records"]):
        customer_id = _clean_scalar(raw.get("customer_id"))
        if customer_id is None:
            quarantine.append({"index": index, "reason": "missing_customer_id"})
            continue
        customer_id = str(customer_id).upper()
        name = _clean_scalar(raw.get("name"))
        name = str(name).title() if name is not None else None
        email = _clean_scalar(raw.get("email"))
        email = str(email).casefold() if email is not None and "@" in str(email) else None
        age_raw = _clean_scalar(raw.get("age"))
        try:
            age = int(age_raw) if age_raw is not None else None
        except (TypeError, ValueError):
            age = None
        if age is not None and not 0 <= age <= 120:
            age = None
        row = {"customer_id": customer_id, "name": name, "email": email, "age": age}
        missing_cells += sum(value is None for value in (name, email, age))
        if customer_id not in merged:
            merged[customer_id] = row
            continue
        duplicates += 1
        existing = merged[customer_id]
        for field in ("name", "email", "age"):
            if existing[field] is None and row[field] is not None:
                existing[field] = row[field]
    records = [merged[key] for key in sorted(merged)]
    return {
        "records": records,
        "quarantine": quarantine,
        "profile": {
            "input_rows": len(payload["records"]),
            "output_rows": len(records),
            "duplicate_rows": duplicates,
            "quarantined_rows": len(quarantine),
            "missing_cells": missing_cells,
        },
    }


_CLEAN_CASES = (
    TaskCaseData(
        "agent-case.clean-customers.public",
        "development",
        {
            "records": [
                {"customer_id": " a-1 ", "name": "  ADA  LOVELACE ", "email": "ADA@EXAMPLE.COM ", "age": "36"},
                {"customer_id": "A-1", "name": "N/A", "email": None, "age": None},
                {"customer_id": "b-2", "name": " grace hopper ", "email": "bad-email", "age": "121"},
                {"customer_id": "", "name": "orphan", "email": "o@example.com", "age": 20},
            ]
        },
        {},
        True,
        ("duplicates", "missingness"),
    ),
    TaskCaseData(
        "agent-case.clean-customers.holdout-a",
        "holdout",
        {
            "records": [
                {"customer_id": 7, "name": "  katherine   johnson", "email": "KJ@NASA.GOV", "age": 101},
                {"customer_id": "7", "name": None, "email": "none", "age": "bad"},
                {"customer_id": "8", "name": "dorothy vaughan", "email": "dv@nasa.gov", "age": 98},
            ]
        },
        {},
        False,
        ("numeric-id",),
    ),
    TaskCaseData(
        "agent-case.clean-customers.holdout-b",
        "stress",
        {
            "records": [
                {"customer_id": "x", "name": "   ", "email": "x@example.org", "age": -1},
                {"customer_id": "y", "name": "marie curie", "email": "Y@EXAMPLE.ORG", "age": 66},
                {"customer_id": None, "name": None, "email": None, "age": None},
            ]
        },
        {},
        False,
        ("boundary",),
    ),
)
_CLEAN_CASES = tuple(
    TaskCaseData(case.id, case.split, case.payload, solve_clean_customer_records(case.payload), case.candidate_readable, case.tags)
    for case in _CLEAN_CASES
)

CLEAN_CUSTOMER_RECORDS = make_bundle(
    task_id="agent-task.data-cleaning",
    title="Clean and deduplicate customer records",
    summary="Implement a deterministic, provenance-friendly customer-record cleaning pipeline.",
    instructions=(
        "Normalize whitespace and missing tokens; uppercase customer_id; title-case names; "
        "lowercase syntactically valid email addresses; coerce age to an integer in [0,120]; "
        "quarantine missing IDs; merge duplicates by keeping the first non-null value; sort by ID; "
        "and return exact row-accounting metrics. Do not use third-party packages."
    ),
    input_contract="A JSON object with records containing customer_id, name, email, and age.",
    output_contract="An object with canonical records, ordered quarantine entries, and an exact profile.",
    success_contract="All public and sealed cases match the independently computed canonical output exactly.",
    categories=("data.cleaning", "data.deduplication", "data.validation"),
    template_id="template.data-quality",
    stages=("Profile", "Normalize", "Validate", "Deduplicate", "Quarantine", "Report"),
    cases=_CLEAN_CASES,
    reference_solver=solve_clean_customer_records,
    allowed_imports=("re", "collections", "typing"),
)


def solve_conflict_validation(payload: dict[str, Any]) -> dict[str, Any]:
    precedence = {source: index for index, source in enumerate(payload["source_precedence"])}
    required = tuple(payload["required_fields"])
    records: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    for raw in payload["records"]:
        entity_id = str(raw["entity_id"])
        canonical: dict[str, Any] = {"entity_id": entity_id}
        provenance: dict[str, str] = {}
        entity_conflict = False
        for field in sorted(raw["claims"]):
            claims = raw["claims"][field]
            ranked = sorted(
                claims,
                key=lambda claim: (
                    precedence.get(claim["source"], len(precedence)),
                    str(claim["observed_at"]),
                    str(claim["value"]),
                ),
            )
            best_rank = precedence.get(ranked[0]["source"], len(precedence))
            leaders = [
                claim for claim in ranked
                if precedence.get(claim["source"], len(precedence)) == best_rank
            ]
            values = sorted({str(claim["value"]) for claim in leaders})
            if len(values) > 1:
                conflicts.append({"entity_id": entity_id, "field": field, "values": values})
                entity_conflict = True
                continue
            canonical[field] = leaders[-1]["value"]
            provenance[field] = leaders[-1]["source"]
        missing = sorted(field for field in required if field not in canonical)
        if missing or entity_conflict:
            quarantine.append(
                {
                    "entity_id": entity_id,
                    "reasons": (["conflicting_authoritative_claims"] if entity_conflict else [])
                    + (["missing_required:" + ",".join(missing)] if missing else []),
                }
            )
            continue
        canonical["provenance"] = provenance
        records.append(canonical)
    return {
        "records": sorted(records, key=lambda row: row["entity_id"]),
        "conflicts": sorted(conflicts, key=lambda row: (row["entity_id"], row["field"])),
        "quarantine": sorted(quarantine, key=lambda row: row["entity_id"]),
    }


_CONFLICT_CASES_RAW = (
    TaskCaseData(
        "agent-case.conflict-validation.public",
        "development",
        {
            "source_precedence": ["registry", "crm", "import"],
            "required_fields": ["name", "state"],
            "records": [
                {
                    "entity_id": "1",
                    "claims": {
                        "name": [
                            {"source": "import", "value": "Acme", "observed_at": "2026-01-01"},
                            {"source": "registry", "value": "ACME LLC", "observed_at": "2026-01-02"},
                        ],
                        "state": [{"source": "crm", "value": "NY", "observed_at": "2026-01-03"}],
                    },
                },
                {
                    "entity_id": "2",
                    "claims": {
                        "name": [
                            {"source": "registry", "value": "One", "observed_at": "2026-01-01"},
                            {"source": "registry", "value": "Two", "observed_at": "2026-01-02"},
                        ],
                        "state": [{"source": "crm", "value": "CA", "observed_at": "2026-01-03"}],
                    },
                },
            ],
        },
        {},
        True,
    ),
    TaskCaseData(
        "agent-case.conflict-validation.holdout-a",
        "holdout",
        {
            "source_precedence": ["authority", "warehouse", "feed"],
            "required_fields": ["status", "amount"],
            "records": [
                {
                    "entity_id": "A",
                    "claims": {
                        "status": [{"source": "authority", "value": "open", "observed_at": "2026-02-01"}],
                        "amount": [{"source": "warehouse", "value": 12, "observed_at": "2026-02-02"}],
                    },
                },
                {
                    "entity_id": "B",
                    "claims": {
                        "status": [{"source": "feed", "value": "closed", "observed_at": "2026-02-03"}],
                    },
                },
            ],
        },
        {},
        False,
    ),
    TaskCaseData(
        "agent-case.conflict-validation.holdout-b",
        "stress",
        {
            "source_precedence": ["p0", "p1"],
            "required_fields": ["value"],
            "records": [
                {
                    "entity_id": "Z",
                    "claims": {
                        "value": [
                            {"source": "p1", "value": 2, "observed_at": "2026-01-02"},
                            {"source": "p0", "value": 1, "observed_at": "2026-01-01"},
                        ]
                    },
                }
            ],
        },
        {},
        False,
    ),
)
_CONFLICT_CASES = tuple(
    TaskCaseData(case.id, case.split, case.payload, solve_conflict_validation(case.payload), case.candidate_readable, case.tags)
    for case in _CONFLICT_CASES_RAW
)

CONFLICT_VALIDATION = make_bundle(
    task_id="agent-task.data-conflict-validation",
    title="Resolve source claims without hiding conflicts",
    summary="Build a field-level source-precedence validator with provenance and quarantine.",
    instructions=(
        "For each field, select the highest-precedence source. If equally authoritative claims "
        "disagree, record the sorted values and quarantine the entity. Quarantine any entity "
        "missing required fields. Accepted records must retain field-to-source provenance."
    ),
    input_contract="Records contain entity IDs and field-level claims with source and observation time.",
    output_contract="Canonical records, explicit conflict facts, and reason-coded quarantine entries.",
    success_contract="No authoritative disagreement is silently collapsed and every required field is present.",
    categories=("data.validation", "data.reconciliation", "data.quarantine"),
    template_id="template.data-quality",
    stages=("Ingest claims", "Rank authority", "Detect conflict", "Validate", "Quarantine", "Publish provenance"),
    cases=_CONFLICT_CASES,
    reference_solver=solve_conflict_validation,
    allowed_imports=("collections", "typing"),
)


def _place_key(city: Any, state: Any, zip_code: Any) -> str:
    city_text = " ".join(str(city).strip().split()).casefold()
    state_text = str(state).strip().upper()
    digits = re.sub(r"\D", "", str(zip_code))[:5]
    return f"{city_text}|{state_text}|{digits}"


def solve_geotemporal_enrichment(payload: dict[str, Any]) -> dict[str, Any]:
    reference = {
        _place_key(row["city"], row["state"], row["zip"]): row
        for row in payload["place_reference"]
    }
    events = {
        (str(row["city"]).casefold(), str(row["state"]).upper(), row["date"]): row["name"]
        for row in payload["events"]
    }
    enriched: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    for raw in payload["rows"]:
        key = _place_key(raw.get("city", ""), raw.get("state", ""), raw.get("zip", ""))
        place = reference.get(key)
        if place is None:
            quarantine.append({"id": raw["id"], "reason": "unknown_place"})
            continue
        local = datetime.fromisoformat(raw["local_time"])
        offset = int(place["utc_offset_hours"])
        utc_value = (local - timedelta(hours=offset)).replace(tzinfo=timezone.utc)
        local_date = local.date().isoformat()
        event = events.get((str(place["city"]).casefold(), str(place["state"]).upper(), local_date))
        enriched.append(
            {
                "id": raw["id"],
                "city": place["city"],
                "state": str(place["state"]).upper(),
                "zip": re.sub(r"\D", "", str(place["zip"]))[:5],
                "latitude": float(place["latitude"]),
                "longitude": float(place["longitude"]),
                "local_date": local_date,
                "day_of_week": local.strftime("%A"),
                "utc_time": utc_value.isoformat().replace("+00:00", "Z"),
                "event": event,
                "authority": "fixture.place-reference@1",
            }
        )
    return {"enriched": enriched, "quarantine": quarantine}


_GEO_BASE = {
    "place_reference": [
        {"city": "New York", "state": "NY", "zip": "10001", "latitude": 40.7506, "longitude": -73.9972, "utc_offset_hours": -4},
        {"city": "Chicago", "state": "IL", "zip": "60601", "latitude": 41.8864, "longitude": -87.6186, "utc_offset_hours": -5},
        {"city": "Los Angeles", "state": "CA", "zip": "90012", "latitude": 34.0614, "longitude": -118.2395, "utc_offset_hours": -7},
    ],
    "events": [
        {"city": "New York", "state": "NY", "date": "2026-07-04", "name": "Independence Day event"},
        {"city": "Chicago", "state": "IL", "date": "2026-10-11", "name": "Marathon"},
    ],
}
_GEO_CASES_RAW = (
    TaskCaseData(
        "agent-case.geotemporal.public",
        "development",
        {**_GEO_BASE, "rows": [
            {"id": "n1", "city": " new   york ", "state": "ny", "zip": "10001-1234", "local_time": "2026-07-04T20:30:00"},
            {"id": "bad", "city": "Atlantis", "state": "ZZ", "zip": "00000", "local_time": "2026-07-04T10:00:00"},
        ]},
        {},
        True,
    ),
    TaskCaseData(
        "agent-case.geotemporal.holdout-a",
        "holdout",
        {**_GEO_BASE, "rows": [
            {"id": "c1", "city": "Chicago", "state": "il", "zip": 60601, "local_time": "2026-10-11T07:45:00"},
        ]},
        {},
        False,
    ),
    TaskCaseData(
        "agent-case.geotemporal.holdout-b",
        "stress",
        {**_GEO_BASE, "rows": [
            {"id": "l1", "city": "los angeles", "state": "CA", "zip": "90012", "local_time": "2026-12-31T23:30:00"},
        ]},
        {},
        False,
    ),
)
_GEO_CASES = tuple(
    TaskCaseData(case.id, case.split, case.payload, solve_geotemporal_enrichment(case.payload), case.candidate_readable, case.tags)
    for case in _GEO_CASES_RAW
)

GEOTEMPORAL_ENRICHMENT = make_bundle(
    task_id="agent-task.geotemporal-enrichment",
    title="Enrich place and local-time records",
    summary="Join an explicit offline place authority with local time and event context.",
    instructions=(
        "Normalize city/state/ZIP, require an exact reference-table match, preserve fixture authority, "
        "derive local date/day name and UTC from the supplied fixed offset, join a same-city/local-date "
        "event when present, and quarantine unknown places. Do not call a network service."
    ),
    input_contract="Rows plus explicit place and event reference tables; local_time is naive local ISO-8601.",
    output_contract="Ordered enriched rows with geographic, UTC, calendar, event, and authority fields plus quarantine.",
    success_contract="Every accepted row matches the supplied authority and all derived times are exact.",
    categories=("data.enrichment", "geospatial.enrichment", "time.enrichment"),
    template_id="template.geospatial-analytics",
    stages=("Normalize place", "Verify reference", "Resolve offset", "Derive calendar", "Join event", "Publish provenance"),
    cases=_GEO_CASES,
    reference_solver=solve_geotemporal_enrichment,
    allowed_imports=("datetime", "re", "typing"),
    extra_context_sources=("ENGINEERING_DAG_AND_DUECARE_HARNESS_SHOWCASE.md",),
    limitations=("Fixed UTC offsets are fixture data and do not replace a versioned timezone database.",),
)


DATA_TASKS = (CLEAN_CUSTOMER_RECORDS, CONFLICT_VALIDATION, GEOTEMPORAL_ENRICHMENT)

__all__ = [
    "CLEAN_CUSTOMER_RECORDS",
    "CONFLICT_VALIDATION",
    "DATA_TASKS",
    "GEOTEMPORAL_ENRICHMENT",
    "solve_clean_customer_records",
    "solve_conflict_validation",
    "solve_geotemporal_enrichment",
]
