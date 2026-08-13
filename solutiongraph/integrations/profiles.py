"""Reference integration profiles; these describe projections, not live connectors."""

from solutiongraph.integrations.model import IntegrationAdapterProfile

OPENAPI_ADAPTER = IntegrationAdapterProfile(
    id="adapter.openapi",
    source_kind="standard.openapi",
    supported_versions=("3.0", "3.1", "3.2"),
    output_kind="projection.interface-operations",
    description="Project OpenAPI path operations into typed authoring evidence.",
    limitations=(
        "The projection does not resolve remote references, generate clients, send requests, or certify OpenAPI conformance.",
    ),
)
CLOUDEVENTS_ADAPTER = IntegrationAdapterProfile(
    id="adapter.cloudevents",
    source_kind="standard.cloudevents",
    supported_versions=("1.0",),
    output_kind="projection.event-types",
    description="Project CloudEvents envelopes into explicit event-type operations.",
    limitations=(
        "The projection does not verify transport delivery, signatures, data schemas, or producer authority.",
    ),
)
BPMN_ADAPTER = IntegrationAdapterProfile(
    id="adapter.bpmn",
    source_kind="standard.bpmn",
    supported_versions=("2.0", "2.0.2"),
    output_kind="projection.workflow-structure",
    description="Project BPMN flow nodes and sequence dependencies into authoring evidence.",
    limitations=(
        "The projection is structural; it does not implement BPMN token, compensation, transaction, timer, or engine semantics.",
    ),
)


def _orchestrator(
    suffix: str,
    source_kind: str,
    versions: tuple[str, ...],
    description: str,
) -> IntegrationAdapterProfile:
    return IntegrationAdapterProfile(
        id=f"adapter.orchestrator.{suffix}",
        source_kind=source_kind,
        supported_versions=versions,
        output_kind="projection.frozen-plan",
        description=description,
        limitations=(
            "The export is a portable manifest, not deployable native code; an authorized adapter must enforce runtime, secret, retry, and isolation policy.",
        ),
    )


AIRFLOW_ADAPTER = _orchestrator(
    "airflow",
    "orchestrator.airflow",
    ("3",),
    "Preserve frozen route identity for an Airflow DAG/task adapter.",
)
DAGSTER_ADAPTER = _orchestrator(
    "dagster",
    "orchestrator.dagster",
    ("1",),
    "Preserve frozen route identity for a Dagster asset/op adapter.",
)
TEMPORAL_ADAPTER = _orchestrator(
    "temporal",
    "orchestrator.temporal",
    ("1",),
    "Preserve frozen route identity for a Temporal workflow/activity adapter.",
)
KUBERNETES_ADAPTER = _orchestrator(
    "kubernetes",
    "orchestrator.kubernetes-job",
    ("batch/v1",),
    "Preserve frozen route identity for Kubernetes Job generation.",
)

REFERENCE_INTEGRATION_ADAPTERS = (
    OPENAPI_ADAPTER,
    CLOUDEVENTS_ADAPTER,
    BPMN_ADAPTER,
    AIRFLOW_ADAPTER,
    DAGSTER_ADAPTER,
    TEMPORAL_ADAPTER,
    KUBERNETES_ADAPTER,
)
INTEGRATION_ADAPTER_BY_ID = {item.id: item for item in REFERENCE_INTEGRATION_ADAPTERS}


def validate_integration_profiles() -> list[str]:
    problems: list[str] = []
    ids = [item.id for item in REFERENCE_INTEGRATION_ADAPTERS]
    if len(ids) != len(set(ids)):
        problems.append("integration adapter ids must be unique")
    for index, profile in enumerate(REFERENCE_INTEGRATION_ADAPTERS):
        problems.extend(profile.validate(f"integration_adapters[{index}]"))
    return problems


__all__ = [
    "AIRFLOW_ADAPTER",
    "BPMN_ADAPTER",
    "CLOUDEVENTS_ADAPTER",
    "DAGSTER_ADAPTER",
    "INTEGRATION_ADAPTER_BY_ID",
    "KUBERNETES_ADAPTER",
    "OPENAPI_ADAPTER",
    "REFERENCE_INTEGRATION_ADAPTERS",
    "TEMPORAL_ADAPTER",
    "validate_integration_profiles",
]
