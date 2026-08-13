"""Dependency-free aggregate profiling and conservative semantic field mapping."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Any

from solutiongraph.interrogation.model import (
    ConceptDefinition,
    DatasetProfile,
    FieldConceptMatch,
    FieldProfile,
    SemanticFieldMap,
)
from solutiongraph.model import canonical_json, sha256_digest

PLACEHOLDER_VALUES = frozenset(
    {
        "",
        "-",
        "--",
        "?",
        "n/a",
        "na",
        "none",
        "null",
        "nil",
        "not available",
        "not applicable",
        "unknown",
        "unk",
        "missing",
        "placeholder",
        "test",
        "tbd",
        "xxx",
    }
)


def records_digest(records: Sequence[Mapping[str, Any]]) -> str:
    """Hash the complete ordered JSON-compatible record collection."""
    portable = [dict(record) for record in records]
    canonical_json(portable)
    return sha256_digest(portable)


def _missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and value != value:
        return True
    return isinstance(value, str) and not value.strip()


def _placeholder(value: Any) -> bool:
    return isinstance(value, str) and value.strip().casefold() in PLACEHOLDER_VALUES


def _inferred_type(values: Sequence[Any]) -> str:
    observed = [value for value in values if not _missing(value)]
    if not observed:
        return "data.unknown"
    if all(isinstance(value, bool) for value in observed):
        return "data.boolean"
    if all(
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and isfinite(float(value))
        for value in observed
    ):
        return "data.number"
    if all(isinstance(value, str) for value in observed):
        return "data.text"
    if all(isinstance(value, Mapping) for value in observed):
        return "data.object"
    if all(isinstance(value, (list, tuple)) for value in observed):
        return "data.array"
    return "data.mixed"


def profile_records(
    records: Sequence[Mapping[str, Any]],
    *,
    source_id: str = "source.inline-records",
    sample_limit: int = 0,
    top_value_limit: int = 5,
) -> DatasetProfile:
    """Create an aggregate-only profile; raw sample values are never retained."""
    if sample_limit < 0:
        raise ValueError("sample_limit must be non-negative")
    if top_value_limit < 0:
        raise ValueError("top_value_limit must be non-negative")
    portable = [dict(record) for record in records]
    dataset_digest = records_digest(portable)
    columns: list[str] = []
    seen_columns: set[str] = set()
    for record in portable:
        for key in record:
            if not isinstance(key, str) or not key.strip():
                raise ValueError("record keys must be nonempty strings")
            if key not in seen_columns:
                seen_columns.add(key)
                columns.append(key)
    sample = portable if sample_limit == 0 else portable[:sample_limit]
    field_profiles: list[FieldProfile] = []
    for field_name in columns:
        values = [record.get(field_name) for record in sample]
        non_missing = [value for value in values if not _missing(value)]
        serialized = [canonical_json(value) for value in non_missing]
        counts = Counter(serialized)
        text_values = [value for value in non_missing if isinstance(value, str)]
        lengths = [len(value) for value in text_values]
        numeric_count = sum(
            1
            for value in non_missing
            if not isinstance(value, bool)
            and isinstance(value, (int, float))
            and isfinite(float(value))
        )
        top_hashes = tuple(
            (sha256_digest(value), count)
            for value, count in sorted(
                counts.items(), key=lambda item: (-item[1], item[0])
            )[:top_value_limit]
        )
        field_profiles.append(
            FieldProfile(
                field_name=field_name,
                inferred_type=_inferred_type(values),
                row_count=len(sample),
                non_missing_count=len(non_missing),
                distinct_count=len(counts),
                missing_fraction=(
                    (len(sample) - len(non_missing)) / len(sample) if sample else 0.0
                ),
                placeholder_count=sum(_placeholder(value) for value in values),
                control_character_count=sum(
                    1
                    for value in text_values
                    if any(
                        unicodedata.category(character).startswith("C")
                        and character not in "\n\r\t"
                        for character in value
                    )
                ),
                non_nfc_count=sum(
                    unicodedata.normalize("NFC", value) != value for value in text_values
                ),
                leading_or_trailing_space_count=sum(
                    value != value.strip() for value in text_values
                ),
                min_length=min(lengths) if lengths else None,
                max_length=max(lengths) if lengths else None,
                numeric_fraction=(numeric_count / len(non_missing) if non_missing else 0.0),
                top_value_hashes=top_hashes,
            )
        )
    row_hashes = Counter(canonical_json(record) for record in sample)
    duplicate_rows = sum(count - 1 for count in row_hashes.values() if count > 1)
    warnings = ()
    if sample_limit and len(portable) > sample_limit:
        warnings = (
            f"Profile statistics use the first {sample_limit} rows of {len(portable)}; "
            "the dataset digest still covers every row.",
        )
    result = DatasetProfile(
        dataset_digest=dataset_digest,
        source_id=source_id,
        row_count=len(portable),
        column_names=tuple(columns),
        fields=tuple(field_profiles),
        duplicate_row_count=duplicate_rows,
        sampled_row_count=len(sample),
        warnings=warnings,
        extensions=(("profile.raw-values-retained", False),),
    )
    problems = result.validate()
    if problems:
        raise ValueError("invalid dataset profile: " + "; ".join(problems))
    return result


def normalize_field_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def _context_tokens(field_names: Sequence[str]) -> set[str]:
    return {
        token
        for field_name in field_names
        for token in normalize_field_name(field_name).split("_")
        if token
    }


def map_semantic_fields(
    profile: DatasetProfile,
    concepts: Sequence[ConceptDefinition],
    *,
    strategy: str = "conservative",
    explicit_hints: Mapping[str, str] | None = None,
) -> SemanticFieldMap:
    """Map field names to concepts without reading field values or granting validity."""
    if strategy not in ("exact", "conservative", "broad"):
        raise ValueError("strategy must be exact, conservative, or broad")
    concept_by_id = {concept.id: concept for concept in concepts}
    hints = dict(explicit_hints or {})
    unknown_hints = sorted(set(hints.values()) - set(concept_by_id))
    if unknown_hints:
        raise ValueError("explicit hints reference unknown concepts: " + ", ".join(unknown_hints))
    aliases: dict[str, list[ConceptDefinition]] = {}
    for concept in concepts:
        for alias in concept.aliases:
            aliases.setdefault(normalize_field_name(alias), []).append(concept)
    context = _context_tokens(profile.column_names)
    matches: list[FieldConceptMatch] = []
    unmapped: list[str] = []
    warnings: list[str] = []
    for field_name in profile.column_names:
        if field_name in hints:
            matches.append(
                FieldConceptMatch(
                    field_name,
                    hints[field_name],
                    1.0,
                    "mapping.explicit-hint",
                    evidence=("caller supplied an explicit concept binding",),
                )
            )
            continue
        normalized = normalize_field_name(field_name)
        candidates: dict[str, tuple[float, str]] = {}
        for concept in aliases.get(normalized, ()):  # exact alias
            candidates[concept.id] = (0.98, f"exact alias: {normalized}")
        if strategy in ("conservative", "broad"):
            field_tokens = set(normalized.split("_"))
            for alias, alias_concepts in aliases.items():
                alias_tokens = set(alias.split("_"))
                if not alias_tokens:
                    continue
                if alias_tokens <= field_tokens or field_tokens <= alias_tokens:
                    base = 0.78 if alias_tokens <= field_tokens else 0.70
                    for concept in alias_concepts:
                        current = candidates.get(concept.id, (0.0, ""))
                        if base > current[0]:
                            candidates[concept.id] = (base, f"token alias: {alias}")
        if strategy == "broad":
            for alias, alias_concepts in aliases.items():
                if alias in normalized or normalized in alias:
                    for concept in alias_concepts:
                        current = candidates.get(concept.id, (0.0, ""))
                        if 0.58 > current[0]:
                            candidates[concept.id] = (0.58, f"substring alias: {alias}")
        adjusted: list[tuple[float, str, str]] = []
        for concept_id, (score, evidence) in candidates.items():
            if concept_id.startswith("concept.product") and {"product", "sku", "item"} & context:
                score += 0.08
            if concept_id.startswith("concept.organization") and {
                "company", "organization", "business", "vendor", "employer"
            } & context:
                score += 0.08
            if concept_id.startswith("concept.person") and {
                "person", "customer", "contact", "employee"
            } & context:
                score += 0.05
            adjusted.append((min(score, 1.0), concept_id, evidence))
        adjusted.sort(key=lambda item: (-item[0], item[1]))
        if not adjusted or adjusted[0][0] < (0.65 if strategy != "broad" else 0.55):
            unmapped.append(field_name)
            continue
        best_score, best_id, evidence = adjusted[0]
        alternatives = tuple(item[1] for item in adjusted[1:4] if item[0] >= best_score - 0.15)
        if alternatives:
            warnings.append(
                f"{field_name!r} maps to {best_id} with alternatives: {', '.join(alternatives)}"
            )
        matches.append(
            FieldConceptMatch(
                field_name=field_name,
                concept_id=best_id,
                confidence=best_score,
                method=f"mapping.{strategy}",
                alternatives=alternatives,
                evidence=(evidence,),
            )
        )
    result = SemanticFieldMap(
        dataset_digest=profile.dataset_digest,
        mapping_policy_id=f"mapping.{strategy}",
        matches=tuple(matches),
        unmapped_fields=tuple(unmapped),
        warnings=tuple(warnings),
        extensions=(("mapping.uses-field-values", False),),
    )
    problems = result.validate()
    if problems:
        raise ValueError("invalid semantic field map: " + "; ".join(problems))
    return result


__all__ = [
    "PLACEHOLDER_VALUES",
    "map_semantic_fields",
    "normalize_field_name",
    "profile_records",
    "records_digest",
]
