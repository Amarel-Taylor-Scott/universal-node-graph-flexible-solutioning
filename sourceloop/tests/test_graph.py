from __future__ import annotations

from sourceloop.domain import CaseCreate, CaseKind
from sourceloop.engine import SourceLoopEngine
from sourceloop.graph import GraphProjector


def test_graph_and_geojson_projection(engine: SourceLoopEngine) -> None:
    case = engine.create_case(
        CaseCreate(
            title="Graph test",
            kind=CaseKind.CIVIC_INTELLIGENCE,
            pack="civic_intelligence",
            objective="Map a public organization.",
            requester_name="Test",
            demo=True,
            requirements={"geography": "Example"},
        )
    )
    case = engine.run_until_blocked(case.id)
    projector = GraphProjector()
    graph = projector.build_networkx([case])
    geojson = projector.geojson([case])
    assert case.id in graph
    assert graph.number_of_nodes() >= 3
    assert geojson["type"] == "FeatureCollection"
    assert geojson["features"]
