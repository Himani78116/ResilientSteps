from __future__ import annotations

from typing import Tuple

import geopandas as gpd
import networkx as nx
import osmnx as ox
from shapely.geometry import LineString

PUNE_CENTER_LAT = 18.5204
PUNE_CENTER_LON = 73.8567
PUNE_RADIUS_METERS = 2500


def generate_street_graph(
    *,
    lat: float = PUNE_CENTER_LAT,
    lon: float = PUNE_CENTER_LON,
    radius_meters: int = PUNE_RADIUS_METERS,
    network_type: str = "walk",
) -> Tuple[nx.MultiDiGraph, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Fetches a pedestrian graph and returns graph, nodes GDF, and edges GDF."""
    # Step 1: Download a walkable OSM graph for the requested area.
    ox.settings.use_cache = True
    ox.settings.log_console = False
    graph = ox.graph_from_point(
        (lat, lon),
        dist=radius_meters,
        network_type=network_type,
        simplify=True,
    )

    # Step 2: Convert graph to GeoDataFrames.
    nodes_gdf, edges_gdf = ox.graph_to_gdfs(graph, nodes=True, edges=True)

    if nodes_gdf.crs is None:
        nodes_gdf = nodes_gdf.set_crs(epsg=4326, allow_override=True)
    else:
        nodes_gdf = nodes_gdf.to_crs(epsg=4326)

    if edges_gdf.crs is None:
        edges_gdf = edges_gdf.set_crs(epsg=4326, allow_override=True)
    else:
        edges_gdf = edges_gdf.to_crs(epsg=4326)

    # Step 3: Ensure all edges have geometry (fallback to node-to-node lines).
    edges_gdf = _ensure_edge_geometry(nodes_gdf, edges_gdf)

    return graph, nodes_gdf, edges_gdf


def _ensure_edge_geometry(
    nodes_gdf: gpd.GeoDataFrame,
    edges_gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Builds missing edge geometry from its source/target node coordinates."""
    fixed_edges = edges_gdf.copy()
    missing_geometry_indices = fixed_edges.index[
        fixed_edges.geometry.isna() | fixed_edges.geometry.is_empty
    ]

    if missing_geometry_indices.empty:
        return fixed_edges

    for edge_idx in missing_geometry_indices:
        if not isinstance(edge_idx, tuple) or len(edge_idx) < 2:
            continue

        u, v = edge_idx[0], edge_idx[1]
        if u not in nodes_gdf.index or v not in nodes_gdf.index:
            continue

        start_node = nodes_gdf.loc[u]
        end_node = nodes_gdf.loc[v]
        fixed_edges.at[edge_idx, "geometry"] = LineString(
            [(start_node["x"], start_node["y"]), (end_node["x"], end_node["y"])]
        )

    return fixed_edges


if __name__ == "__main__":
    graph, nodes, edges = generate_street_graph()
    print(
        "Fetched graph:",
        {
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "nodes_gdf": len(nodes),
            "edges_gdf": len(edges),
        },
    )
