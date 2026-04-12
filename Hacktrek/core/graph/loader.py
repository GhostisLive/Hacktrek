import os
import pickle
import osmnx as ox
import networkx as nx
from loguru import logger
 
from config import CITY_NAME, NETWORK_TYPE, GRAPH_CACHE_DIR
 
 
# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
 
def _cache_path(city: str) -> str:
    """Return the .pkl cache path for a given city name."""
    slug = city.lower().replace(",", "").replace(" ", "_")
    return os.path.join(GRAPH_CACHE_DIR, f"{slug}.pkl")
 
 
def _load_from_cache(path: str):
    logger.info(f"Loading cached graph from {path}")
    with open(path, "rb") as f:
        return pickle.load(f)
 
 
def _save_to_cache(G, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(G, f)
    logger.success(f"Graph cached to {path}")
 
 
# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
 
def load_graph(city: str = CITY_NAME, force_reload: bool = False):
    """
    Load the projected road network graph for a city.
 
    Steps
    -----
    1. Check disk cache — return immediately if found (and force_reload is False).
    2. Download from OpenStreetMap via OSMnx.
    3. Enrich edges with speed_kph and travel_time (seconds).
    4. Project to UTM so edge `length` is in metres.
    5. Cache to disk for future runs.
 
    Parameters
    ----------
    city : str
        Any place name valid on OpenStreetMap, e.g. "Kolkata, India".
    force_reload : bool
        Skip the cache and re-download even if a cached file exists.
 
    Returns
    -------
    G : networkx.MultiDiGraph
        Projected graph. Nodes have `x`, `y` (UTM metres).
        Edges have `length` (m), `speed_kph`, `travel_time` (s).
    """
    cache = _cache_path(city)
 
    if not force_reload and os.path.exists(cache):
        return _load_from_cache(cache)
 
    logger.info(f"Downloading road network for '{city}' from OpenStreetMap ...")
    G = ox.graph_from_place(city, network_type=NETWORK_TYPE)
 
    logger.info("Enriching edges with speed and travel time ...")
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
 
    logger.info("Projecting graph to UTM ...")
    G = ox.project_graph(G)
 
    logger.success(
        f"Graph ready — {G.number_of_nodes():,} nodes, "
        f"{G.number_of_edges():,} edges"
    )
 
    _save_to_cache(G, cache)
    return G
 
 
def nearest_node(G, lat: float, lon: float) -> int:
    """
    Snap a WGS-84 coordinate to the nearest road-network node.
 
    OSMnx expects (X=lon, Y=lat) in the *original* CRS.  Because our graph
    is projected we pass the raw lon/lat and let OSMnx handle the conversion.
 
    Parameters
    ----------
    G   : projected MultiDiGraph returned by load_graph()
    lat : latitude  (WGS-84 degrees)
    lon : longitude (WGS-84 degrees)
 
    Returns
    -------
    node_id : int
    """
    return ox.nearest_nodes(G, X=lon, Y=lat)
 
 
def graph_summary(G) -> dict:
    """Return a lightweight summary dict — useful for logging and tests."""
    return {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "crs": G.graph.get("crs", "unknown"),
    }
 