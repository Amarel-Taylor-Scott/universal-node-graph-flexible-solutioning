from __future__ import annotations

from sourceloop.domain import ApprovalRequest, CaseCreate, CaseKind
from sourceloop.engine import SourceLoopEngine
from sourceloop.graph import GraphProjector


def test_graph_and_geojson_projection(engine: SourceLoopEngine) -> None:
    case = engine.create_case(
        CaseCreate(
            title="Map test",
            kind=CaseKind.QUOTE_INTELLIGENCE,
            pack="facilities_quote",
            objective="Collect two comparable quotes.",
            requester_name="Test Procurement",
            demo=True,
            requirements={"service": "commercial service", "minimum_quotes": 2},
        )
    )
    case = engine.run_until_blocked(case.id)
    for action in case.actions:
        case = engine.approve_action(case.id, action.id, ApprovalRequest(approver="reviewer"))
    case = engine.dispatch_approved(case.id)
    case = engine.simulate_demo_replies(case.id)

    projector = GraphProjector()
    graph = projector.build_networkx([case])
    payload = projector.node_link([case])
    geojson = projector.geojson([case])

    assert graph.number_of_nodes() > len(case.contacts)
    assert graph.number_of_edges() > 0
    assert payload["nodes"]
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 1 + len(case.contacts)
