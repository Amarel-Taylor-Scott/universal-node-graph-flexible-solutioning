"""Safe structural projections for OpenAPI, CloudEvents, and BPMN inputs."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any
from xml.etree import ElementTree

from solutiongraph.integrations.model import IntegrationProjection, ProjectedOperation
from solutiongraph.integrations.profiles import (
    BPMN_ADAPTER,
    CLOUDEVENTS_ADAPTER,
    OPENAPI_ADAPTER,
)
from solutiongraph.model import canonical_json, sha256_digest

_HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
_BPMN_FLOW_NODES = {
    "task",
    "userTask",
    "serviceTask",
    "scriptTask",
    "manualTask",
    "businessRuleTask",
    "sendTask",
    "receiveTask",
    "callActivity",
    "subProcess",
    "startEvent",
    "endEvent",
    "intermediateCatchEvent",
    "intermediateThrowEvent",
    "boundaryEvent",
    "exclusiveGateway",
    "inclusiveGateway",
    "parallelGateway",
    "eventBasedGateway",
    "complexGateway",
}


def _slug(value: str, *, fallback: str = "unnamed") -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return normalized or fallback


def _projection_id(prefix: str, source_digest: str) -> str:
    return f"projection.{prefix}.{source_digest.removeprefix('sha256:')[:20]}"


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{path} must be a string-keyed object")
    return value


def project_openapi(document: Mapping[str, Any]) -> IntegrationProjection:
    """Project OpenAPI operations without resolving references or making requests."""

    root = _mapping(document, "OpenAPI document")
    version = root.get("openapi")
    if not isinstance(version, str) or not any(
        version.startswith(item + ".") or version == item
        for item in OPENAPI_ADAPTER.supported_versions
    ):
        raise ValueError("OpenAPI version must be a supported 3.0, 3.1, or 3.2 release")
    paths = _mapping(root.get("paths", {}), "OpenAPI paths")
    if not paths:
        raise ValueError("OpenAPI projection requires at least one path operation")
    source_digest = sha256_digest(root)
    operations: list[ProjectedOperation] = []
    used_ids: set[str] = set()
    root_security = root.get("security", ())
    for path_name, raw_path_item in sorted(paths.items()):
        path_item = _mapping(raw_path_item, f"OpenAPI path {path_name}")
        inherited_parameters = path_item.get("parameters", ())
        if not isinstance(inherited_parameters, Sequence) or isinstance(
            inherited_parameters, (str, bytes)
        ):
            raise ValueError(f"OpenAPI path {path_name} parameters must be an array")
        for method in _HTTP_METHODS:
            raw_operation = path_item.get(method)
            if raw_operation is None:
                continue
            operation = _mapping(raw_operation, f"OpenAPI operation {method} {path_name}")
            raw_id = operation.get("operationId")
            if not isinstance(raw_id, str) or not raw_id.strip():
                raw_id = f"{method}-{path_name}"
            base_id = f"operation.openapi.{_slug(raw_id)}"
            operation_id = base_id
            duplicate = 2
            while operation_id in used_ids:
                operation_id = f"{base_id}-{duplicate}"
                duplicate += 1
            used_ids.add(operation_id)

            parameters = operation.get("parameters", ())
            if not isinstance(parameters, Sequence) or isinstance(parameters, (str, bytes)):
                raise ValueError(f"OpenAPI operation {raw_id} parameters must be an array")
            parameter_types: list[str] = []
            for raw_parameter in (*inherited_parameters, *parameters):
                parameter = _mapping(raw_parameter, f"OpenAPI operation {raw_id} parameter")
                if "$ref" in parameter:
                    parameter_types.append(
                        f"type.openapi.parameter-ref.{_slug(str(parameter['$ref']))}"
                    )
                    continue
                name = parameter.get("name")
                location = parameter.get("in")
                if not isinstance(name, str) or not isinstance(location, str):
                    raise ValueError(f"OpenAPI operation {raw_id} parameter needs name and in")
                parameter_types.append(
                    f"type.openapi.parameter.{_slug(location)}.{_slug(name)}"
                )
            request_body = operation.get("requestBody")
            if request_body is not None:
                request = _mapping(request_body, f"OpenAPI operation {raw_id} requestBody")
                content = _mapping(request.get("content", {}), "OpenAPI request content")
                parameter_types.extend(
                    f"type.openapi.request.{_slug(media_type)}" for media_type in sorted(content)
                )
            responses = _mapping(
                operation.get("responses", {}), f"OpenAPI operation {raw_id} responses"
            )
            if not responses:
                raise ValueError(f"OpenAPI operation {raw_id} must declare responses")
            output_types: list[str] = []
            for status, raw_response in sorted(responses.items()):
                response = _mapping(raw_response, f"OpenAPI response {status}")
                content = response.get("content", {})
                if content:
                    content_map = _mapping(content, f"OpenAPI response {status} content")
                    output_types.extend(
                        f"type.openapi.response.{_slug(status)}.{_slug(media_type)}"
                        for media_type in sorted(content_map)
                    )
                else:
                    output_types.append(f"type.openapi.response.{_slug(status)}")
            read_only = method in {"get", "head", "options", "trace"}
            effect = "network.read" if read_only else "network.write"
            security = operation.get("security", root_security)
            operations.append(
                ProjectedOperation(
                    id=operation_id,
                    source_ref=f"{method.upper()} {path_name}",
                    kind="operation.http",
                    label=str(operation.get("summary") or operation.get("description") or raw_id),
                    input_type_ids=tuple(dict.fromkeys(parameter_types)),
                    output_type_ids=tuple(dict.fromkeys(output_types)),
                    effects=(effect,),
                    permissions=(effect,),
                    metadata=(
                        ("openapi.method", method.upper()),
                        ("openapi.path", path_name),
                        ("openapi.security-declared", bool(security)),
                        ("openapi.deprecated", bool(operation.get("deprecated", False))),
                    ),
                )
            )
    if not operations:
        raise ValueError("OpenAPI document contains no supported path operations")
    projection = IntegrationProjection(
        id=_projection_id("openapi", source_digest),
        adapter_id=OPENAPI_ADAPTER.id,
        adapter_digest=OPENAPI_ADAPTER.digest,
        source_kind=OPENAPI_ADAPTER.source_kind,
        source_version=version,
        source_digest=source_digest,
        operations=tuple(operations),
        limitations=OPENAPI_ADAPTER.limitations,
    )
    problems = projection.validate()
    if problems:
        raise ValueError("invalid OpenAPI projection: " + "; ".join(problems))
    return projection


def project_cloudevents(events: Sequence[Mapping[str, Any]]) -> IntegrationProjection:
    """Project exact CloudEvents envelope types from supplied event fixtures."""

    if not events:
        raise ValueError("CloudEvents projection requires at least one event")
    normalized: list[Mapping[str, Any]] = []
    by_type: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for index, raw_event in enumerate(events):
        event = _mapping(raw_event, f"CloudEvent[{index}]")
        for field in ("specversion", "id", "source", "type"):
            if not isinstance(event.get(field), str) or not str(event[field]).strip():
                raise ValueError(f"CloudEvent[{index}].{field} must be a nonempty string")
        if not str(event["specversion"]).startswith("1.0"):
            raise ValueError("CloudEvents projection supports the 1.0 specification line")
        canonical_json(event)
        normalized.append(event)
        by_type[str(event["type"])].append(event)
    source_digest = sha256_digest(normalized)
    operations: list[ProjectedOperation] = []
    for event_type, type_events in sorted(by_type.items()):
        sources = tuple(sorted({str(event["source"]) for event in type_events}))
        data_schemas = tuple(
            sorted(
                {
                    str(event["dataschema"])
                    for event in type_events
                    if isinstance(event.get("dataschema"), str)
                }
            )
        )
        content_types = tuple(
            sorted(
                {
                    str(event["datacontenttype"])
                    for event in type_events
                    if isinstance(event.get("datacontenttype"), str)
                }
            )
        )
        output_types = (
            tuple(f"type.cloudevent.data.{_slug(item)}" for item in data_schemas)
            or (f"type.cloudevent.data.{_slug(event_type)}",)
        )
        operations.append(
            ProjectedOperation(
                id=f"operation.cloudevent.consume.{_slug(event_type)}",
                source_ref=event_type,
                kind="operation.event-consume",
                label=f"Consume {event_type}",
                input_type_ids=("type.cloudevent.envelope",),
                output_type_ids=output_types,
                effects=("event.consume",),
                permissions=("event.read",),
                metadata=(
                    ("cloudevents.event-count", len(type_events)),
                    ("cloudevents.sources", sources),
                    ("cloudevents.data-schemas", data_schemas),
                    ("cloudevents.content-types", content_types),
                ),
            )
        )
    projection = IntegrationProjection(
        id=_projection_id("cloudevents", source_digest),
        adapter_id=CLOUDEVENTS_ADAPTER.id,
        adapter_digest=CLOUDEVENTS_ADAPTER.digest,
        source_kind=CLOUDEVENTS_ADAPTER.source_kind,
        source_version="1.0",
        source_digest=source_digest,
        operations=tuple(operations),
        limitations=CLOUDEVENTS_ADAPTER.limitations,
    )
    problems = projection.validate()
    if problems:
        raise ValueError("invalid CloudEvents projection: " + "; ".join(problems))
    return projection


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def project_bpmn(xml: str | bytes, *, max_bytes: int = 5_000_000) -> IntegrationProjection:
    """Project BPMN flow structure with DTD/entity expansion rejected up front."""

    payload = xml.encode("utf-8") if isinstance(xml, str) else xml
    if not payload or len(payload) > max_bytes:
        raise ValueError("BPMN payload must be nonempty and within max_bytes")
    upper = payload.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("BPMN projection rejects DTD and entity declarations")
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise ValueError(f"BPMN XML is malformed: {exc}") from exc
    if _local_name(root.tag) != "definitions":
        raise ValueError("BPMN root element must be definitions")

    source_digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    nodes: dict[str, Any] = {}
    flows: list[tuple[str, str, str]] = []
    for element in root.iter():
        local = _local_name(element.tag)
        if local in _BPMN_FLOW_NODES:
            source_id = element.attrib.get("id", "")
            if not source_id:
                raise ValueError(f"BPMN {local} requires an id")
            if source_id in nodes:
                raise ValueError(f"duplicate BPMN flow-node id {source_id!r}")
            nodes[source_id] = element
        elif local == "sequenceFlow":
            flow_id = element.attrib.get("id", "")
            source = element.attrib.get("sourceRef", "")
            target = element.attrib.get("targetRef", "")
            if not flow_id or not source or not target:
                raise ValueError("BPMN sequenceFlow requires id, sourceRef, and targetRef")
            flows.append((flow_id, source, target))
    if not nodes:
        raise ValueError("BPMN projection requires at least one supported flow node")
    unknown_refs = sorted(
        {reference for _, source, target in flows for reference in (source, target)}
        - set(nodes)
    )
    if unknown_refs:
        raise ValueError("BPMN sequence flows reference unsupported nodes: " + ", ".join(unknown_refs))
    operation_id_by_source = {
        source_id: f"operation.bpmn.{_slug(source_id)}" for source_id in nodes
    }
    if len(set(operation_id_by_source.values())) != len(operation_id_by_source):
        raise ValueError("BPMN ids collide after portable identifier normalization")
    dependencies: dict[str, list[str]] = defaultdict(list)
    for _, source, target in flows:
        dependencies[target].append(operation_id_by_source[source])
    operations: list[ProjectedOperation] = []
    for source_id, element in nodes.items():
        local = _local_name(element.tag)
        effects: tuple[str, ...] = ()
        permissions: tuple[str, ...] = ()
        if local == "userTask":
            effects = ("human.request",)
            permissions = ("human.review",)
        elif local in {"serviceTask", "sendTask"}:
            effects = ("network.write",)
            permissions = ("network.write",)
        elif local == "receiveTask":
            effects = ("network.read",)
            permissions = ("network.read",)
        operations.append(
            ProjectedOperation(
                id=operation_id_by_source[source_id],
                source_ref=source_id,
                kind=f"operation.bpmn-{_slug(local)}",
                label=element.attrib.get("name") or source_id,
                dependencies=tuple(dict.fromkeys(dependencies[source_id])),
                effects=effects,
                permissions=permissions,
                metadata=(
                    ("bpmn.element-kind", local),
                    (
                        "bpmn.outgoing-count",
                        sum(source == source_id for _, source, _ in flows),
                    ),
                    (
                        "bpmn.incoming-count",
                        sum(target == source_id for _, _, target in flows),
                    ),
                ),
            )
        )
    projection = IntegrationProjection(
        id=_projection_id("bpmn", source_digest),
        adapter_id=BPMN_ADAPTER.id,
        adapter_digest=BPMN_ADAPTER.digest,
        source_kind=BPMN_ADAPTER.source_kind,
        source_version="2.0.2",
        source_digest=source_digest,
        operations=tuple(operations),
        limitations=BPMN_ADAPTER.limitations,
    )
    problems = projection.validate()
    if problems:
        raise ValueError("invalid BPMN projection: " + "; ".join(problems))
    return projection


__all__ = ["project_bpmn", "project_cloudevents", "project_openapi"]
