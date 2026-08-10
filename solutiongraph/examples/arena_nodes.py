"""Dependency-free nodes for the executable Universal DAG Arena fixtures.

The fixtures are deliberately small enough to run in CI, while preserving the
same typed seams a production connector or domain library would implement.
"""

from __future__ import annotations

import ast
import csv
import io
import math
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def _alnum(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


# Golden customer table -----------------------------------------------------


def normalize_customers_conservative(bundle: dict[str, Any]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, source in enumerate(bundle["records"]):
        record = {
            _key(name): value.strip() if isinstance(value, str) else value
            for name, value in source.items()
        }
        record["source_record"] = str(source.get("source_record", f"row-{index + 1}"))
        if record.get("email"):
            record["email"] = str(record["email"]).lower()
        if record.get("phone"):
            record["phone"] = re.sub(r"\D", "", str(record["phone"]))
        records.append(record)
    return {**bundle, "records": records, "normalization": "conservative"}


def normalize_customers_canonical(bundle: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_customers_conservative(bundle)
    for record in normalized["records"]:
        if record.get("name"):
            record["name"] = " ".join(str(record["name"]).split()).title()
        if record.get("address"):
            address = str(record["address"]).upper()
            address = re.sub(r"\bSTREET\b", "ST", address)
            address = re.sub(r"\bAVENUE\b", "AVE", address)
            record["address"] = " ".join(address.split())
    normalized["normalization"] = "canonical"
    return normalized


def validate_customer_contacts_syntax(bundle: dict[str, Any]) -> dict[str, Any]:
    records = []
    for source in bundle["records"]:
        record = dict(source)
        email_ok = bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(record.get("email", ""))))
        phone_ok = len(re.sub(r"\D", "", str(record.get("phone", "")))) == 10
        record["verified_fields"] = [
            name for name, valid in (("email", email_ok), ("phone", phone_ok)) if valid
        ]
        record["verification_method"] = "syntax"
        records.append(record)
    return {**bundle, "records": records}


def validate_customer_contacts_reference(bundle: dict[str, Any]) -> dict[str, Any]:
    directory = bundle.get("contact_directory", {})
    emails = {str(value).lower() for value in directory.get("emails", [])}
    phones = {re.sub(r"\D", "", str(value)) for value in directory.get("phones", [])}
    records = []
    for source in bundle["records"]:
        record = dict(source)
        verified: list[str] = []
        if str(record.get("email", "")).lower() in emails:
            verified.append("email")
        if re.sub(r"\D", "", str(record.get("phone", ""))) in phones:
            verified.append("phone")
        record["verified_fields"] = verified
        record["verification_method"] = "offline-reference-fixture"
        records.append(record)
    return {**bundle, "records": records}


def resolve_customers_by_email(bundle: dict[str, Any]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for index, record in enumerate(bundle["records"]):
        email = _alnum(record.get("email", ""))
        groups.setdefault(email or f"unmatched-{index}", []).append(dict(record))
    return {**bundle, "groups": list(groups.values()), "resolution": "exact-email"}


def resolve_customers_multikey(bundle: dict[str, Any]) -> dict[str, Any]:
    records = [dict(record) for record in bundle["records"]]
    parent = list(range(len(records)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[b] = a

    for left in range(len(records)):
        for right in range(left + 1, len(records)):
            shared = any(
                records[left].get(field)
                and _alnum(records[left].get(field)) == _alnum(records[right].get(field))
                for field in ("email", "phone")
            )
            names_match = _alnum(records[left].get("name")) == _alnum(records[right].get("name"))
            addresses_match = _alnum(records[left].get("address")) == _alnum(records[right].get("address"))
            if shared or (names_match and addresses_match):
                union(left, right)
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for index, record in enumerate(records):
        grouped[find(index)].append(record)
    return {**bundle, "groups": list(grouped.values()), "resolution": "multi-key"}


def emit_customer_first(groups: dict[str, Any]) -> list[dict[str, Any]]:
    bundle = groups
    output = []
    for group in bundle["groups"]:
        record = dict(group[0])
        record["provenance"] = [item["source_record"] for item in group]
        record["verified_source_count"] = sum(bool(item.get("verified_fields")) for item in group)
        output.append(record)
    return sorted(output, key=lambda item: str(item.get("name", "")))


def emit_customer_complete(groups: dict[str, Any]) -> list[dict[str, Any]]:
    bundle = groups
    output = []
    for group in bundle["groups"]:
        record: dict[str, Any] = {}
        for item in group:
            for field, value in item.items():
                if field not in {"verified_fields", "verification_method", "source_record"} and value not in (None, ""):
                    record.setdefault(field, value)
        record["provenance"] = sorted(item["source_record"] for item in group)
        record["verified_fields"] = sorted(
            {field for item in group for field in item.get("verified_fields", [])}
        )
        record["verified_source_count"] = sum(bool(item.get("verified_fields")) for item in group)
        output.append(record)
    return sorted(output, key=lambda item: str(item.get("name", "")))


# Address standardization and reference verification -----------------------


def parse_addresses_commas(bundle: dict[str, Any]) -> dict[str, Any]:
    parsed = []
    for index, value in enumerate(bundle["addresses"]):
        parts = [part.strip() for part in str(value).split(",")]
        region_zip = parts[-1].split() if parts else []
        parsed.append(
            {
                "source_index": index,
                "street": parts[0] if parts else "",
                "city": parts[-2] if len(parts) >= 2 else "",
                "region": region_zip[0] if region_zip else "",
                "postal_code": region_zip[-1] if len(region_zip) >= 2 else "",
            }
        )
    return {**bundle, "records": parsed, "parser": "comma"}


def parse_addresses_structured(bundle: dict[str, Any]) -> dict[str, Any]:
    parsed = []
    pattern = re.compile(
        r"^\s*(.+?),\s*([^,]+?),\s*([A-Za-z]{2})\s+(\d{5}(?:-\d{4})?)\s*$"
    )
    for index, value in enumerate(bundle["addresses"]):
        match = pattern.match(str(value))
        if match:
            street, city, region, postal_code = match.groups()
        else:
            street, city, region, postal_code = str(value), "", "", ""
        parsed.append(
            {
                "source_index": index,
                "street": street,
                "city": city,
                "region": region,
                "postal_code": postal_code,
            }
        )
    return {**bundle, "records": parsed, "parser": "structured"}


def normalize_addresses_basic(bundle: dict[str, Any]) -> dict[str, Any]:
    records = []
    for source in bundle["records"]:
        record = {key: " ".join(str(value).upper().split()) for key, value in source.items() if key != "source_index"}
        record["source_index"] = source["source_index"]
        records.append(record)
    return {**bundle, "records": records, "normalizer": "basic"}


def normalize_addresses_postal(bundle: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_addresses_basic(bundle)
    suffixes = {
        "STREET": "ST",
        "AVENUE": "AVE",
        "ROAD": "RD",
        "BOULEVARD": "BLVD",
        "APARTMENT": "APT",
        "SUITE": "STE",
    }
    for record in normalized["records"]:
        words = [suffixes.get(word, word) for word in record["street"].split()]
        record["street"] = " ".join(words)
    normalized["normalizer"] = "postal-abbreviation-fixture"
    return normalized


def verify_addresses_exact(bundle: dict[str, Any]) -> dict[str, Any]:
    directory = {
        (item["street"], item["city"], item["region"], item["postal_code"]): item
        for item in bundle.get("reference_directory", [])
    }
    records = []
    for source in bundle["records"]:
        record = dict(source)
        key = tuple(record.get(field, "") for field in ("street", "city", "region", "postal_code"))
        record["verified"] = key in directory
        record["match_code"] = "exact" if record["verified"] else "unmatched"
        record["authority"] = "offline-reference-fixture"
        records.append(record)
    return {**bundle, "records": records}


def verify_addresses_alias_aware(bundle: dict[str, Any]) -> dict[str, Any]:
    references = bundle.get("reference_directory", [])
    records = []
    for source in bundle["records"]:
        record = dict(source)
        matched = next(
            (
                item
                for item in references
                if _alnum(item["street"]) == _alnum(record.get("street"))
                and _alnum(item["city"]) == _alnum(record.get("city"))
                and item["region"] == record.get("region")
                and item["postal_code"] == record.get("postal_code")
            ),
            None,
        )
        record["verified"] = matched is not None
        record["match_code"] = "canonicalized" if matched else "unmatched"
        record["authority"] = "offline-reference-fixture"
        if matched:
            for field in ("street", "city", "region", "postal_code"):
                record[field] = matched[field]
        records.append(record)
    return {**bundle, "records": records}


def emit_verified_addresses(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        (dict(record) for record in bundle["records"]),
        key=lambda item: (item["postal_code"], item["street"]),
    )


# Product dataset -----------------------------------------------------------


def acquire_product_sources_preserve(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(source) for source in sources]


def acquire_product_sources_sorted(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted((dict(source) for source in sources), key=lambda item: item["url"])


def extract_products_regex(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    pattern = re.compile(
        r"<article\s+data-sku=['\"]([^'\"]+)['\"]>.*?<h2>(.*?)</h2>.*?"
        r"<span\s+class=['\"]price['\"]>(.*?)</span>.*?</article>",
        re.I | re.S,
    )
    for source in sources:
        for sku, name, price in pattern.findall(source["html"]):
            products.append({"sku": sku.strip(), "name": re.sub(r"<[^>]+>", "", name).strip(), "price": price.strip(), "source_url": source["url"]})
    return products


class _ProductParser(HTMLParser):
    def __init__(self, source_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.source_url = source_url
        self.products: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self.field = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "article" and attributes.get("data-sku"):
            self.current = {"sku": attributes["data-sku"], "source_url": self.source_url}
        elif self.current is not None and tag == "h2":
            self.field = "name"
        elif self.current is not None and tag == "span" and attributes.get("class") == "price":
            self.field = "price"

    def handle_endtag(self, tag: str) -> None:
        if tag == "article" and self.current is not None:
            self.products.append(self.current)
            self.current = None
        self.field = ""

    def handle_data(self, data: str) -> None:
        if self.current is not None and self.field and data.strip():
            self.current[self.field] = " ".join(data.split())


def extract_products_parser(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for source in sources:
        parser = _ProductParser(source["url"])
        parser.feed(source["html"])
        products.extend(parser.products)
    return products


def normalize_product_prices_float(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for source in products:
        item = dict(source)
        item["price_cents"] = round(float(re.sub(r"[^0-9.]", "", item["price"])) * 100)
        output.append(item)
    return output


def normalize_product_prices_decimal(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for source in products:
        item = dict(source)
        amount = Decimal(re.sub(r"[^0-9.-]", "", item["price"]))
        item["price_cents"] = int(amount * 100)
        item["name"] = " ".join(item["name"].split())
        output.append(item)
    return output


def verify_products_single_source(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for source in products:
        item = dict(source)
        item["verified"] = False
        item["evidence_sources"] = [item["source_url"]]
        output.append(item)
    return output


def verify_products_cross_source(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for product in products:
        grouped[(product["sku"], int(product["price_cents"]))].append(product)
    output = []
    for (sku, price_cents), group in sorted(grouped.items()):
        sources = sorted({item["source_url"] for item in group})
        output.append(
            {
                "sku": sku,
                "name": group[0]["name"],
                "price_cents": price_cents,
                "verified": len(sources) >= 2,
                "evidence_sources": sources,
            }
        )
    return output


# Calibrated forecast -------------------------------------------------------


def prepare_series_observed(series: dict[str, Any]) -> dict[str, Any]:
    return {**series, "train": [float(value) for value in series["train"]], "preparation": "observed"}


def prepare_series_interpolate(series: dict[str, Any]) -> dict[str, Any]:
    values = list(series["train"])
    for index, value in enumerate(values):
        if value is None:
            left = next((float(values[pos]) for pos in range(index - 1, -1, -1) if values[pos] is not None), 0.0)
            right = next((float(values[pos]) for pos in range(index + 1, len(values)) if values[pos] is not None), left)
            values[index] = (left + right) / 2
    return {**series, "train": [float(value) for value in values], "preparation": "interpolate"}


def fit_forecast_mean(series: dict[str, Any]) -> dict[str, Any]:
    values = series["train"]
    return {**series, "model": {"kind": "mean", "level": sum(values) / len(values)}}


def fit_forecast_trend(series: dict[str, Any]) -> dict[str, Any]:
    values = series["train"]
    xs = list(range(len(values)))
    mean_x = sum(xs) / len(xs)
    mean_y = sum(values) / len(values)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values, strict=True)) / denominator
    return {**series, "model": {"kind": "trend", "slope": slope, "intercept": mean_y - slope * mean_x}}


def generate_forecast(series: dict[str, Any]) -> dict[str, Any]:
    model = series["model"]
    horizon = int(series["horizon"])
    start = len(series["train"])
    if model["kind"] == "mean":
        predictions = [model["level"]] * horizon
    else:
        predictions = [model["intercept"] + model["slope"] * (start + offset) for offset in range(horizon)]
    return {**series, "predictions": predictions}


def calibrate_intervals_fixed(series: dict[str, Any]) -> dict[str, Any]:
    width = 0.25
    return {**series, "intervals": [[value - width, value + width] for value in series["predictions"]], "interval_method": "fixed"}


def calibrate_intervals_residual(series: dict[str, Any]) -> dict[str, Any]:
    model = series["model"]
    fitted = []
    for index in range(len(series["train"])):
        fitted.append(model["level"] if model["kind"] == "mean" else model["intercept"] + model["slope"] * index)
    residuals = [abs(actual - predicted) for actual, predicted in zip(series["train"], fitted, strict=True)]
    width = max(0.5, sorted(residuals)[max(0, math.ceil(0.9 * len(residuals)) - 1)])
    return {**series, "intervals": [[value - width, value + width] for value in series["predictions"]], "interval_method": "empirical-residual"}


# Organization entity linking ---------------------------------------------


def normalize_organizations_basic(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for source in records:
        item = dict(source)
        item["normalized_name"] = " ".join(re.sub(r"[^a-z0-9 ]", " ", item["name"].lower()).split())
        item["normalized_domain"] = item.get("domain", "").lower().removeprefix("www.")
        output.append(item)
    return output


def normalize_organizations_legal(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = normalize_organizations_basic(records)
    suffixes = {"inc", "incorporated", "llc", "ltd", "limited", "corp", "corporation"}
    for item in output:
        item["normalized_name"] = " ".join(word for word in item["normalized_name"].split() if word not in suffixes)
    return output


def block_organizations_domain(records: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = []
    for left in range(len(records)):
        for right in range(left + 1, len(records)):
            if records[left].get("normalized_domain") and records[left]["normalized_domain"] == records[right].get("normalized_domain"):
                pairs.append([left, right])
    return {"records": records, "pairs": pairs, "blocking": "domain"}


def block_organizations_tokens(records: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = []
    for left in range(len(records)):
        for right in range(left + 1, len(records)):
            left_tokens = set(records[left]["normalized_name"].split())
            right_tokens = set(records[right]["normalized_name"].split())
            if left_tokens & right_tokens or records[left].get("normalized_domain") == records[right].get("normalized_domain"):
                pairs.append([left, right])
    return {"records": records, "pairs": pairs, "blocking": "tokens"}


def link_organizations_exact(blocked: dict[str, Any]) -> dict[str, Any]:
    links = [
        pair
        for pair in blocked["pairs"]
        if blocked["records"][pair[0]]["normalized_name"] == blocked["records"][pair[1]]["normalized_name"]
    ]
    return {**blocked, "links": links, "linker": "exact-name"}


def link_organizations_evidence(blocked: dict[str, Any]) -> dict[str, Any]:
    links = []
    for pair in blocked["pairs"]:
        left, right = (blocked["records"][index] for index in pair)
        name_overlap = bool(set(left["normalized_name"].split()) & set(right["normalized_name"].split()))
        domain_match = bool(left.get("normalized_domain") and left.get("normalized_domain") == right.get("normalized_domain"))
        address_match = _alnum(left.get("address")) == _alnum(right.get("address"))
        if sum((name_overlap, domain_match, address_match)) >= 2:
            links.append(pair)
    return {**blocked, "links": links, "linker": "multi-evidence"}


def build_entity_components(linked: dict[str, Any]) -> list[dict[str, Any]]:
    records = linked["records"]
    parent = list(range(len(records)))

    def find(index: int) -> int:
        if parent[index] != index:
            parent[index] = find(parent[index])
        return parent[index]

    for left, right in linked["links"]:
        parent[find(right)] = find(left)
    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for index, record in enumerate(records):
        groups[find(index)].append(record)
    return [
        {
            "entity_id": f"entity-{position + 1}",
            "record_ids": sorted(item["id"] for item in group),
            "canonical_name": sorted((item["name"] for item in group), key=len)[0],
            "linker": linked["linker"],
        }
        for position, group in enumerate(sorted(groups.values(), key=lambda group: min(item["id"] for item in group)))
    ]


# Tested code repair --------------------------------------------------------


def inspect_code_ast(repository: dict[str, Any]) -> dict[str, Any]:
    source = repository["files"]["math_utils.py"]
    tree = ast.parse(source)
    operators = [type(node.op).__name__ for node in ast.walk(tree) if isinstance(node, ast.BinOp)]
    return {**repository, "findings": {"operators": operators, "method": "ast"}}


def inspect_code_tests(repository: dict[str, Any]) -> dict[str, Any]:
    return {**repository, "findings": {"failing_cases": list(repository["tests"]), "method": "test-contract"}}


def propose_operator_repair(proposal: dict[str, Any]) -> dict[str, Any]:
    return {**proposal, "patch": {"old": "return a - b", "new": "return a + b", "hypothesis": "operator mismatch"}}


def propose_contract_repair(proposal: dict[str, Any]) -> dict[str, Any]:
    tests = proposal["tests"]
    additive = all(case["expected"] == case["args"][0] + case["args"][1] for case in tests)
    replacement = "return a + b" if additive else "return a - b"
    return {**proposal, "patch": {"old": "return a - b", "new": replacement, "hypothesis": "derive behavior from fixed tests"}}


def apply_repair_exact(proposal: dict[str, Any]) -> dict[str, Any]:
    files = dict(proposal["files"])
    patch = proposal["patch"]
    files["math_utils.py"] = files["math_utils.py"].replace(patch["old"], patch["new"], 1)
    return {**proposal, "files": files, "changed_files": ["math_utils.py"]}


def apply_repair_line(proposal: dict[str, Any]) -> dict[str, Any]:
    files = dict(proposal["files"])
    lines = files["math_utils.py"].splitlines()
    lines = [
        line[: len(line) - len(line.lstrip())] + proposal["patch"]["new"]
        if line.strip().startswith("return a ")
        else line
        for line in lines
    ]
    files["math_utils.py"] = "\n".join(lines) + "\n"
    return {**proposal, "files": files, "changed_files": ["math_utils.py"]}


def _safe_binary_function(source: str):
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
    expression = next(node.value for node in function.body if isinstance(node, ast.Return))
    if not isinstance(expression, ast.BinOp) or not isinstance(expression.left, ast.Name) or not isinstance(expression.right, ast.Name):
        raise ValueError("fixture tester only permits one binary return expression")
    operators = {ast.Add: lambda left, right: left + right, ast.Sub: lambda left, right: left - right}
    operation = operators.get(type(expression.op))
    if operation is None:
        raise ValueError("fixture tester encountered an unsupported operator")
    return operation


def test_repair_ast(proposal: dict[str, Any]) -> dict[str, Any]:
    source = proposal["files"]["math_utils.py"]
    operation = _safe_binary_function(source)
    results = [operation(*case["args"]) == case["expected"] for case in proposal["tests"]]
    return {"passed": all(results), "passed_cases": sum(results), "total_cases": len(results), "changed_files": proposal["changed_files"], "source": source, "tester": "ast-interpreter"}


def test_repair_symbolic(proposal: dict[str, Any]) -> dict[str, Any]:
    source = proposal["files"]["math_utils.py"]
    tree = ast.parse(source)
    has_add = any(isinstance(node, ast.Add) for node in ast.walk(tree))
    operation = _safe_binary_function(source)
    results = [operation(*case["args"]) == case["expected"] for case in proposal["tests"]]
    return {"passed": has_add and all(results), "passed_cases": sum(results), "total_cases": len(results), "changed_files": proposal["changed_files"], "source": source, "tester": "symbolic-and-cases"}


# Multi-feed analytical dataset -------------------------------------------


def decode_feeds_csv_module(feeds: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(row, source="csv") for row in csv.DictReader(io.StringIO(feeds["csv"]))]
    rows.extend(dict(row, source="json") for row in feeds["json"])
    return rows


def decode_feeds_line_parser(feeds: dict[str, Any]) -> list[dict[str, Any]]:
    lines = [line for line in feeds["csv"].splitlines() if line.strip()]
    header = [item.strip() for item in lines[0].split(",")]
    rows = [dict(zip(header, [item.strip() for item in line.split(",")], strict=True), source="csv") for line in lines[1:]]
    rows.extend(dict(row, source="json") for row in feeds["json"])
    return rows


def normalize_feed_rows_strict(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        item = dict(row)
        try:
            item["amount"] = float(item["amount"])
            item["normalization_error"] = ""
        except (TypeError, ValueError):
            item["normalization_error"] = "amount-not-numeric"
        output.append(item)
    return output


def normalize_feed_rows_coerce(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        item = dict(row)
        try:
            item["amount"] = float(Decimal(re.sub(r"[^0-9.-]", "", str(item["amount"]))))
            item["normalization_error"] = ""
        except (InvalidOperation, ValueError):
            item["normalization_error"] = "amount-not-numeric"
        item["id"] = str(item["id"])
        item["name"] = " ".join(str(item["name"]).split()).title()
        output.append(item)
    return output


def reconcile_feed_rows_priority(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {"csv": 0, "json": 1}
    output: dict[str, dict[str, Any]] = {}
    for row in sorted(rows, key=lambda item: priority[item["source"]]):
        output.setdefault(str(row["id"]), dict(row))
    return list(output.values())


def reconcile_feed_rows_complete(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    sources: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        key = str(row["id"])
        merged = output.setdefault(key, {})
        for field, value in row.items():
            if value not in (None, "", []) and field != "source":
                merged.setdefault(field, value)
        sources[key].add(row["source"])
    for key, row in output.items():
        row["sources"] = sorted(sources[key])
    return list(output.values())


def validate_feed_rows_strict(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if not row.get("normalization_error") and set(("id", "name", "amount")).issubset(row)]
    invalid = [row for row in rows if row not in valid]
    return {"rows": sorted(valid, key=lambda row: row["id"]), "quarantine": invalid, "quality": len(valid) / len(rows) if rows else 0.0}


def validate_feed_rows_quarantine(rows: list[dict[str, Any]]) -> dict[str, Any]:
    report = validate_feed_rows_strict(rows)
    report["lineage_complete"] = all(bool(row.get("sources") or row.get("source")) for row in rows)
    return report
