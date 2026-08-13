"""Small dependency-free dataset readers for the interrogation CLI."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def _record_list(value: Any, *, source: Path) -> list[dict[str, Any]]:
    if isinstance(value, dict) and "records" in value:
        value = value["records"]
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{source} must contain a JSON array of objects or a records array")
    return [dict(item) for item in value]


def load_records(path: str | Path) -> list[dict[str, Any]]:
    """Read JSON, JSONL/NDJSON, CSV, or TSV records without type guessing."""
    source = Path(path)
    suffix = source.suffix.casefold()
    if suffix == ".json":
        return _record_list(json.loads(source.read_text(encoding="utf-8")), source=source)
    if suffix in (".jsonl", ".ndjson"):
        records: list[dict[str, Any]] = []
        for line_number, line in enumerate(
            source.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{source}:{line_number} must be a JSON object")
            records.append(dict(value))
        return records
    if suffix in (".csv", ".tsv"):
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t" if suffix == ".tsv" else ",")
            if not reader.fieldnames:
                raise ValueError(f"{source} has no header row")
            return [dict(row) for row in reader]
    raise ValueError("dataset must use .json, .jsonl, .ndjson, .csv, or .tsv")


__all__ = ["load_records"]
