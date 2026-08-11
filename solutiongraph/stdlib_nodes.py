"""Dependency-free, reusable data and text primitives for SolutionGraph packs."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

from solutiongraph.model import canonical_json


def identity_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copy a JSON-record collection without changing its values."""
    return [dict(record) for record in records]


def normalize_unicode(text: str, form: str = "NFKC") -> str:
    """Normalize Unicode with one explicitly selected standard form."""
    if form not in {"NFC", "NFKC"}:
        raise ValueError("form must be NFC or NFKC")
    return unicodedata.normalize(form, text)


def normalize_whitespace(text: str, mode: str = "lines") -> str:
    """Normalize whitespace while either preserving or collapsing line records."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if mode == "lines":
        return "\n".join(
            " ".join(line.split()) for line in normalized.split("\n") if line.strip()
        )
    if mode == "compact":
        return " ".join(normalized.split())
    raise ValueError("mode must be lines or compact")


def strip_control_characters(text: str, preserve_newlines: bool = True) -> str:
    """Remove Unicode control characters with an explicit newline policy."""
    preserved = {"\n", "\t"} if preserve_newlines else set()
    return "".join(
        character
        for character in text
        if character in preserved or unicodedata.category(character) != "Cc"
    )


def parse_json_value(text: str) -> Any:
    """Parse strict JSON without repair or coercion."""
    return json.loads(text)


def parse_json_lines(text: str) -> list[dict[str, Any]]:
    """Parse nonempty JSON Lines records and require object-shaped rows."""
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, Mapping):
            raise TypeError(f"JSON Lines row {line_number} is not an object")
        records.append(dict(value))
    return records


def parse_delimited_records(text: str, delimiter: str = ",") -> list[dict[str, str]]:
    """Parse CSV/TSV-like text through the standard-library CSV state machine."""
    if delimiter not in {",", ";", "\t"}:
        raise ValueError("delimiter must be comma, semicolon, or tab")
    return [dict(row) for row in csv.DictReader(io.StringIO(text), delimiter=delimiter)]


def _key(value: str, mode: str) -> str:
    lowered = value.strip().lower()
    if mode == "lower":
        return lowered
    if mode == "snake":
        return re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    raise ValueError("mode must be lower or snake")


def normalize_record_keys(
    records: list[dict[str, Any]], mode: str = "snake"
) -> list[dict[str, Any]]:
    """Normalize top-level record keys and reject collisions after normalization."""
    normalized: list[dict[str, Any]] = []
    for row_number, record in enumerate(records, start=1):
        item: dict[str, Any] = {}
        for raw_key, value in record.items():
            key = _key(str(raw_key), mode)
            if key in item:
                raise ValueError(
                    f"record {row_number} has a key collision after {mode} normalization"
                )
            item[key] = value
        normalized.append(item)
    return normalized


def _trim(value: Any, recursive: bool) -> Any:
    if isinstance(value, str):
        return value.strip()
    if recursive and isinstance(value, list):
        return [_trim(item, True) for item in value]
    if recursive and isinstance(value, Mapping):
        return {str(key): _trim(item, True) for key, item in value.items()}
    return value


def trim_record_strings(
    records: list[dict[str, Any]], recursive: bool = False
) -> list[dict[str, Any]]:
    """Trim string fields with an explicit shallow or recursive policy."""
    return [
        {str(key): _trim(value, recursive) for key, value in record.items()}
        for record in records
    ]


def normalize_missing_values(
    records: list[dict[str, Any]],
    sentinels: Sequence[str] = ("", "na", "n/a", "null", "none"),
) -> list[dict[str, Any]]:
    """Map configured case-insensitive string sentinels to JSON null."""
    normalized_sentinels = {str(value).strip().casefold() for value in sentinels}
    return [
        {
            str(key): (
                None
                if isinstance(value, str)
                and value.strip().casefold() in normalized_sentinels
                else value
            )
            for key, value in record.items()
        }
        for record in records
    ]


def casefold_record_fields(
    records: list[dict[str, Any]], fields: Sequence[str]
) -> list[dict[str, Any]]:
    """Case-fold only explicitly named top-level string fields."""
    selected = {str(field) for field in fields}
    return [
        {
            str(key): value.casefold()
            if key in selected and isinstance(value, str)
            else value
            for key, value in record.items()
        }
        for record in records
    ]


def project_record_fields(
    records: list[dict[str, Any]], fields: Sequence[str]
) -> list[dict[str, Any]]:
    """Project records to an ordered configured set of fields."""
    selected = tuple(str(field) for field in fields)
    return [{field: record.get(field) for field in selected} for record in records]


def require_record_fields(
    records: list[dict[str, Any]], fields: Sequence[str]
) -> list[dict[str, Any]]:
    """Require configured fields to exist and contain non-null, nonempty values."""
    required = tuple(str(field) for field in fields)
    for row_number, record in enumerate(records, start=1):
        missing = [
            field
            for field in required
            if field not in record or record[field] is None or record[field] == ""
        ]
        if missing:
            raise ValueError(
                f"record {row_number} is missing required fields: {', '.join(missing)}"
            )
    return [dict(record) for record in records]


def filter_complete_records(
    records: list[dict[str, Any]], fields: Sequence[str]
) -> list[dict[str, Any]]:
    """Keep only records with non-null, nonempty configured fields."""
    required = tuple(str(field) for field in fields)
    return [
        dict(record)
        for record in records
        if all(
            field in record and record[field] is not None and record[field] != ""
            for field in required
        )
    ]


def _canonical_component(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return re.sub(r"[^a-z0-9]+", "", value.casefold())
    return canonical_json(value)


def deduplicate_records(
    records: list[dict[str, Any]],
    key_fields: Sequence[str],
    canonical: bool = False,
) -> list[dict[str, Any]]:
    """Keep first occurrence by exact or canonicalized configured key fields."""
    fields = tuple(str(field) for field in key_fields)
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []
    for record in records:
        key = tuple(
            _canonical_component(record.get(field))
            if canonical
            else canonical_json(record.get(field))
            for field in fields
        )
        if key not in seen:
            seen.add(key)
            result.append(dict(record))
    return result


def sort_records(
    records: list[dict[str, Any]], fields: Sequence[str], reverse: bool = False
) -> list[dict[str, Any]]:
    """Sort records deterministically by canonicalized configured field values."""
    selected = tuple(str(field) for field in fields)
    return sorted(
        (dict(record) for record in records),
        key=lambda record: tuple(canonical_json(record.get(field)) for field in selected),
        reverse=reverse,
    )


def profile_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute small deterministic completeness and schema observations."""
    fields = sorted({str(key) for record in records for key in record})
    missing_by_field = {
        field: sum(
            field not in record or record[field] is None or record[field] == ""
            for record in records
        )
        for field in fields
    }
    return {
        "row_count": len(records),
        "fields": fields,
        "missing_by_field": missing_by_field,
        "missing_count": sum(missing_by_field.values()),
    }


def hash_records(records: list[dict[str, Any]]) -> str:
    """Return a stable sha256 identity for the exact ordered records."""
    payload = canonical_json(records).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def emit_records_with_profile(
    records: list[dict[str, Any]], include_digest: bool = True
) -> dict[str, Any]:
    """Emit cleaned records and a deterministic quality profile together."""
    profile = profile_records(records)
    if include_digest:
        profile["records_digest"] = hash_records(records)
    return {"records": [dict(record) for record in records], "profile": profile}


__all__ = [
    "casefold_record_fields",
    "deduplicate_records",
    "emit_records_with_profile",
    "filter_complete_records",
    "hash_records",
    "identity_records",
    "normalize_missing_values",
    "normalize_record_keys",
    "normalize_unicode",
    "normalize_whitespace",
    "parse_delimited_records",
    "parse_json_lines",
    "parse_json_value",
    "profile_records",
    "project_record_fields",
    "require_record_fields",
    "sort_records",
    "strip_control_characters",
    "trim_record_strings",
]
