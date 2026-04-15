import networkx as nx
from loguru import logger
from core.graph.loader import nearest_node


def full_path_between_nodes(
    G: nx.DiGraph, source_node_id: int, target_node_id: int
) -> list[int]:

    try:
        path = nx.shortest_path(G, source_node_id, target_node_id, weight="travel_time")
        return path
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        logger.warning(f"No path from {source_node_id} to {target_node_id}")
        return []


def reconstruct_osm_route(
    G: nx.DiGraph, route_node_indices: list[int]
) -> list[tuple[float, float]]:

    if not route_node_indices or len(route_node_indices) < 2:
        return []

    path_coords = []

    for i in range(len(route_node_indices) - 1):
        current_node = route_node_indices[i]
        next_node = route_node_indices[i + 1]

        segment_path = full_path_between_nodes(G, current_node, next_node)

        if segment_path:
            for j, node_id in enumerate(segment_path):
                if node_id in G.nodes():
                    node_data = G.nodes[node_id]
                    lat = node_data.get("y")
                    lon = node_data.get("x")
                    if lat is not None and lon is not None:
                        if not path_coords or (lat, lon) != path_coords[-1]:
                            path_coords.append((lat, lon))
        else:
            logger.warning(f"Segment {current_node} → {next_node} has no path")

    return path_coords


def reconstruct_all_routes(
    G: nx.DiGraph, osm_node_ids: list[int], solver_routes: list[list[int]]
) -> list[list[tuple[float, float]]]:

    reconstructed = []

    for route_indices in solver_routes:
        osm_route = [osm_node_ids[idx] for idx in route_indices]

        path_coords = reconstruct_osm_route(G, osm_route)
        reconstructed.append(path_coords)

    return reconstructed


def route_summary(path_coords: list[tuple[float, float]]) -> dict:

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
