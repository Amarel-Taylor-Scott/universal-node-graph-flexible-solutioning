"""Check-adapter registry and dependency-free interrogation executor."""

from __future__ import annotations

import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from time import perf_counter
from typing import Any, Protocol
from urllib.parse import urlparse

from solutiongraph.executor import callable_implementation_digest
from solutiongraph.interrogation.model import (
    DatasetProfile,
    Finding,
    FindingSet,
    QuestionDefinition,
    QuestionPlan,
    QuestionReceipt,
    SemanticFieldMap,
)
from solutiongraph.interrogation.profiling import PLACEHOLDER_VALUES, records_digest
from solutiongraph.model import ID_RE, canonical_json, sha256_digest


@dataclass(frozen=True)
class CheckObservation:
    outcome: str
    affected_row_ids: tuple[str, ...] = ()
    affected_count: int = 0
    fields: tuple[str, ...] = ()
    evidence: tuple[tuple[str, Any], ...] = ()
    sample_value_digests: tuple[str, ...] = ()
    summary: str = ""
    confidence: float = 1.0
    error_code: str = ""


class CheckAdapter(Protocol):
    id: str
    version: str
    implementation_digest: str
    capability: str
    mode: str

    def run(
        self,
        records: Sequence[Mapping[str, Any]],
        fields: tuple[str, ...],
        question: QuestionDefinition,
        profile: DatasetProfile,
        field_map: SemanticFieldMap,
    ) -> CheckObservation: ...


CheckFunction = Callable[
    [Sequence[Mapping[str, Any]], tuple[str, ...], QuestionDefinition, DatasetProfile, SemanticFieldMap],
    CheckObservation,
]


@dataclass(frozen=True)
class CallableCheckAdapter:
    id: str
    version: str
    capability: str
    function: CheckFunction
    mode: str = "deterministic"

    @property
    def implementation_digest(self) -> str:
        return callable_implementation_digest(self.function)

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not ID_RE.fullmatch(self.capability):
            problems.append("check adapter id and capability must be namespaced identifiers")
        if not self.version.strip() or self.mode not in ("deterministic", "external", "llm", "human"):
            problems.append("check adapter version and mode must be valid")
        return problems

    def run(
        self,
        records: Sequence[Mapping[str, Any]],
        fields: tuple[str, ...],
        question: QuestionDefinition,
        profile: DatasetProfile,
        field_map: SemanticFieldMap,
    ) -> CheckObservation:
        return self.function(records, fields, question, profile, field_map)


@dataclass(frozen=True)
class CheckRegistry:
    id: str
    version: str
    adapters: tuple[CallableCheckAdapter, ...]

    @property
    def digest(self) -> str:
        return sha256_digest(
            {
                "id": self.id,
                "version": self.version,
                "adapters": [
                    {
                        "id": item.id,
                        "version": item.version,
                        "capability": item.capability,
                        "mode": item.mode,
                        "implementation_digest": item.implementation_digest,
                    }
                    for item in self.adapters
                ],
            }
        )

    @property
    def capabilities(self) -> tuple[str, ...]:
        return tuple(adapter.capability for adapter in self.adapters)

    def get(self, capability: str) -> CallableCheckAdapter | None:
        return next((item for item in self.adapters if item.capability == capability), None)

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.id) or not self.version.strip():
            problems.append("check registry id and version must be valid")
        capabilities = self.capabilities
        if len(capabilities) != len(set(capabilities)):
            problems.append("check registry capabilities must be unique")
        for adapter in self.adapters:
            problems.extend(adapter.validate())
        return problems


def _row_id(index: int, record: Mapping[str, Any]) -> str:
    explicit = next(
        (record[key] for key in ("record_id", "row_id", "id") if key in record),
        None,
    )
    identity = {"index": index, "explicit": explicit, "record": dict(record)}
    return "row." + sha256_digest(identity).removeprefix("sha256:")


def _missing(value: Any) -> bool:
    return value is None or (isinstance(value, float) and value != value) or (
        isinstance(value, str) and not value.strip()
    )


def _values(
    records: Sequence[Mapping[str, Any]], fields: tuple[str, ...]
) -> list[tuple[int, str, Any]]:
    return [
        (index, field, record.get(field))
        for index, record in enumerate(records)
        for field in fields
        if field in record
    ]


def _observation(
    records: Sequence[Mapping[str, Any]],
    affected: Sequence[tuple[int, str, Any]],
    *,
    summary: str,
    evidence: tuple[tuple[str, Any], ...] = (),
    confidence: float = 1.0,
) -> CheckObservation:
    rows = tuple(dict.fromkeys(_row_id(index, records[index]) for index, _, _ in affected))
    fields = tuple(dict.fromkeys(field for _, field, _ in affected))
    sample_digests = tuple(
        dict.fromkeys(sha256_digest(value) for _, _, value in affected[:5])
    )
    count = len(affected)
    return CheckObservation(
        outcome="fail" if affected else "pass",
        affected_row_ids=rows[:100],
        affected_count=count,
        fields=fields,
        evidence=(("evidence.affected-count", count), *evidence),
        sample_value_digests=sample_digests,
        summary=summary,
        confidence=confidence,
    )


def check_placeholders(records, fields, question, profile, field_map) -> CheckObservation:
    affected = [
        item
        for item in _values(records, fields)
        if _missing(item[2])
        or (isinstance(item[2], str) and item[2].strip().casefold() in PLACEHOLDER_VALUES)
    ]
    return _observation(records, affected, summary="Missing or placeholder values were detected.")


def check_unicode_controls(records, fields, question, profile, field_map) -> CheckObservation:
    affected = []
    for item in _values(records, fields):
        value = item[2]
        if not isinstance(value, str):
            continue
        controls = any(
            unicodedata.category(character).startswith("C") and character not in "\n\r\t"
            for character in value
        )
        if controls or unicodedata.normalize("NFC", value) != value:
            affected.append(item)
    return _observation(
        records, affected, summary="Unicode normalization or control-character anomalies were detected."
    )


def check_whitespace(records, fields, question, profile, field_map) -> CheckObservation:
    repeated = re.compile(r"[ \t]{2,}")
    affected = [
        item
        for item in _values(records, fields)
        if isinstance(item[2], str)
        and (item[2] != item[2].strip() or repeated.search(item[2]))
    ]
    return _observation(records, affected, summary="Whitespace anomalies were detected.")


def check_punctuation(records, fields, question, profile, field_map) -> CheckObservation:
    edge = re.compile(r"^[^\w\s#&+]+|[^\w\s.)&+#]+$")
    repeated = re.compile(r"([^\w\s])\1{2,}")
    affected = [
        item
        for item in _values(records, fields)
        if isinstance(item[2], str) and (edge.search(item[2].strip()) or repeated.search(item[2]))
    ]
    return _observation(records, affected, summary="Unexpected edge or repeated punctuation was detected.")


def check_type_conformance(records, fields, question, profile, field_map) -> CheckObservation:
    affected = []
    expected = {item.field_name: item.inferred_type for item in profile.fields}
    for item in _values(records, fields):
        index, field, value = item
        if _missing(value):
            continue
        expected_type = expected.get(field)
        valid = True
        if expected_type == "data.number":
            valid = not isinstance(value, bool) and isinstance(value, (int, float))
        elif expected_type == "data.boolean":
            valid = isinstance(value, bool)
        elif expected_type == "data.text":
            valid = isinstance(value, str)
        elif expected_type == "data.object":
            valid = isinstance(value, Mapping)
        elif expected_type == "data.array":
            valid = isinstance(value, (list, tuple))
        if not valid:
            affected.append((index, field, value))
    return _observation(records, affected, summary="Values conflict with the observed field type.")


def check_duplicate_records(records, fields, question, profile, field_map) -> CheckObservation:
    seen: dict[str, int] = {}
    affected = []
    for index, record in enumerate(records):
        digest = sha256_digest(dict(record))
        if digest in seen:
            affected.append((index, "__record__", digest))
        else:
            seen[digest] = index
    return _observation(records, affected, summary="Exact duplicate records were detected.")


def check_identifier_uniqueness(records, fields, question, profile, field_map) -> CheckObservation:
    affected = []
    for field in fields:
        seen: dict[str, int] = {}
        for index, record in enumerate(records):
            value = record.get(field)
            if _missing(value):
                continue
            key = canonical_json(value)
            if key in seen:
                affected.append((index, field, value))
            else:
                seen[key] = index
    return _observation(records, affected, summary="Duplicate values were found in identifier fields.")


def check_cardinality(records, fields, question, profile, field_map) -> CheckObservation:
    affected = []
    evidence: list[tuple[str, Any]] = []
    for field in fields:
        values = [record.get(field) for record in records if not _missing(record.get(field))]
        if not values:
            continue
        counts = Counter(canonical_json(value) for value in values)
        dominant = max(counts.values()) / len(values)
        if len(counts) == 1 or (len(values) >= 10 and dominant >= 0.95):
            affected.append((0, field, next(iter(counts))))
            field_token = re.sub(r"[^a-z0-9-]+", "-", field.casefold()).strip("-")
            evidence.append((f"evidence.modal-share-{field_token or 'field'}", dominant))
    return _observation(
        records, affected, summary="Suspiciously low cardinality or modal dominance was detected.",
        evidence=tuple(evidence),
    )


def check_numeric_outliers(records, fields, question, profile, field_map) -> CheckObservation:
    affected = []
    for field in fields:
        numeric = [
            (index, float(record[field]))
            for index, record in enumerate(records)
            if field in record
            and not isinstance(record[field], bool)
            and isinstance(record[field], (int, float))
            and isfinite(float(record[field]))
        ]
        if len(numeric) < 8:
            continue
        values = sorted(value for _, value in numeric)
        quartiles = statistics.quantiles(values, n=4, method="inclusive")
        low, high = quartiles[0], quartiles[2]
        iqr = high - low
        if iqr <= 0:
            continue
        lower, upper = low - 3 * iqr, high + 3 * iqr
        affected.extend(
            (index, field, value) for index, value in numeric if value < lower or value > upper
        )
    return _observation(records, affected, summary="Robust IQR outliers were detected.", confidence=0.85)


def check_case_pattern(records, fields, question, profile, field_map) -> CheckObservation:
    affected = []
    for item in _values(records, fields):
        value = item[2]
        if not isinstance(value, str) or len(value) < 4 or not any(ch.isalpha() for ch in value):
            continue
        if value.isupper() or value.islower():
            affected.append(item)
    return _observation(
        records, affected, summary="All-upper or all-lower casing requires branding review.", confidence=0.60
    )


_ORG_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "llc", "l.l.c",
    "llp", "l.l.p", "lp", "l.p", "ltd", "limited", "plc", "gmbh", "ag", "sa", "s.a",
    "bv", "b.v", "nv", "n.v", "pte", "pty", "oy", "ab", "sas", "sarl",
}


def check_organization_suffix(records, fields, question, profile, field_map) -> CheckObservation:
    affected = []
    suffix_like = re.compile(r"\b([a-z][a-z.]{1,15})[,.]?$", re.IGNORECASE)
    for item in _values(records, fields):
        value = item[2]
        if not isinstance(value, str):
            continue
        match = suffix_like.search(value.strip())
        if not match:
            continue
        token = match.group(1).casefold().rstrip(".")
        looks_legal = token.startswith(("ll", "inc", "corp", "ltd", "plc"))
        if looks_legal and token not in _ORG_SUFFIXES:
            affected.append(item)
    return _observation(
        records, affected,
        summary="Unrecognized legal-suffix-like tokens require jurisdictional review.",
        confidence=0.70,
    )


def _org_key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    tokens = re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKC", value).casefold())
    while tokens and tokens[-1] in _ORG_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def check_organization_duplicates(records, fields, question, profile, field_map) -> CheckObservation:
    affected = []
    seen: dict[str, int] = {}
    for index, record in enumerate(records):
        values = [_org_key(record.get(field)) for field in fields]
        key = next((value for value in values if value), "")
        if not key:
            continue
        if key in seen:
            affected.append((index, fields[0], key))
        else:
            seen[key] = index
    return _observation(records, affected, summary="Names collapse to duplicate conservative comparison keys.")


def check_organization_domain(records, fields, question, profile, field_map) -> CheckObservation:
    domain_fields = field_map.fields_for(("concept.organization.domain",))
    email_fields = field_map.fields_for(("concept.contact.email",))
    affected = []
    for index, record in enumerate(records):
        domains = {
            urlparse(str(record.get(field, "")) if "://" in str(record.get(field, "")) else "//" + str(record.get(field, ""))).hostname
            for field in domain_fields
            if record.get(field)
        }
        domains.discard(None)
        for field in email_fields:
            email = str(record.get(field, ""))
            if "@" not in email or not domains:
                continue
            email_domain = email.rsplit("@", 1)[1].casefold().rstrip(".")
            if not any(email_domain == domain or email_domain.endswith("." + str(domain)) for domain in domains):
                affected.append((index, field, email_domain))
    return _observation(
        records, affected, summary="Email and organization domains disagree; this is a clue, not identity proof.",
        confidence=0.65,
    )


def check_address_components(records, fields, question, profile, field_map) -> CheckObservation:
    country_fields = field_map.fields_for(("concept.postal.country",))
    street_fields = field_map.fields_for(("concept.postal.street", "concept.postal.address"))
    locality_fields = field_map.fields_for(("concept.postal.city",))
    code_fields = field_map.fields_for(("concept.postal.code",))
    affected = []
    for index, record in enumerate(records):
        has_any = any(not _missing(record.get(field)) for field in fields)
        if not has_any:
            continue
        country = next((str(record.get(field, "")).strip().upper() for field in country_fields if record.get(field)), "")
        required = (*street_fields, *locality_fields, *code_fields)
        if country in ("US", "USA", "UNITED STATES") and any(_missing(record.get(field)) for field in required):
            affected.append((index, "__address__", "missing-us-component"))
        elif not country and not street_fields:
            affected.append((index, "__address__", "missing-country-and-street"))
    return _observation(records, affected, summary="Address components required by the local policy are missing.")


_POSTAL_PATTERNS = {
    "US": re.compile(r"^\d{5}(?:-\d{4})?$"),
    "USA": re.compile(r"^\d{5}(?:-\d{4})?$"),
    "CA": re.compile(r"^[A-Z]\d[A-Z][ -]?\d[A-Z]\d$", re.IGNORECASE),
    "GB": re.compile(r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$", re.IGNORECASE),
}


def check_postal_format(records, fields, question, profile, field_map) -> CheckObservation:
    code_fields = field_map.fields_for(("concept.postal.code",)) or fields
    country_fields = field_map.fields_for(("concept.postal.country",))
    affected = []
    for index, record in enumerate(records):
        country = next((str(record.get(field, "")).strip().upper() for field in country_fields if record.get(field)), "")
        pattern = _POSTAL_PATTERNS.get(country)
        for field in code_fields:
            value = record.get(field)
            if _missing(value):
                continue
            text = str(value).strip()
            if pattern is not None and not pattern.fullmatch(text):
                affected.append((index, field, value))
            elif pattern is None and (len(text) < 3 or len(text) > 12 or not re.search(r"[A-Z0-9]", text, re.I)):
                affected.append((index, field, value))
    return _observation(
        records, affected,
        summary="Postal-code formats are implausible for the available country context; deliverability was not tested.",
        confidence=0.85,
    )


_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC", "PR",
}


def check_region_country(records, fields, question, profile, field_map) -> CheckObservation:
    region_fields = field_map.fields_for(("concept.postal.region",))
    country_fields = field_map.fields_for(("concept.postal.country",))
    affected = []
    for index, record in enumerate(records):
        country = next((str(record.get(field, "")).strip().upper() for field in country_fields if record.get(field)), "")
        for field in region_fields:
            region = record.get(field)
            if _missing(region):
                continue
            text = str(region).strip().upper()
            if country in ("US", "USA", "UNITED STATES") and text not in _US_STATES:
                affected.append((index, field, region))
    return _observation(records, affected, summary="Region codes conflict with declared country syntax.")


def check_usps_delivery_line(records, fields, question, profile, field_map) -> CheckObservation:
    valid_suffixes = {
        "ST", "STREET", "AVE", "AVENUE", "RD", "ROAD", "BLVD", "BOULEVARD", "DR", "DRIVE",
        "LN", "LANE", "CT", "COURT", "HWY", "HIGHWAY", "PKWY", "PARKWAY", "PL", "PLACE",
        "TER", "TERRACE", "WAY", "CIR", "CIRCLE",
    }
    affected = []
    for item in _values(records, fields):
        value = item[2]
        if not isinstance(value, str) or not re.search(r"\d", value):
            continue
        tokens = re.findall(r"[A-Z]+", value.upper())
        if tokens and not any(token in valid_suffixes for token in tokens) and "BOX" not in tokens:
            affected.append(item)
    return _observation(
        records, affected, summary="US delivery lines lack a recognizable street suffix; no deliverability claim was made.",
        confidence=0.65,
    )


def check_po_box_mix(records, fields, question, profile, field_map) -> CheckObservation:
    affected = [
        item
        for item in _values(records, fields)
        if isinstance(item[2], str)
        and re.search(r"\bP\.?\s*O\.?\s*BOX\b", item[2], re.I)
        and re.search(r"\b\d+\s+[A-Z].*\b(?:ST|RD|AVE|BLVD|DR|LN)\b", item[2], re.I)
    ]
    return _observation(records, affected, summary="PO Box and physical delivery patterns are mixed.")


def check_shared_address(records, fields, question, profile, field_map) -> CheckObservation:
    address_fields = field_map.fields_for(
        ("concept.postal.street", "concept.postal.city", "concept.postal.region", "concept.postal.code")
    )
    groups: defaultdict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        key = "|".join(str(record.get(field, "")).strip().casefold() for field in address_fields)
        if key.strip("|"):
            groups[key].append(index)
    threshold = max(5, round(len(records) * 0.20))
    affected = [
        (index, "__address__", key)
        for key, indices in groups.items()
        if len(indices) >= threshold
        for index in indices[1:]
    ]
    return _observation(
        records, affected, summary="One normalized address is shared by an unusually large record cluster.",
        confidence=0.70,
    )


_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+$")


def check_email_syntax(records, fields, question, profile, field_map) -> CheckObservation:
    affected = [
        item for item in _values(records, fields)
        if not _missing(item[2]) and (not isinstance(item[2], str) or not _EMAIL_RE.fullmatch(item[2].strip()))
    ]
    return _observation(
        records, affected, summary="Email syntax is implausible; ownership and deliverability were not tested."
    )


def check_email_domain(records, fields, question, profile, field_map) -> CheckObservation:
    return check_organization_domain(records, fields, question, profile, field_map)


def check_phone_format(records, fields, question, profile, field_map) -> CheckObservation:
    phone_fields = field_map.fields_for(("concept.contact.telephone",)) or fields
    affected = []
    for item in _values(records, phone_fields):
        value = item[2]
        if _missing(value):
            continue
        text = str(value).strip()
        digits = re.sub(r"\D", "", text.split("x", 1)[0])
        if len(digits) < 7 or len(digits) > 15 or (text.startswith("+") and not re.fullmatch(r"\+[0-9 ()-]+(?:\s*(?:x|ext)\s*\d+)?", text, re.I)):
            affected.append(item)
    return _observation(records, affected, summary="Phone values cannot be represented safely under basic E.164 length semantics.")


def check_phone_country(records, fields, question, profile, field_map) -> CheckObservation:
    phone_fields = field_map.fields_for(("concept.contact.telephone",))
    country_fields = field_map.fields_for(("concept.postal.country",))
    prefixes = {"US": "+1", "USA": "+1", "CA": "+1", "GB": "+44", "PH": "+63", "AU": "+61"}
    affected = []
    for index, record in enumerate(records):
        country = next((str(record.get(field, "")).strip().upper() for field in country_fields if record.get(field)), "")
        expected = prefixes.get(country)
        if not expected:
            continue
        for field in phone_fields:
            value = str(record.get(field, "")).strip()
            if value.startswith("+") and not value.startswith(expected):
                affected.append((index, field, value))
    return _observation(records, affected, summary="Explicit international prefixes conflict with address country.", confidence=0.80)


def check_contact_reuse(records, fields, question, profile, field_map) -> CheckObservation:
    affected = []
    for field in fields:
        groups: defaultdict[str, list[int]] = defaultdict(list)
        for index, record in enumerate(records):
            value = record.get(field)
            if not _missing(value):
                groups[str(value).strip().casefold()].append(index)
        threshold = max(4, round(len(records) * 0.15))
        for value, indices in groups.items():
            if len(indices) >= threshold:
                affected.extend((index, field, value) for index in indices[1:])
    return _observation(records, affected, summary="Contact values are reused across an unusually large record cluster.")


def check_role_account(records, fields, question, profile, field_map) -> CheckObservation:
    role_names = {"info", "support", "sales", "billing", "admin", "contact", "hello", "office"}
    affected = []
    for item in _values(records, field_map.fields_for(("concept.contact.email",)) or fields):
        value = item[2]
        if isinstance(value, str) and "@" in value and value.split("@", 1)[0].casefold() in role_names:
            affected.append(item)
    return _observation(
        records, affected, summary="Role mailboxes were detected and may need distinct workflow semantics.", confidence=0.90
    )


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
    return None


def check_datetime_parse(records, fields, question, profile, field_map) -> CheckObservation:
    affected = [
        item for item in _values(records, fields)
        if not _missing(item[2]) and _parse_datetime(item[2]) is None
    ]
    return _observation(records, affected, summary="Date-time values are unparseable under the declared conservative formats.")


def check_timezone(records, fields, question, profile, field_map) -> CheckObservation:
    instant_fields = field_map.fields_for(("concept.time.instant", "concept.time.start", "concept.time.end"))
    timezone_fields = field_map.fields_for(("concept.time.timezone",))
    affected = []
    for index, record in enumerate(records):
        timezone = next((record.get(field) for field in timezone_fields if record.get(field)), None)
        for field in instant_fields:
            value = record.get(field)
            parsed = _parse_datetime(value)
            if parsed is not None and parsed.tzinfo is None and not timezone:
                affected.append((index, field, value))
    return _observation(records, affected, summary="Timezone-naive timestamps lack an explicit timezone field.")


def check_datetime_order(records, fields, question, profile, field_map) -> CheckObservation:
    starts = field_map.fields_for(("concept.time.start",))
    ends = field_map.fields_for(("concept.time.end",))
    affected = []
    for index, record in enumerate(records):
        start = _parse_datetime(next((record.get(field) for field in starts if record.get(field)), None))
        end = _parse_datetime(next((record.get(field) for field in ends if record.get(field)), None))
        if start is not None and end is not None:
            try:
                invalid = start > end
            except TypeError:
                invalid = True
            if invalid:
                affected.append((index, starts[0] if starts else "__start__", "invalid-order"))
    return _observation(records, affected, summary="Start values occur after end values or use incompatible timezone semantics.")


def check_datetime_precision(records, fields, question, profile, field_map) -> CheckObservation:
    precisions = set()
    for _, _, value in _values(records, fields):
        if not isinstance(value, str):
            continue
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
            precisions.add("date")
        elif "." in value:
            precisions.add("subsecond")
        elif "T" in value or ":" in value:
            precisions.add("second")
    affected = []
    if len(precisions) > 1 and records:
        affected.append((0, fields[0] if fields else "__datetime__", sorted(precisions)))
    return _observation(records, affected, summary="Mixed date-time precision was detected.", confidence=0.80)


def check_coordinate_range(records, fields, question, profile, field_map) -> CheckObservation:
    lat_fields = field_map.fields_for(("concept.geography.latitude",))
    lon_fields = field_map.fields_for(("concept.geography.longitude",))
    affected = []
    for index, record in enumerate(records):
        for field, lower, upper in ((*[(f, -90, 90) for f in lat_fields], *[(f, -180, 180) for f in lon_fields])):
            value = record.get(field)
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                if not _missing(value):
                    affected.append((index, field, value))
                continue
            if not isfinite(numeric) or numeric < lower or numeric > upper:
                affected.append((index, field, value))
    return _observation(records, affected, summary="Coordinates are nonnumeric, nonfinite, or outside valid ranges.")


def check_default_coordinate(records, fields, question, profile, field_map) -> CheckObservation:
    lat_fields = field_map.fields_for(("concept.geography.latitude",))
    lon_fields = field_map.fields_for(("concept.geography.longitude",))
    affected = []
    groups: defaultdict[tuple[float, float], list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        try:
            point = (float(record.get(lat_fields[0])), float(record.get(lon_fields[0])))
        except (TypeError, ValueError, IndexError):
            continue
        groups[point].append(index)
        if point == (0.0, 0.0):
            affected.append((index, lat_fields[0], point))
    threshold = max(5, round(len(records) * 0.25))
    for point, indices in groups.items():
        if len(indices) >= threshold and point != (0.0, 0.0):
            affected.extend((index, lat_fields[0], point) for index in indices[1:])
    return _observation(records, affected, summary="Default or suspiciously repeated coordinates were detected.")


def check_product_identifier(records, fields, question, profile, field_map) -> CheckObservation:
    affected = []
    for item in _values(records, fields):
        value = str(item[2]).strip()
        if not value or len(value) > 64 or not re.fullmatch(r"[A-Za-z0-9._/-]+", value):
            affected.append(item)
        elif value.isdigit() and len(value) in (8, 12, 13, 14):
            digits = [int(character) for character in value]
            check = digits.pop()
            total = sum(number * (3 if (len(digits) - index) % 2 else 1) for index, number in enumerate(digits))
            if (10 - total % 10) % 10 != check:
                affected.append(item)
    return _observation(records, affected, summary="Product identifier shapes or supported checksums are invalid.")


def check_amount_parse(records, fields, question, profile, field_map) -> CheckObservation:
    money = re.compile(r"^\(?[-+]?\s*[$€£]?\s*\d{1,3}(?:,?\d{3})*(?:\.\d+)?\)?$")
    affected = [
        item for item in _values(records, fields)
        if not _missing(item[2])
        and not (
            not isinstance(item[2], bool)
            and isinstance(item[2], (int, float))
            and isfinite(float(item[2]))
        )
        and not (isinstance(item[2], str) and money.fullmatch(item[2].strip()))
    ]
    return _observation(records, affected, summary="Monetary amounts cannot be parsed without ambiguity.")


def check_currency_code(records, fields, question, profile, field_map) -> CheckObservation:
    amount_fields = field_map.fields_for(("concept.transaction.amount",))
    currency_fields = field_map.fields_for(("concept.transaction.currency",))
    affected = []
    for index, record in enumerate(records):
        if not any(not _missing(record.get(field)) for field in amount_fields):
            continue
        if not currency_fields:
            affected.append((index, "__currency__", "missing-field"))
            continue
        for field in currency_fields:
            value = record.get(field)
            if not isinstance(value, str) or not re.fullmatch(r"[A-Z]{3}", value.strip().upper()):
                affected.append((index, field, value))
    return _observation(records, affected, summary="Amounts lack a plausible three-letter currency code.")


def check_url_syntax(records, fields, question, profile, field_map) -> CheckObservation:
    affected = []
    for item in _values(records, fields):
        value = item[2]
        if _missing(value):
            continue
        parsed = urlparse(str(value))
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            affected.append(item)
    return _observation(records, affected, summary="URLs are syntactically invalid or use unsupported schemes.")


def check_document_identity(records, fields, question, profile, field_map) -> CheckObservation:
    return check_identifier_uniqueness(records, fields, question, profile, field_map)


def check_document_text(records, fields, question, profile, field_map) -> CheckObservation:
    affected = []
    for item in _values(records, fields):
        value = item[2]
        if not isinstance(value, str) or not value.strip():
            affected.append(item)
            continue
        replacement_share = value.count("�") / max(1, len(value))
        if replacement_share > 0.005 or len(set(value.strip())) <= 2:
            affected.append(item)
    return _observation(records, affected, summary="Document text is empty or shows probable extraction corruption.")


def check_document_injection(records, fields, question, profile, field_map) -> CheckObservation:
    pattern = re.compile(
        r"(?:ignore (?:all )?(?:previous|prior) instructions|system prompt|developer message|"
        r"execute (?:this|the following)|reveal (?:your|the) prompt|tool call)",
        re.IGNORECASE,
    )
    affected = [
        item for item in _values(records, fields)
        if isinstance(item[2], str) and pattern.search(item[2])
    ]
    return _observation(
        records, affected, summary="Document text contains instruction-like patterns and must remain untrusted data.",
        confidence=0.75,
    )


def check_ml_target(records, fields, question, profile, field_map) -> CheckObservation:
    target_fields = field_map.fields_for(("concept.ml.target",)) or fields
    affected = []
    for field in target_fields:
        values = [record.get(field) for record in records]
        if not values or all(_missing(value) for value in values):
            affected.append((0, field, "missing-target")) if records else None
        elif sum(_missing(value) for value in values) / len(values) > 0.20:
            affected.append((0, field, "high-target-missingness"))
    return _observation(records, affected, summary="Target fields are absent or materially incomplete.")


def check_target_balance(records, fields, question, profile, field_map) -> CheckObservation:
    target_fields = field_map.fields_for(("concept.ml.target",)) or fields
    affected = []
    evidence: list[tuple[str, Any]] = []
    for field in target_fields:
        values = [record.get(field) for record in records if not _missing(record.get(field))]
        if len(values) < 5:
            continue
        counts = Counter(canonical_json(value) for value in values)
        if len(counts) <= 20:
            minority = min(counts.values()) / len(values)
            evidence.append((f"evidence.minority-share-{field}", minority))
            if minority < 0.05:
                affected.append((0, field, "rare-target-class"))
    return _observation(
        records, affected, summary="Target classes are highly imbalanced and need metric/slice review.",
        evidence=tuple(evidence), confidence=0.90,
    )


def check_ml_leakage(records, fields, question, profile, field_map) -> CheckObservation:
    targets = field_map.fields_for(("concept.ml.target",))
    affected = []
    for target in targets:
        target_values = [record.get(target) for record in records]
        for field in profile.column_names:
            if field == target:
                continue
            normalized = field.casefold()
            values = [record.get(field) for record in records]
            if values == target_values or any(token in normalized for token in ("target_copy", "post_outcome", "future_label")):
                affected.append((0, field, "target-derived-feature"))
    return _observation(records, affected, summary="Feature columns duplicate or explicitly reveal the target.")


def check_ml_prediction_contamination(records, fields, question, profile, field_map) -> CheckObservation:
    prediction_fields = field_map.fields_for(("concept.ml.prediction",))
    affected = [(0, field, "prediction-like-feature") for field in prediction_fields] if records else []
    return _observation(records, affected, summary="Prediction-like columns require explicit exclusion or stacking provenance.")


def check_privacy_patterns(records, fields, question, profile, field_map) -> CheckObservation:
    ssn = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    card = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
    affected = [
        item for item in _values(records, fields)
        if isinstance(item[2], str) and (ssn.search(item[2]) or card.search(item[2]))
    ]
    return _observation(
        records, affected, summary="High-risk identifier patterns were detected; values were not retained in findings.",
        confidence=0.75,
    )


_CHECKS: tuple[tuple[str, CheckFunction], ...] = (
    ("quality.placeholder-check", check_placeholders),
    ("quality.unicode-control-check", check_unicode_controls),
    ("quality.whitespace-check", check_whitespace),
    ("quality.punctuation-check", check_punctuation),
    ("quality.type-conformance-check", check_type_conformance),
    ("quality.duplicate-record-check", check_duplicate_records),
    ("quality.identifier-uniqueness-check", check_identifier_uniqueness),
    ("quality.cardinality-check", check_cardinality),
    ("quality.numeric-outlier-check", check_numeric_outliers),
    ("quality.case-pattern-check", check_case_pattern),
    ("quality.organization-suffix-check", check_organization_suffix),
    ("quality.organization-duplicate-check", check_organization_duplicates),
    ("quality.organization-domain-check", check_organization_domain),
    ("quality.address-component-check", check_address_components),
    ("quality.postal-format-check", check_postal_format),
    ("quality.region-country-check", check_region_country),
    ("quality.usps-delivery-line-check", check_usps_delivery_line),
    ("quality.po-box-mix-check", check_po_box_mix),
    ("quality.shared-address-check", check_shared_address),
    ("quality.email-syntax-check", check_email_syntax),
    ("quality.email-domain-check", check_email_domain),
    ("quality.phone-format-check", check_phone_format),
    ("quality.phone-country-check", check_phone_country),
    ("quality.contact-reuse-check", check_contact_reuse),
    ("quality.role-account-check", check_role_account),
    ("quality.datetime-parse-check", check_datetime_parse),
    ("quality.timezone-check", check_timezone),
    ("quality.datetime-order-check", check_datetime_order),
    ("quality.datetime-precision-check", check_datetime_precision),
    ("quality.coordinate-range-check", check_coordinate_range),
    ("quality.default-coordinate-check", check_default_coordinate),
    ("quality.product-identifier-check", check_product_identifier),
    ("quality.amount-parse-check", check_amount_parse),
    ("quality.currency-code-check", check_currency_code),
    ("quality.url-syntax-check", check_url_syntax),
    ("quality.document-identity-check", check_document_identity),
    ("quality.document-text-check", check_document_text),
    ("quality.document-injection-pattern-check", check_document_injection),
    ("quality.ml-target-check", check_ml_target),
    ("quality.target-balance-check", check_target_balance),
    ("quality.ml-leakage-check", check_ml_leakage),
    ("quality.ml-prediction-contamination-check", check_ml_prediction_contamination),
    ("quality.privacy-pattern-check", check_privacy_patterns),
)

STANDARD_CHECK_REGISTRY = CheckRegistry(
    id="registry.interrogation-checks",
    version="1.0.0",
    adapters=tuple(
        CallableCheckAdapter(
            id="check.stdlib." + capability.removeprefix("quality.").replace(".", "-"),
            version="1.0.0",
            capability=capability,
            function=function,
        )
        for capability, function in _CHECKS
    ),
)


class QuestionExecutor:
    id = "executor.semantic-interrogation"
    version = "1.0.0"

    def execute(
        self,
        records: Sequence[Mapping[str, Any]],
        profile: DatasetProfile,
        field_map: SemanticFieldMap,
        plan: QuestionPlan,
        questions: Mapping[str, QuestionDefinition],
        registry: CheckRegistry = STANDARD_CHECK_REGISTRY,
        *,
        record_timing: bool = False,
    ) -> FindingSet:
        dataset_digest = records_digest(records)
        if dataset_digest != profile.dataset_digest:
            raise ValueError("records do not match the profiled dataset")
        if plan.dataset_profile_digest != profile.digest:
            raise ValueError("question plan does not identify this dataset profile")
        if plan.semantic_field_map_digest != field_map.digest:
            raise ValueError("question plan does not identify this semantic field map")
        receipts: list[QuestionReceipt] = []
        findings: list[Finding] = []
        selected = [item for item in plan.items if item.status == "selected"]
        for index, item in enumerate(selected):
            question = questions.get(item.question_id)
            if question is None or question.digest != item.question_digest:
                raise ValueError(f"plan question identity cannot be resolved: {item.question_id}")
            adapter = registry.get(item.selected_capability)
            receipt_id = (
                f"question-receipt.{plan.digest.removeprefix('sha256:')[:16]}.{index:04d}"
            )
            if adapter is None:
                receipts.append(
                    QuestionReceipt(
                        id=receipt_id,
                        plan_digest=plan.digest,
                        dataset_digest=dataset_digest,
                        question_id=question.id,
                        question_digest=question.digest,
                        check_capability=item.selected_capability,
                        check_implementation_id="check.unavailable",
                        check_implementation_version="1.0.0",
                        check_implementation_digest=sha256_digest("check.unavailable"),
                        mode=item.selected_mode,
                        outcome="not-run",
                        fields=item.fields,
                        rows_examined=0,
                        coverage=0.0,
                        error_code="check.capability-unavailable",
                    )
                )
                continue
            start = perf_counter() if record_timing else 0.0
            try:
                observation = adapter.run(records, item.fields, question, profile, field_map)
            except Exception as exc:  # adapter boundary converts to stable evidence
                observation = CheckObservation(
                    outcome="error",
                    error_code="check.adapter-exception",
                    evidence=(("evidence.error-type", type(exc).__name__),),
                    summary="The check adapter raised an exception.",
                )
            latency = (perf_counter() - start) * 1000.0 if record_timing else 0.0
            finding_ids: tuple[str, ...] = ()
            if observation.outcome == "fail":
                finding = Finding(
                    question_id=question.id,
                    question_digest=question.digest,
                    code=question.finding_code,
                    severity=question.severity,
                    confidence=observation.confidence,
                    fields=observation.fields or item.fields,
                    row_ids=observation.affected_row_ids,
                    affected_count=observation.affected_count,
                    evidence=observation.evidence,
                    sample_value_digests=observation.sample_value_digests,
                    remediation_families=question.repair_families,
                    summary=observation.summary,
                )
                findings.append(finding)
                finding_ids = (finding.id,)
            receipts.append(
                QuestionReceipt(
                    id=receipt_id,
                    plan_digest=plan.digest,
                    dataset_digest=dataset_digest,
                    question_id=question.id,
                    question_digest=question.digest,
                    check_capability=adapter.capability,
                    check_implementation_id=adapter.id,
                    check_implementation_version=adapter.version,
                    check_implementation_digest=adapter.implementation_digest,
                    mode=adapter.mode,
                    outcome=observation.outcome,
                    fields=item.fields,
                    rows_examined=len(records),
                    coverage=1.0 if records else 0.0,
                    finding_ids=finding_ids,
                    evidence=observation.evidence,
                    error_code=observation.error_code,
                    latency_ms=latency,
                )
            )
        result = FindingSet(
            dataset_digest=dataset_digest,
            plan_digest=plan.digest,
            receipts=tuple(receipts),
            findings=tuple(findings),
            executor_id=self.id,
            executor_version=self.version,
        )
        problems = result.validate()
        if problems:
            raise ValueError("invalid finding set: " + "; ".join(problems))
        return result


__all__ = [
    "STANDARD_CHECK_REGISTRY",
    "CallableCheckAdapter",
    "CheckAdapter",
    "CheckObservation",
    "CheckRegistry",
    "QuestionExecutor",
]
