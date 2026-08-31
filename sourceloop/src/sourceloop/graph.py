"""NetworkX, GeoJSON, and optional City2Graph projections."""

from __future__ import annotations

from typing import Any

import networkx as nx

from .domain import CaseRecord


class GraphProjector:
    """Materializes task-specific graphs from the authoritative case ledger."""

    def build_networkx(self, cases: list[CaseRecord]) -> nx.MultiDiGraph:
        graph = nx.MultiDiGraph(name="sourceloop-intelligence")
        for case in cases:
            graph.add_node(
                case.id,
                node_type="case",
                label=case.title,
                kind=case.kind.value,
                stage=case.stage.value,
                status=case.status.value,
                latitude=case.location.latitude if case.location else None,
                longitude=case.location.longitude if case.location else None,
                quote_count=len(case.quotes),
                claim_count=len(case.claims),
            )
            for contact in case.contacts:
                graph.add_node(
                    contact.id,
                    node_type="contact_route",
                    label=contact.organization_name,
                    role=contact.role_title,
                    endpoint=contact.endpoint,
                    confidence=contact.confidence,
                    geography=contact.geography,
                    latitude=contact.location.latitude if contact.location else None,
                    longitude=contact.location.longitude if contact.location else None,
                )
                graph.add_edge(case.id, contact.id, relation="targets", source="case_state")

            for action in case.actions:
                graph.add_node(
                    action.id,
                    node_type="action",
                    label=action.subject,
                    status=action.status.value,
                    recipient=action.recipient,
                )
                graph.add_edge(case.id, action.id, relation="proposed_action", source="action_ledger")
                matching = next((contact for contact in case.contacts if contact.endpoint == action.recipient), None)
                if matching:
                    graph.add_edge(action.id, matching.id, relation="addressed_to", source="action_ledger")

            for interaction in case.interactions:
                graph.add_node(
                    interaction.id,
                    node_type="interaction",
                    label=interaction.subject,
                    direction=interaction.direction.value,
                    endpoint=interaction.endpoint,
                    evidence_id=interaction.evidence_id,
                    processed=interaction.processed,
                )
                graph.add_edge(case.id, interaction.id, relation="has_interaction", source="evidence_ledger")
                matching = next((contact for contact in case.contacts if contact.endpoint == interaction.endpoint), None)
                if matching:
                    graph.add_edge(matching.id, interaction.id, relation="participated_in", source="evidence_ledger")

            for claim in case.claims:
                graph.add_node(
                    claim.id,
                    node_type="claim",
                    label=claim.predicate,
                    predicate=claim.predicate,
                    claim_kind=claim.kind.value,
                    confidence=claim.confidence,
                    value=str(claim.value),
                    geography=claim.geography_scope,
                    expires_at=claim.expires_at.isoformat() if claim.expires_at else None,
                )
                graph.add_edge(case.id, claim.id, relation="produced_claim", source="claim_ledger")
                if claim.subject_id in graph:
                    graph.add_edge(claim.subject_id, claim.id, relation="subject_of", source="claim_ledger")

            for quote in case.quotes:
                graph.add_node(
                    quote.id,
                    node_type="quote",
                    label=f"{quote.supplier_name} quote",
                    supplier=quote.supplier_name,
                    quote_type=quote.quote_type,
                    currency=quote.currency,
                    normalized_total=quote.normalized_total,
                    extraction_confidence=quote.extraction_confidence,
                    valid_until=quote.valid_until.isoformat() if quote.valid_until else None,
                )
                graph.add_edge(case.id, quote.id, relation="received_quote", source="quote_ledger")
                if quote.contact_id and quote.contact_id in graph:
                    graph.add_edge(quote.contact_id, quote.id, relation="submitted", source="quote_ledger")
                for index, line_item in enumerate(quote.line_items):
                    line_id = f"{quote.id}:line:{index}"
                    graph.add_node(
                        line_id,
                        node_type="quote_line_item",
                        label=line_item.description,
                        unit=line_item.unit,
                        quantity=line_item.quantity,
                        unit_price=line_item.unit_price,
                        currency=line_item.currency,
                        one_time=line_item.one_time,
                    )
                    graph.add_edge(quote.id, line_id, relation="contains", source="quote_ledger")
        return graph

    def node_link(self, cases: list[CaseRecord]) -> dict[str, Any]:
        return nx.node_link_data(self.build_networkx(cases))

    def geojson(self, cases: list[CaseRecord]) -> dict[str, Any]:
        features: list[dict[str, Any]] = []
        for case in cases:
            if case.location:
                features.append(
                    _point_feature(
                        case.id,
                        case.location.longitude,
                        case.location.latitude,
                        {
                            "node_type": "case",
                            "label": case.title,
                            "kind": case.kind.value,
                            "status": case.status.value,
                        },
                    )
                )
            for contact in case.contacts:
                if contact.location:
                    features.append(
                        _point_feature(
                            contact.id,
                            contact.location.longitude,
                            contact.location.latitude,
                            {
                                "node_type": "contact_route",
                                "label": contact.organization_name,
                                "role": contact.role_title,
                                "geography": contact.geography,
                                "confidence": contact.confidence,
                                "case_id": case.id,
                            },
                        )
                    )
        return {"type": "FeatureCollection", "features": features}

    def city2graph_status(self, cases: list[CaseRecord]) -> dict[str, Any]:
        """Build a real City2Graph projection when optional geospatial dependencies exist."""

        try:
            import geopandas as gpd
            import pandas as pd
            from city2graph.graph import gdf_to_pyg, is_torch_available
            from city2graph.utils import gdf_to_nx, nx_to_rx
            from shapely.geometry import LineString, Point
        except ImportError as exc:
            return {
                "available": False,
                "reason": str(exc),
                "install": "pip install -e '.[geo]'",
                "networkx_projection_available": True,
            }

        node_rows: list[dict[str, Any]] = []
        edge_rows: list[dict[str, Any]] = []
        coordinates: dict[str, tuple[float, float]] = {}
        for case in cases:
            if case.location:
                coordinates[case.id] = (case.location.longitude, case.location.latitude)
                node_rows.append(
                    {
                        "node_id": case.id,
                        "node_kind": 0.0,
                        "activity": float(len(case.interactions)),
                        "geometry": Point(coordinates[case.id]),
                    }
                )
            for contact in case.contacts:
                if contact.location:
                    coordinates[contact.id] = (contact.location.longitude, contact.location.latitude)
                    node_rows.append(
                        {
                            "node_id": contact.id,
                            "node_kind": 1.0,
                            "activity": float(
                                sum(1 for item in case.interactions if item.endpoint == contact.endpoint)
                            ),
                            "geometry": Point(coordinates[contact.id]),
                        }
                    )
                    if case.id in coordinates:
                        edge_rows.append(
                            {
                                "from_node_id": case.id,
                                "to_node_id": contact.id,
                                "edge_key": 0,
                                "weight": float(contact.confidence),
                                "geometry": LineString([coordinates[case.id], coordinates[contact.id]]),
                            }
                        )

        if not node_rows:
            return {"available": True, "node_count": 0, "edge_count": 0, "message": "No geocoded nodes."}

        nodes = gpd.GeoDataFrame(node_rows, geometry="geometry", crs="EPSG:4326").set_index("node_id")
        if edge_rows:
            edge_frame = gpd.GeoDataFrame(edge_rows, geometry="geometry", crs="EPSG:4326")
            edges = edge_frame.set_index(["from_node_id", "to_node_id", "edge_key"])
        else:
            empty_index = pd.MultiIndex.from_arrays([[], [], []], names=["from_node_id", "to_node_id", "edge_key"])
            edges = gpd.GeoDataFrame({"weight": [], "geometry": []}, index=empty_index, crs="EPSG:4326")

        c2g_networkx = gdf_to_nx(nodes=nodes, edges=edges, directed=True, multigraph=True)
        rustworkx_graph = nx_to_rx(c2g_networkx)
        result: dict[str, Any] = {
            "available": True,
            "node_count": int(c2g_networkx.number_of_nodes()),
            "edge_count": int(c2g_networkx.number_of_edges()),
            "networkx_type": type(c2g_networkx).__name__,
            "rustworkx_type": type(rustworkx_graph).__name__,
            "torch_available": bool(is_torch_available()),
        }
        if is_torch_available():
            pyg = gdf_to_pyg(
                nodes=nodes,
                edges=edges,
                node_feature_cols=["node_kind", "activity"],
                edge_feature_cols=["weight"],
                directed=True,
                multigraph=True,
            )
            result["pyg_type"] = type(pyg).__name__
            result["pyg_node_rows"] = int(pyg.x.shape[0])
        return result


def _point_feature(identifier: str, longitude: float, latitude: float, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Feature",
        "id": identifier,
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": properties,
    }
