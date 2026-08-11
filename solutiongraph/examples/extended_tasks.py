"""Additional executable DAG fixtures for cross-domain Arena task families.

The algorithms are intentionally small standard-library references.  They
exercise real typed transformations and independent oracles; they are not
claims of production domain accuracy or external-authority validation.
"""

from __future__ import annotations

import math
import re
from copy import deepcopy
from typing import Any

from solutiongraph.evidence import Objective
from solutiongraph.examples.tasks import ExampleRoute, ExecutableExample
from solutiongraph.executor import (
    CallableVerifier,
    ExecutionPolicy,
    VerificationContext,
    VerificationResult,
    callable_implementation_digest,
)
from solutiongraph.experiments import ExperimentCase
from solutiongraph.model import (
    Candidate,
    Edge,
    GraphInput,
    GraphOutput,
    Idempotency,
    NodeSpec,
    ParameterSpec,
    Port,
    ProgramGraph,
    Registry,
    SemanticSlot,
    ValueType,
)

WORKFLOW_PAYLOAD = ValueType("example.extended-workflow-payload")


def _state(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    result = deepcopy(payload)
    state = result.setdefault("state", {})
    result.setdefault("completed", [])
    result.setdefault("warnings", [])
    return result, state


def _apply_step(
    payload: dict[str, Any], domain: str, operation: str
) -> dict[str, Any]:
    result, state = _state(payload)
    raw = result["raw"]
    if domain == "contact":
        if operation == "parse":
            state["email"] = str(raw["email"]).strip()
            state["phone"] = str(raw["phone"]).strip()
        elif operation == "normalize":
            state["email"] = state["email"].lower()
            state["phone"] = re.sub(r"\D", "", state["phone"])
        elif operation == "verify":
            state["email_valid"] = bool(re.fullmatch(
                r"[^@\s]+@[^@\s]+\.[^@\s]+", state["email"]
            ))
            state["phone_valid"] = len(state["phone"]) in (10, 11)
        elif operation == "consent":
            state["can_contact"] = bool(
                raw.get("consent", {}).get("email") and state["email_valid"]
            )
    elif domain == "web-change":
        if operation == "canonicalize":
            state["prior"] = dict(sorted(raw["prior"].items()))
            state["current"] = dict(sorted(raw["current"].items()))
        elif operation == "diff":
            keys = sorted(set(state["prior"]) | set(state["current"]))
            state["changed_fields"] = [
                key for key in keys if state["prior"].get(key) != state["current"].get(key)
            ]
        elif operation == "corroborate":
            state["significant"] = "price" in state["changed_fields"]
            state["evidence_count"] = 2
    elif domain == "reconciliation":
        if operation == "normalize":
            state["left"] = [
                {**row, "amount": round(float(str(row["amount"]).replace("$", "")), 2)}
                for row in raw["left"]
            ]
            state["right"] = [
                {**row, "amount": round(float(str(row["amount"]).replace("$", "")), 2)}
                for row in raw["right"]
            ]
        elif operation == "match":
            right = {row["id"]: row for row in state["right"]}
            state["matches"] = [
                {"id": row["id"], "left": row["amount"], "right": right[row["id"]]["amount"]}
                for row in state["left"]
                if row["id"] in right
            ]
        elif operation == "balance":
            state["residual"] = round(sum(
                row["left"] - row["right"] for row in state["matches"]
            ), 2)
            state["matched_count"] = len(state["matches"])
    elif domain == "pii":
        document = str(raw["document"])
        pattern = r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\b\d{3}-\d{2}-\d{4}\b"
        if operation == "detect":
            state["spans"] = re.findall(pattern, document)
        elif operation == "redact":
            state["redacted"] = re.sub(pattern, "[REDACTED]", document)
        elif operation == "leakage-check":
            state["leakage"] = bool(re.search(pattern, state["redacted"]))
            state["redaction_count"] = state["redacted"].count("[REDACTED]")
    elif domain == "schema-migration":
        if operation == "transform":
            migrated = []
            for row in raw["rows"]:
                first, _, last = row["full_name"].partition(" ")
                migrated.append({
                    "id": int(row["id"]),
                    "first_name": first,
                    "last_name": last,
                    "amount": float(row["amount"]),
                })
            state["rows"] = migrated
        elif operation == "validate":
            required = {"id", "first_name", "last_name", "amount"}
            state["valid"] = all(set(row) == required for row in state["rows"])
        elif operation == "shadow-compare":
            state["row_count_preserved"] = len(state["rows"]) == len(raw["rows"])
            state["amount_preserved"] = math.isclose(
                sum(row["amount"] for row in state["rows"]),
                sum(float(row["amount"]) for row in raw["rows"]),
            )
    elif domain == "incident":
        if operation == "parse":
            state["events"] = [
                {**event, "level": event["level"].lower()} for event in raw["events"]
            ]
        elif operation == "correlate":
            counts: dict[str, int] = {}
            for event in state["events"]:
                if event["level"] == "error":
                    counts[event["service"]] = counts.get(event["service"], 0) + 1
            state["error_counts"] = counts
        elif operation == "rank":
            state["ranked_services"] = [
                service for service, _ in sorted(
                    state["error_counts"].items(), key=lambda item: (-item[1], item[0])
                )
            ]
    elif domain == "dependency":
        if operation == "resolve":
            state["dependencies"] = sorted(set(raw["dependencies"]))
        elif operation == "scan":
            state["findings"] = [
                {"package": package, **raw["advisories"][package]}
                for package in state["dependencies"]
                if package in raw["advisories"]
            ]
        elif operation == "policy":
            state["blocked"] = any(
                finding["severity"] in ("high", "critical")
                for finding in state["findings"]
            )
            state["sbom_count"] = len(state["dependencies"])
    elif domain == "recommendation":
        if operation == "eligibility":
            state["eligible"] = [item for item in raw["catalog"] if item["available"]]
        elif operation == "score":
            preferred = set(raw["preferred_categories"])
            state["scored"] = sorted(
                (
                    {
                        **item,
                        "score": float(item["popularity"]) + (
                            10.0 if item["category"] in preferred else 0.0
                        ),
                    }
                    for item in state["eligible"]
                ),
                key=lambda item: (-item["score"], item["id"]),
            )
        elif operation == "diversify":
            selected = []
            used = set()
            for item in state["scored"]:
                if item["category"] not in used or len(selected) < 1:
                    selected.append(item["id"])
                    used.add(item["category"])
                if len(selected) == 2:
                    break
            state["ranking"] = selected
    elif domain == "scientific":
        if operation == "design":
            groups: dict[str, list[float]] = {}
            for row in raw["observations"]:
                groups.setdefault(row["group"], []).append(float(row["value"]))
            state["groups"] = groups
        elif operation == "analyze":
            means = {
                group: sum(values) / len(values)
                for group, values in state["groups"].items()
            }
            state["means"] = means
            state["effect"] = means["treatment"] - means["control"]
        elif operation == "robustness":
            state["stable_positive_effect"] = (
                state["effect"] > 0
                and min(state["groups"]["treatment"])
                > max(state["groups"]["control"])
            )
    elif domain == "numerical":
        matrix = raw["matrix"]
        vector = raw["vector"]
        if operation == "validate":
            determinant = matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
            state["determinant"] = float(determinant)
            state["symmetric"] = matrix[0][1] == matrix[1][0]
        elif operation == "solve":
            determinant = state["determinant"]
            state["solution"] = [
                (vector[0] * matrix[1][1] - matrix[0][1] * vector[1]) / determinant,
                (matrix[0][0] * vector[1] - vector[0] * matrix[1][0]) / determinant,
            ]
        elif operation == "residual":
            x = state["solution"]
            residuals = [
                matrix[index][0] * x[0] + matrix[index][1] * x[1] - vector[index]
                for index in range(2)
            ]
            state["residual_norm"] = math.sqrt(sum(value * value for value in residuals))
    else:
        raise ValueError(f"unknown extended domain {domain!r}")
    result["completed"].append(operation)
    return result


def execute_strict_step(
    payload: dict[str, Any], domain: str, operation: str
) -> dict[str, Any]:
    """Execute a deterministic reference operation with its full contract."""
    return _apply_step(payload, domain, operation)


def execute_heuristic_step(
    payload: dict[str, Any], domain: str, operation: str
) -> dict[str, Any]:
    """Execute the operation but disclose that its evidence is only heuristic."""
    result = _apply_step(payload, domain, operation)
    result["warnings"].append(f"{domain}.{operation}:heuristic-only")
    return result


DOMAIN_OPERATIONS = {
    "contact": ("parse", "normalize", "verify", "consent"),
    "web-change": ("canonicalize", "diff", "corroborate"),
    "reconciliation": ("normalize", "match", "balance"),
    "pii": ("detect", "redact", "leakage-check"),
    "schema-migration": ("transform", "validate", "shadow-compare"),
    "incident": ("parse", "correlate", "rank"),
    "dependency": ("resolve", "scan", "policy"),
    "recommendation": ("eligibility", "score", "diversify"),
    "scientific": ("design", "analyze", "robustness"),
    "numerical": ("validate", "solve", "residual"),
}


def _node(domain: str, operation: str, strategy: str) -> NodeSpec:
    function = execute_strict_step if strategy == "strict" else execute_heuristic_step
    return NodeSpec(
        id=f"example.extended.{domain}.{operation}.{strategy}",
        version="1.0.0",
        implementation_digest=callable_implementation_digest(function),
        inputs=(Port("payload", WORKFLOW_PAYLOAD),),
        outputs=(Port("payload", WORKFLOW_PAYLOAD),),
        runtime="python",
        entrypoint=f"{function.__module__}:{function.__name__}",
        description=f"{strategy.title()} reference implementation for {domain}/{operation}.",
        parameters=(
            ParameterSpec("domain", "string", required=True, choices=(domain,)),
            ParameterSpec("operation", "string", required=True, choices=(operation,)),
        ),
        capabilities=(f"extended.{domain}.{operation}",),
        idempotency=Idempotency.IDEMPOTENT,
        source="solutiongraph/examples/extended_tasks.py",
    )


EXTENDED_NODES = tuple(
    _node(domain, operation, strategy)
    for domain, operations in DOMAIN_OPERATIONS.items()
    for operation in operations
    for strategy in ("strict", "heuristic")
)
EXTENDED_CANDIDATES = tuple(
    Candidate(
        id=f"candidate.{node.id}",
        node_id=node.id,
        node_version=node.version,
        implementation_digest=node.implementation_digest,
        parameters={
            "domain": node.id.split(".")[2],
            "operation": node.id.split(".")[3],
        },
    )
    for node in EXTENDED_NODES
)
EXTENDED_REGISTRY = Registry(
    "example.extended-arena-registry",
    "1.0.0",
    EXTENDED_NODES,
    EXTENDED_CANDIDATES,
)


def _program(domain: str, title: str) -> ProgramGraph:
    operations = DOMAIN_OPERATIONS[domain]
    slots = tuple(
        SemanticSlot(
            operation,
            f"Execute the {operation} obligation.",
            (Port("payload", WORKFLOW_PAYLOAD),),
            (Port("payload", WORKFLOW_PAYLOAD),),
            f"The {operation} result is typed, explicit, and independently checkable.",
            group=(f"stage.{domain}",),
            required_capabilities=(f"extended.{domain}.{operation}",),
        )
        for operation in operations
    )
    return ProgramGraph(
        f"example.extended-{domain}",
        "1.0.0",
        title,
        "The independent domain oracle accepts exact fixture facts and no heuristic-only evidence.",
        slots,
        tuple(
            Edge(left, "payload", right, "payload")
            for left, right in zip(operations, operations[1:], strict=False)
        ),
        (GraphInput("payload", WORKFLOW_PAYLOAD, operations[0], "payload"),),
        (GraphOutput("result", WORKFLOW_PAYLOAD, operations[-1], "payload"),),
    )


def _accepted_state(domain: str, state: dict[str, Any]) -> bool:
    if domain == "contact":
        return state.get("email") == "alice@example.com" and state.get("can_contact") is True
    if domain == "web-change":
        return state.get("changed_fields") == ["price"] and state.get("significant") is True
    if domain == "reconciliation":
        return state.get("matched_count") == 2 and state.get("residual") == 0
    if domain == "pii":
        return state.get("redaction_count") == 2 and state.get("leakage") is False
    if domain == "schema-migration":
        return all((state.get("valid"), state.get("row_count_preserved"), state.get("amount_preserved")))
    if domain == "incident":
        return state.get("ranked_services", [None])[0] == "checkout"
    if domain == "dependency":
        return state.get("sbom_count") == 3 and state.get("blocked") is True
    if domain == "recommendation":
        return state.get("ranking") == ["item-a", "item-b"]
    if domain == "scientific":
        return math.isclose(state.get("effect", 0), 3.0) and state.get("stable_positive_effect") is True
    if domain == "numerical":
        return state.get("symmetric") is True and state.get("residual_norm", 1) < 1e-12
    return False


def verify_extended(context: VerificationContext) -> VerificationResult:
    result = context.outputs["result"]
    domain = context.program.id.removeprefix("example.extended-")
    operations = DOMAIN_OPERATIONS[domain]
    accepted = (
        result.get("completed") == list(operations)
        and not result.get("warnings")
        and _accepted_state(domain, result.get("state", {}))
    )
    return VerificationResult(
        accepted,
        "extended-fixture-accepted" if accepted else "extended-fixture-rejected",
        {"quality": 1.0 if accepted else 0.0},
        {"domain": domain, "completed": result.get("completed", [])},
    )


FIXTURES = {
    "contact": {
        "id": "contact-verification",
        "title": "Contact endpoint verification",
        "task": "Parse, normalize, syntactically verify, and consent-gate contact endpoints.",
        "raw": {"email": " Alice@Example.COM ", "phone": "(212) 555-0100", "consent": {"email": True}},
    },
    "web-change": {
        "id": "web-change-monitoring",
        "title": "Verified web change monitoring",
        "task": "Canonicalize captured records, detect changes, and classify significance.",
        "raw": {"prior": {"name": "Widget", "price": 10}, "current": {"name": "Widget", "price": 12}},
    },
    "reconciliation": {
        "id": "transaction-reconciliation",
        "title": "Transaction reconciliation",
        "task": "Normalize two ledgers, match identities, and prove the residual.",
        "raw": {"left": [{"id": "a", "amount": "$10.00"}, {"id": "b", "amount": "20"}], "right": [{"id": "a", "amount": 10}, {"id": "b", "amount": "20.00"}]},
    },
    "pii": {
        "id": "pii-redaction",
        "title": "PII redaction with leakage check",
        "task": "Detect, redact, and independently scan a document for residual PII.",
        "raw": {"document": "Email alice@example.com; SSN 123-45-6789."},
    },
    "schema-migration": {
        "id": "schema-migration",
        "title": "Verified schema migration",
        "task": "Transform rows to a new schema and shadow-check preserved invariants.",
        "raw": {"rows": [{"id": "1", "full_name": "Ada Lovelace", "amount": "12.5"}, {"id": "2", "full_name": "Grace Hopper", "amount": "7.5"}]},
    },
    "incident": {
        "id": "incident-triage",
        "title": "Incident signal triage",
        "task": "Parse, correlate, and rank failing services from captured events.",
        "raw": {"events": [{"service": "checkout", "level": "ERROR"}, {"service": "search", "level": "ERROR"}, {"service": "checkout", "level": "ERROR"}, {"service": "search", "level": "INFO"}]},
    },
    "dependency": {
        "id": "dependency-assurance",
        "title": "Dependency policy assurance",
        "task": "Resolve a dependency set, scan an immutable advisory fixture, and apply policy.",
        "raw": {"dependencies": ["alpha", "beta", "gamma", "alpha"], "advisories": {"beta": {"severity": "high", "id": "ADV-1"}}},
    },
    "recommendation": {
        "id": "recommendation-ranking",
        "title": "Policy-aware recommendation ranking",
        "task": "Filter, score, and diversify eligible catalog items.",
        "raw": {"preferred_categories": ["books"], "catalog": [{"id": "item-a", "category": "books", "popularity": 9, "available": True}, {"id": "item-b", "category": "tools", "popularity": 8, "available": True}, {"id": "item-c", "category": "books", "popularity": 7, "available": True}, {"id": "item-d", "category": "games", "popularity": 20, "available": False}]},
    },
    "scientific": {
        "id": "scientific-experiment",
        "title": "Reproducible scientific comparison",
        "task": "Design grouped observations, estimate an effect, and test robustness.",
        "raw": {"observations": [{"group": "control", "value": 1}, {"group": "control", "value": 2}, {"group": "treatment", "value": 4}, {"group": "treatment", "value": 5}]},
    },
    "numerical": {
        "id": "numerical-linear-system",
        "title": "Verified numerical linear solve",
        "task": "Validate, solve, and independently measure a two-by-two linear system residual.",
        "raw": {"matrix": [[4.0, 1.0], [1.0, 3.0]], "vector": [1.0, 2.0]},
    },
}


def _candidate_id(domain: str, operation: str, strategy: str) -> str:
    return f"candidate.example.extended.{domain}.{operation}.{strategy}"


def _example(domain: str) -> ExecutableExample:
    fixture = FIXTURES[domain]
    operations = DOMAIN_OPERATIONS[domain]
    strict = {
        operation: _candidate_id(domain, operation, "strict")
        for operation in operations
    }
    heuristic = {
        operation: _candidate_id(domain, operation, "heuristic")
        for operation in operations
    }
    return ExecutableExample(
        fixture["id"],
        fixture["title"],
        fixture["task"],
        _program(domain, fixture["task"]),
        (
            ExampleRoute("heuristic-control", "All operations disclose heuristic-only evidence.", heuristic, expected_accepted=False),
            ExampleRoute("strict-reference", "All operations use deterministic reference contracts.", strict),
        ),
        ExperimentCase(
            f"case.extended-{domain}",
            {"payload": {"raw": fixture["raw"]}},
            CallableVerifier("verifier.example.extended", verify_extended),
        ),
        ExecutionPolicy(),
        (
            Objective("quality", "maximize", hard_minimum=1.0),
            Objective("latency_ms", "minimize", weight=0.1),
        ),
        registry=EXTENDED_REGISTRY,
    )


EXTENDED_EXAMPLE_TASKS = tuple(_example(domain) for domain in DOMAIN_OPERATIONS)


__all__ = [
    "DOMAIN_OPERATIONS",
    "EXTENDED_CANDIDATES",
    "EXTENDED_EXAMPLE_TASKS",
    "EXTENDED_NODES",
    "EXTENDED_REGISTRY",
    "WORKFLOW_PAYLOAD",
    "execute_heuristic_step",
    "execute_strict_step",
    "verify_extended",
]
