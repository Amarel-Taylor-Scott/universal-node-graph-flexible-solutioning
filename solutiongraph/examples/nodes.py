"""Small real implementations used by the six reference domain examples.

These functions are deliberately ordinary. Their purpose is to exercise the
universal ABI, not to compete with mature domain packages.
"""

from __future__ import annotations

import math
import re
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import unquote
from urllib.request import Request, urlopen

from solutiongraph.executor import NodeExecutionFailure


def load_web_source_offline(source: dict[str, Any]) -> str:
    """Load inline HTML or a text data URL without network access."""
    if isinstance(source.get("html"), str):
        return source["html"]
    url = str(source.get("url", ""))
    if not url.startswith("data:text/html"):
        raise NodeExecutionFailure(
            "web.offline-source-unavailable",
            "offline loader requires inline HTML or a text/html data URL",
        )
    _, separator, payload = url.partition(",")
    if not separator:
        raise NodeExecutionFailure("web.invalid-data-url", "data URL has no payload")
    return unquote(payload)


def load_web_source_urllib(source: dict[str, Any], timeout_seconds: float = 10.0) -> str:
    """Load inline HTML or fetch an explicitly supplied read-only URL."""
    if isinstance(source.get("html"), str):
        return source["html"]
    url = str(source.get("url", ""))
    if not url:
        raise NodeExecutionFailure("web.missing-url", "source URL is required")
    headers = {str(key): str(value) for key, value in source.get("headers", {}).items()}
    try:
        with urlopen(
            Request(url, headers=headers, method="GET"), timeout=timeout_seconds
        ) as reply:
            charset = reply.headers.get_content_charset() or "utf-8"
            return reply.read().decode(charset, errors="replace")
    except ValueError as exc:
        raise NodeExecutionFailure("web.invalid-url", str(exc)) from exc
    except OSError as exc:
        raise NodeExecutionFailure(
            "network.http-error", str(exc), retryable=True
        ) from exc


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if not value:
            return
        self.text_parts.append(value)
        if self._in_title:
            self.title_parts.append(value)


def extract_page_html_parser(html: str) -> dict[str, Any]:
    """Extract title, visible text, and links with the standard HTML parser."""
    parser = _PageParser()
    parser.feed(html)
    return {
        "title": " ".join(parser.title_parts),
        "text": " ".join(parser.text_parts),
        "links": parser.links,
        "method": "html-parser",
    }


def extract_page_regex(html: str) -> dict[str, Any]:
    """Extract the same page fields with a deliberately simple regex strategy."""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = unescape(re.sub(r"<[^>]+>", " ", title_match.group(1))).strip() if title_match else ""
    links = [unescape(value) for value in re.findall(
        r"<a\b[^>]*?href\s*=\s*['\"]([^'\"]+)['\"]", html, re.I
    )]
    text = unescape(re.sub(r"<[^>]+>", " ", html))
    return {
        "title": " ".join(title.split()),
        "text": " ".join(text.split()),
        "links": links,
        "method": "regex",
    }


def project_page_schema(page: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    """Project an extracted page into an explicit requested schema."""
    missing = [field for field in fields if field not in page]
    if missing:
        raise NodeExecutionFailure(
            "schema.missing-field", "missing page field(s): " + ", ".join(missing)
        )
    return {field: page[field] for field in fields}


def normalize_document_conservative(document: str) -> str:
    """Normalize line endings and trailing whitespace while preserving lines."""
    lines = [line.rstrip() for line in document.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line.strip())


def normalize_document_compact(document: str) -> str:
    """Normalize all repeated whitespace into single spaces around line records."""
    lines = [" ".join(line.split()) for line in document.replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line)


def _field_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def extract_document_lines(text: str) -> dict[str, str]:
    """Extract key/value lines split at the first colon."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator and _field_name(key):
            fields[_field_name(key)] = value.strip()
    return fields


def extract_document_regex(text: str) -> dict[str, str]:
    """Extract key/value lines with a multiline regular expression."""
    return {
        _field_name(key): value.strip()
        for key, value in re.findall(r"^\s*([^:\n]+?)\s*:\s*(.*?)\s*$", text, re.M)
        if _field_name(key)
    }


def project_document_schema(
    fields: dict[str, str], required_fields: tuple[str, ...]
) -> dict[str, str]:
    """Require and project the requested document fields."""
    missing = [field for field in required_fields if not fields.get(field)]
    if missing:
        raise NodeExecutionFailure(
            "schema.missing-field", "missing document field(s): " + ", ".join(missing)
        )
    return {field: fields[field] for field in required_fields}


def _pgm_tokens(document: str) -> list[str]:
    without_comments = "\n".join(line.partition("#")[0] for line in document.splitlines())
    return without_comments.split()


def _build_image(width: int, height: int, maximum: int, values: list[int]) -> dict[str, Any]:
    if width <= 0 or height <= 0 or maximum <= 0:
        raise NodeExecutionFailure("image.invalid-header", "PGM dimensions and maximum must be positive")
    if len(values) != width * height:
        raise NodeExecutionFailure("image.invalid-pixels", "PGM pixel count does not match dimensions")
    if any(value < 0 or value > maximum for value in values):
        raise NodeExecutionFailure("image.invalid-pixels", "PGM pixel falls outside declared range")
    rows = [values[index:index + width] for index in range(0, len(values), width)]
    return {"width": width, "height": height, "max_value": maximum, "pixels": rows}


def decode_pgm_tokens(document: str) -> dict[str, Any]:
    """Decode an ASCII P2 PGM image with a token scanner."""
    tokens = _pgm_tokens(document)
    if len(tokens) < 4 or tokens[0] != "P2":
        raise NodeExecutionFailure("image.unsupported-format", "expected an ASCII P2 PGM image")
    return _build_image(int(tokens[1]), int(tokens[2]), int(tokens[3]), [int(item) for item in tokens[4:]])


def decode_pgm_lines(document: str) -> dict[str, Any]:
    """Decode an ASCII P2 PGM image through a line-oriented parser."""
    lines = [line.partition("#")[0].strip() for line in document.splitlines()]
    lines = [line for line in lines if line]
    if not lines or lines[0] != "P2":
        raise NodeExecutionFailure("image.unsupported-format", "expected an ASCII P2 PGM image")
    numeric = " ".join(lines[1:]).split()
    if len(numeric) < 3:
        raise NodeExecutionFailure("image.invalid-header", "PGM header is incomplete")
    return _build_image(
        int(numeric[0]), int(numeric[1]), int(numeric[2]), [int(item) for item in numeric[3:]]
    )


def enhance_image_identity(image: dict[str, Any]) -> dict[str, Any]:
    """Certify and preserve an image that requires no contrast adjustment."""
    return {
        **image,
        "pixels": [list(row) for row in image["pixels"]],
        "enhancement": "identity",
    }


def enhance_image_minmax(image: dict[str, Any]) -> dict[str, Any]:
    """Stretch grayscale values deterministically across the declared range."""
    values = [int(value) for row in image["pixels"] for value in row]
    low, high = min(values), max(values)
    maximum = int(image["max_value"])
    if high == low:
        pixels = [list(row) for row in image["pixels"]]
    else:
        pixels = [
            [round((int(value) - low) * maximum / (high - low)) for value in row]
            for row in image["pixels"]
        ]
    return {**image, "pixels": pixels, "enhancement": "minmax"}


def inspect_image_mean(image: dict[str, Any]) -> dict[str, Any]:
    """Measure dimensions, range, mean, and contrast directly from pixels."""
    values = [int(value) for row in image["pixels"] for value in row]
    return {
        "width": int(image["width"]),
        "height": int(image["height"]),
        "minimum": min(values),
        "maximum": max(values),
        "mean": sum(values) / len(values),
        "contrast": max(values) - min(values),
        "enhancement": image.get("enhancement", "unknown"),
        "method": "direct",
    }


def inspect_image_histogram(image: dict[str, Any]) -> dict[str, Any]:
    """Measure the same properties through an explicit histogram."""
    values = [int(value) for row in image["pixels"] for value in row]
    histogram: dict[int, int] = {}
    for value in values:
        histogram[value] = histogram.get(value, 0) + 1
    minimum, maximum = min(histogram), max(histogram)
    weighted_sum = sum(value * count for value, count in histogram.items())
    return {
        "width": int(image["width"]),
        "height": int(image["height"]),
        "minimum": minimum,
        "maximum": maximum,
        "mean": weighted_sum / len(values),
        "contrast": maximum - minimum,
        "enhancement": image.get("enhancement", "unknown"),
        "method": "histogram",
    }


def _record_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def normalize_records_conservative(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize keys, trim strings, and lowercase email addresses."""
    normalized: list[dict[str, Any]] = []
    for record in records:
        item = {
            _record_key(str(key)): (value.strip() if isinstance(value, str) else value)
            for key, value in record.items()
        }
        if isinstance(item.get("email"), str):
            item["email"] = item["email"].lower()
        normalized.append(item)
    return normalized


def normalize_records_aggressive(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply conservative cleanup plus person/company and phone normalization."""
    normalized = normalize_records_conservative(records)
    for item in normalized:
        if isinstance(item.get("name"), str):
            item["name"] = " ".join(item["name"].split()).title()
        if isinstance(item.get("company"), str):
            item["company"] = re.sub(r"[^A-Za-z0-9 ]+", "", item["company"])
            item["company"] = " ".join(item["company"].split()).title()
        if isinstance(item.get("phone"), str):
            item["phone"] = re.sub(r"\D", "", item["phone"])
    return normalized


def deduplicate_records_exact(
    records: list[dict[str, Any]], key_fields: tuple[str, ...]
) -> list[dict[str, Any]]:
    """Keep the first record for each exact configured key."""
    seen: set[tuple[Any, ...]] = set()
    kept: list[dict[str, Any]] = []
    for record in records:
        key = tuple(record.get(field) for field in key_fields)
        if key not in seen:
            seen.add(key)
            kept.append(dict(record))
    return kept


def deduplicate_records_normalized(
    records: list[dict[str, Any]], key_fields: tuple[str, ...]
) -> list[dict[str, Any]]:
    """Keep the first record after alphanumeric case-folded key comparison."""
    seen: set[tuple[str, ...]] = set()
    kept: list[dict[str, Any]] = []
    for record in records:
        key = tuple(
            re.sub(r"[^a-z0-9]+", "", str(record.get(field, "")).lower())
            for field in key_fields
        )
        if key not in seen:
            seen.add(key)
            kept.append(dict(record))
    return kept


def sort_records(records: list[dict[str, Any]], sort_key: str) -> list[dict[str, Any]]:
    """Emit records in a deterministic order without mutating input."""
    return sorted((dict(record) for record in records), key=lambda item: str(item.get(sort_key, "")))


def split_regression_tail(dataset: dict[str, Any], holdout_size: int = 2) -> dict[str, Any]:
    """Reserve the last rows as an ordered holdout."""
    rows = [dict(row) for row in dataset["rows"]]
    if holdout_size <= 0 or len(rows) <= holdout_size:
        raise NodeExecutionFailure("ml.invalid-split", "holdout_size leaves no training rows")
    return {
        "train": rows[:-holdout_size],
        "test": rows[-holdout_size:],
        "predict": list(dataset.get("predict", [])),
        "split": "tail",
    }


def split_regression_alternating(dataset: dict[str, Any]) -> dict[str, Any]:
    """Use alternating rows for deterministic train and holdout partitions."""
    rows = [dict(row) for row in dataset["rows"]]
    train = [row for index, row in enumerate(rows) if index % 3 != 2]
    test = [row for index, row in enumerate(rows) if index % 3 == 2]
    if not train or not test:
        raise NodeExecutionFailure("ml.invalid-split", "alternating split needs at least three rows")
    return {
        "train": train,
        "test": test,
        "predict": list(dataset.get("predict", [])),
        "split": "alternating",
    }


def train_mean_regressor(split: dict[str, Any]) -> dict[str, Any]:
    """Fit an intercept-only regression baseline."""
    targets = [float(row["y"]) for row in split["train"]]
    return {"kind": "mean", "mean": sum(targets) / len(targets)}


def train_linear_regressor(split: dict[str, Any]) -> dict[str, Any]:
    """Fit one-feature ordinary least squares using deterministic arithmetic."""
    points = [(float(row["x"]), float(row["y"])) for row in split["train"]]
    mean_x = sum(x for x, _ in points) / len(points)
    mean_y = sum(y for _, y in points) / len(points)
    denominator = sum((x - mean_x) ** 2 for x, _ in points)
    if denominator == 0:
        raise NodeExecutionFailure("ml.constant-feature", "linear fit requires nonconstant x")
    slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / denominator
    return {"kind": "linear", "intercept": mean_y - slope * mean_x, "slope": slope}


def evaluate_regressor(split: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    """Generate holdout and requested predictions with an RMSE measurement."""
    def predict(x: float) -> float:
        if model["kind"] == "mean":
            return float(model["mean"])
        if model["kind"] == "linear":
            return float(model["intercept"]) + float(model["slope"]) * x
        raise NodeExecutionFailure("ml.unknown-model", "model kind is not supported")

    actual = [float(row["y"]) for row in split["test"]]
    holdout_predictions = [predict(float(row["x"])) for row in split["test"]]
    rmse = math.sqrt(sum((left - right) ** 2 for left, right in zip(actual, holdout_predictions)) / len(actual))
    requested = [predict(float(value)) for value in split["predict"]]
    return {
        "model": model,
        "split": split["split"],
        "holdout_actual": actual,
        "holdout_predictions": holdout_predictions,
        "predictions": requested,
        "rmse": rmse,
    }


def split_classification_tail(
    dataset: dict[str, Any], holdout_size: int = 2
) -> dict[str, Any]:
    """Reserve the last labeled rows as a deterministic classification holdout."""
    rows = [dict(row) for row in dataset["rows"]]
    if holdout_size <= 0 or len(rows) <= holdout_size:
        raise NodeExecutionFailure(
            "ml.invalid-split", "holdout_size leaves no classification training rows"
        )
    return {
        "train": rows[:-holdout_size],
        "test": rows[-holdout_size:],
        "predict": list(dataset.get("predict", [])),
        "split": "tail",
    }


def split_classification_alternating(dataset: dict[str, Any]) -> dict[str, Any]:
    """Use alternating labeled rows for deterministic classification partitions."""
    rows = [dict(row) for row in dataset["rows"]]
    train = [row for index, row in enumerate(rows) if index % 3 != 2]
    test = [row for index, row in enumerate(rows) if index % 3 == 2]
    if not train or not test:
        raise NodeExecutionFailure(
            "ml.invalid-split", "alternating classification split needs three rows"
        )
    return {
        "train": train,
        "test": test,
        "predict": list(dataset.get("predict", [])),
        "split": "alternating",
    }


def train_majority_classifier(split: dict[str, Any]) -> dict[str, Any]:
    """Fit a deterministic majority-class control model."""
    counts: dict[Any, int] = {}
    for row in split["train"]:
        label = row["label"]
        counts[label] = counts.get(label, 0) + 1
    if not counts:
        raise NodeExecutionFailure("ml.empty-training-set", "no labels are available")
    majority = sorted(counts, key=lambda label: (-counts[label], repr(label)))[0]
    return {"kind": "majority", "label": majority}


def train_threshold_classifier(split: dict[str, Any]) -> dict[str, Any]:
    """Fit a one-feature binary threshold from class-conditional means."""
    grouped: dict[Any, list[float]] = {}
    for row in split["train"]:
        grouped.setdefault(row["label"], []).append(float(row["x"]))
    if len(grouped) != 2:
        raise NodeExecutionFailure(
            "ml.nonbinary-target", "threshold classifier requires exactly two labels"
        )
    ordered = sorted(
        ((sum(values) / len(values), label) for label, values in grouped.items()),
        key=lambda item: (item[0], repr(item[1])),
    )
    return {
        "kind": "threshold",
        "threshold": (ordered[0][0] + ordered[1][0]) / 2,
        "low_label": ordered[0][1],
        "high_label": ordered[1][1],
    }


def evaluate_classifier(split: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    """Measure holdout accuracy and produce requested class predictions."""
    def predict(x: float) -> Any:
        if model["kind"] == "majority":
            return model["label"]
        if model["kind"] == "threshold":
            return (
                model["low_label"]
                if x <= float(model["threshold"])
                else model["high_label"]
            )
        raise NodeExecutionFailure("ml.unknown-model", "classifier kind is not supported")

    actual = [row["label"] for row in split["test"]]
    holdout_predictions = [predict(float(row["x"])) for row in split["test"]]
    accuracy = sum(
        left == right for left, right in zip(actual, holdout_predictions)
    ) / len(actual)
    return {
        "model": model,
        "split": split["split"],
        "holdout_actual": actual,
        "holdout_predictions": holdout_predictions,
        "predictions": [predict(float(value)) for value in split["predict"]],
        "accuracy": accuracy,
    }


__all__ = [
    "decode_pgm_lines",
    "decode_pgm_tokens",
    "deduplicate_records_exact",
    "deduplicate_records_normalized",
    "enhance_image_identity",
    "enhance_image_minmax",
    "evaluate_classifier",
    "evaluate_regressor",
    "extract_document_lines",
    "extract_document_regex",
    "extract_page_html_parser",
    "extract_page_regex",
    "inspect_image_histogram",
    "inspect_image_mean",
    "load_web_source_offline",
    "load_web_source_urllib",
    "normalize_document_compact",
    "normalize_document_conservative",
    "normalize_records_aggressive",
    "normalize_records_conservative",
    "project_document_schema",
    "project_page_schema",
    "sort_records",
    "split_classification_alternating",
    "split_classification_tail",
    "split_regression_alternating",
    "split_regression_tail",
    "train_linear_regressor",
    "train_majority_classifier",
    "train_mean_regressor",
    "train_threshold_classifier",
]
