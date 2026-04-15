"""
Route Path Reconstruction

Converts solver routes (node indices) to full road paths on OSM network.
Returns sequences of (lat, lon) coordinates for each route segment.
"""

import networkx as nx
from loguru import logger
from core.graph.loader import nearest_node


def full_path_between_nodes(
    G: nx.DiGraph, source_node_id: int, target_node_id: int
) -> list[int]:
    """
    Get the full sequence of OSM node IDs on the shortest path between two nodes.

    Parameters
    ----------
    G : nx.DiGraph
        Road network graph from load_graph()
    source_node_id : int
        Starting OSM node ID
    target_node_id : int
        Ending OSM node ID

    Returns
    -------
    list[int]
        Sequence of node IDs from source to target (inclusive).
        Returns empty list if no path exists.
    """
    try:
        path = nx.shortest_path(G, source_node_id, target_node_id, weight="travel_time")
        return path
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        logger.warning(f"No path from {source_node_id} to {target_node_id}")
        return []


def reconstruct_osm_route(
    G: nx.DiGraph, route_node_indices: list[int]
) -> list[tuple[float, float]]:
    """
    Convert a route (list of OSM node IDs) to a sequence of (lat, lon) coordinates.

    Parameters
    ----------
    G : nx.DiGraph
        Road network graph
    route_node_indices : list[int]
        OSM node IDs in route order (e.g., [depot, stop1, stop2, depot])

    Returns
    -------
    list[tuple[float, float]]
        Sequence of (lat, lon) tuples following the road path.
    """
    if not route_node_indices or len(route_node_indices) < 2:
        return []

    path_coords = []

    # For each consecutive pair of stops, get the full road segment
    for i in range(len(route_node_indices) - 1):
        current_node = route_node_indices[i]
        next_node = route_node_indices[i + 1]

        # Get full path between stops
        segment_path = full_path_between_nodes(G, current_node, next_node)

        if segment_path:
            # Add all nodes in segment, avoiding duplicates at transitions
            for j, node_id in enumerate(segment_path):
                if node_id in G.nodes():
                    node_data = G.nodes[node_id]
                    lat = node_data.get("y")
                    lon = node_data.get("x")
                    if lat is not None and lon is not None:
                        # Avoid duplicate at segment transitions (first node of next segment)
                        if not path_coords or (lat, lon) != path_coords[-1]:
                            path_coords.append((lat, lon))
        else:
            logger.warning(f"Segment {current_node} → {next_node} has no path")

    return path_coords


def reconstruct_all_routes(
    G: nx.DiGraph, osm_node_ids: list[int], solver_routes: list[list[int]]
) -> list[list[tuple[float, float]]]:
    """
    Reconstruct full paths for all routes in a solution.

    Parameters
    ----------
    G : nx.DiGraph
        Road network graph
    osm_node_ids : list[int]
        OSM node IDs in the same order as solver indices
        (from build_distance_matrix return value)
    solver_routes : list[list[int]]
        Routes from solution (each route is list of indices into osm_node_ids)

    Returns
    -------
    list[list[tuple[float, float]]]
        One list of (lat, lon) coords per route.
    """
    reconstructed = []

    for route_indices in solver_routes:
        # Convert indices to OSM node IDs
        osm_route = [osm_node_ids[idx] for idx in route_indices]

        # Reconstruct path
        path_coords = reconstruct_osm_route(G, osm_route)
        reconstructed.append(path_coords)

    return reconstructed


def route_summary(path_coords: list[tuple[float, float]]) -> dict:
    """
    Get summary stats for a reconstructed route.

    Parameters
    ----------
    path_coords : list[tuple[float, float]]
        (lat, lon) coordinates of the route

    Returns
    -------
    dict
        {
            "num_points": total coordinate count,
            "start": (lat, lon) of first point,
            "end": (lat, lon) of last point,
            "bbox": (min_lat, min_lon, max_lat, max_lon)
        }
    """
    if not path_coords:
        return {
            "num_points": 0,
            "start": None,
            "end": None,
            "bbox": None,
        }

    lats = [p[0] for p in path_coords]
    lons = [p[1] for p in path_coords]

    return {
        "num_points": len(path_coords),
        "start": path_coords[0],
        "end": path_coords[-1],
        "bbox": (min(lats), min(lons), max(lats), max(lons)),
    }
