import osmnx as ox
import networkx as nx
import folium
import subprocess
import os
import time
import pickle
import geopandas as gpd
import redis
import io
import json
from shapely import set_precision

place = "Kolkata, West Bengal, India"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
HTML_DIR = os.path.join(os.path.dirname(__file__), "maps")
FORCE_REBUILD = False  # Set True to regenerate HTML even if it exists

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(HTML_DIR, exist_ok=True)
ox.settings.use_cache = True
ox.settings.cache_folder = os.path.join(CACHE_DIR, "osmnx_http")

# Redis connection for production-style caching
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_DB = int(os.environ.get("REDIS_DB", 0))
REDIS_TTL = int(os.environ.get("REDIS_TTL", 86400))  # 24h default; 0 = no expiry
rcache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


def _redis_set(key, data):
    """Store data in Redis, with or without TTL."""
    if REDIS_TTL > 0:
        rcache.setex(key, REDIS_TTL, data)
    else:
        rcache.set(key, data)


def _open_browser(path):
    import os, sys
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path], close_fds=True, start_new_session=True)
    else:
        subprocess.Popen(["xdg-open", path], close_fds=True, start_new_session=True)


def _html_path(name):
    """Return the HTML output path for a given function name."""
    safe_place = place.replace(", ", "_").replace(" ", "_")
    return os.path.join(HTML_DIR, f"{safe_place}_{name}.html")


def _open_or_build(name, build_fn):
    """Open existing HTML map instantly, or restore from Redis, or build."""
    start = time.time()
    path = _html_path(name)
    # 1) Disk cache — instant
    if os.path.exists(path) and not FORCE_REBUILD:
        print(f"  Opening saved map: {os.path.basename(path)}")
        _open_browser(path)
        print(f"  Done in {time.time() - start:.2f}s (from disk)")
        return
    # 2) Redis HTML cache — restore to disk in ms
    safe_place = place.replace(", ", "_").replace(" ", "_")
    redis_key = f"html:{safe_place}:{name}"
    if not FORCE_REBUILD:
        cached_html = rcache.get(redis_key)
        if cached_html:
            with open(path, "wb") as f:
                f.write(cached_html)
            _open_browser(path)
            print(f"  Done in {time.time() - start:.2f}s (restored from Redis)")
            return
    # 3) Build from scratch, then cache HTML in Redis
    print(f"  Building map: {name}...")
    build_fn(path)
    if os.path.exists(path):
        with open(path, "rb") as f:
            _redis_set(f"html:{safe_place}:{name}", f.read())
    print(f"  Done in {time.time() - start:.2f}s (built + cached)")


def _get_graph(network_type="drive"):
    """Load graph from Redis cache, or download & cache it."""
    start = time.time()
    safe_place = place.replace(", ", "_").replace(" ", "_")
    redis_key = f"graph:{safe_place}:{network_type}"
    cached = rcache.get(redis_key)
    if cached:
        graph = pickle.loads(cached)
        print(f"  Loaded graph from Redis in {time.time() - start:.2f}s")
        return graph
    print(f"  Downloading {network_type} network for {place}...")
    graph = ox.graph_from_place(place, network_type=network_type)
    _redis_set(redis_key, pickle.dumps(graph, protocol=pickle.HIGHEST_PROTOCOL))
    print(f"  Downloaded & cached in Redis in {time.time() - start:.2f}s")
    return graph


def _get_features(tags, name):
    """Load features from Redis cache, or download & cache them."""
    start = time.time()
    safe_place = place.replace(", ", "_").replace(" ", "_")
    redis_key = f"features:{safe_place}:{name}"
    cached = rcache.get(redis_key)
    if cached:
        gdf = gpd.read_file(io.BytesIO(cached), driver="GPKG")
        print(f"  Loaded features from Redis in {time.time() - start:.2f}s")
        return gdf
    print(f"  Downloading {name} for {place}...")
    gdf = ox.features_from_place(place, tags=tags)
    # Keep only serializable columns to avoid save errors
    non_geom = [c for c in gdf.columns if c != "geometry"]
    drop_cols = [c for c in non_geom if gdf[c].apply(type).eq(list).any()]
    clean_gdf = gdf.drop(columns=drop_cols, errors="ignore")
    buf = io.BytesIO()
    clean_gdf.to_file(buf, driver="GPKG")
    _redis_set(redis_key, buf.getvalue())
    print(f"  Downloaded & cached in Redis in {time.time() - start:.2f}s")
    return gdf

# ============================================================
# 1) INTERACTIVE STREET NETWORK — roads on a tile map
# ============================================================
def _graph_to_folium(graph, color="blue", weight=2, opacity=0.7):
    """Plot a graph's edges on a folium map using fast GeoJson."""
    nodes, edges = ox.graph_to_gdfs(graph)
    edges = edges.copy()
    # Simplify + reduce coordinate precision — shrinks GeoJSON dramatically
    edges.geometry = set_precision(edges.geometry.simplify(tolerance=0.001), grid_size=0.0001)
    center_lat, center_lon = nodes["y"].mean(), nodes["x"].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
    folium.GeoJson(
        edges[["geometry"]],
        style_function=lambda x: {
            "color": color, "weight": weight, "opacity": opacity,
        },
    ).add_to(m)
    return m


def street_network():
    def _build(out):
        graph = _get_graph("drive")
        m = _graph_to_folium(graph, color="blue", weight=2, opacity=0.7)
        m.save(out)
        _open_browser(out)
    _open_or_build("street_network", _build)

# ============================================================
# 2) WALKING / CYCLING NETWORK
# ============================================================
def walking_network():
    def _build(out):
        graph = _get_graph("walk")
        m = _graph_to_folium(graph, color="#00BFFF", weight=1, opacity=0.6)
        m.save(out)
        _open_browser(out)
    _open_or_build("walking_network", _build)

# ============================================================
# 3) BUILDING FOOTPRINTS — interactive polygons
# ============================================================
def building_footprints():
    def _build(out):
        buildings = _get_features({"building": True}, "buildings")
        buildings = buildings.copy()
        buildings.geometry = buildings.geometry.simplify(tolerance=0.0001)
        bounds = buildings.total_bounds
        m = folium.Map(location=[(bounds[1]+bounds[3])/2, (bounds[0]+bounds[2])/2], zoom_start=14)
        folium.GeoJson(
            buildings,
            style_function=lambda x: {
                "fillColor": "orange", "color": "black",
                "weight": 0.5, "fillOpacity": 0.6,
            },
            tooltip=folium.GeoJsonTooltip(fields=["name"] if "name" in buildings.columns else []),
        ).add_to(m)
        m.save(out)
        _open_browser(out)
    _open_or_build("building_footprints", _build)

# ============================================================
# 4) SHORTEST PATH — route highlighted on interactive map
# ============================================================
def shortest_path():
    def _build(out):
        graph = _get_graph("drive")
        graph = ox.routing.add_edge_speeds(graph)
        graph = ox.routing.add_edge_travel_times(graph)
        nodes = list(graph.nodes)
        orig, dest = nodes[0], nodes[-1]
        route = ox.routing.shortest_path(graph, orig, dest, weight="travel_time")
        if route:
            m = _graph_to_folium(graph, color="gray", weight=1, opacity=0.4)
            route_coords = [(graph.nodes[n]["y"], graph.nodes[n]["x"]) for n in route]
            folium.PolyLine(route_coords, color="red", weight=5, opacity=0.8).add_to(m)
            folium.Marker(
                [graph.nodes[orig]["y"], graph.nodes[orig]["x"]],
                popup="Start", icon=folium.Icon(color="green"),
            ).add_to(m)
            folium.Marker(
                [graph.nodes[dest]["y"], graph.nodes[dest]["x"]],
                popup="End", icon=folium.Icon(color="red"),
            ).add_to(m)
            m.save(out)
            _open_browser(out)
        else:
            print("No route found between the selected nodes.")
    _open_or_build("shortest_path", _build)

# ============================================================
# 5) NETWORK STATS — printed to console
# ============================================================
def network_stats():
    graph = _get_graph("drive")
    stats = ox.stats.basic_stats(graph)
    print(f"\n{'='*50}")
    print(f"  Network Stats for {place}")
    print(f"{'='*50}")
    for key, value in stats.items():
        print(f"  {key}: {value}")

# ============================================================
# 6) POINTS OF INTEREST — hospitals as clickable markers
# ============================================================
def points_of_interest():
    def _build(out):
        pois = _get_features({"amenity": "hospital"}, "hospitals")
        bounds = pois.total_bounds
        m = folium.Map(location=[(bounds[1]+bounds[3])/2, (bounds[0]+bounds[2])/2], zoom_start=12)
        has_name = "name" in pois.columns
        for _, row in pois.iterrows():
            pt = row.geometry.representative_point()
            name = row["name"] if has_name and row["name"] else "Hospital"
            folium.Marker(
                [pt.y, pt.x],
                popup=str(name),
                icon=folium.Icon(color="red", icon="plus-sign"),
            ).add_to(m)
        m.save(out)
        _open_browser(out)
    _open_or_build("points_of_interest", _build)

# ============================================================
# 7) ISOCHRONE MAP — reachable area within 5/10/15 min
# ============================================================
def isochrone_map():
    def _build(out):
        graph = _get_graph("drive")
        graph = ox.routing.add_edge_speeds(graph)
        graph = ox.routing.add_edge_travel_times(graph)
        center_node = ox.distance.nearest_nodes(graph, 88.3639, 22.5726)
        trip_times = [15, 10, 5]
        colors = ["#4daf4a", "#377eb8", "#e41a1c"]
        m = folium.Map(location=[22.5726, 88.3639], zoom_start=13)
        for minutes, color in zip(trip_times, colors):
            subgraph = nx.ego_graph(graph, center_node, radius=minutes * 60, distance="travel_time")
            nodes_gdf = ox.graph_to_gdfs(subgraph, edges=False)
            hull = nodes_gdf.union_all().convex_hull
            folium.GeoJson(
                hull,
                style_function=lambda x, c=color: {
                    "fillColor": c, "color": c,
                    "weight": 2, "fillOpacity": 0.3,
                },
                name=f"{minutes} min",
            ).add_to(m)
        folium.Marker([22.5726, 88.3639], popup="Center", icon=folium.Icon(color="black")).add_to(m)
        folium.LayerControl().add_to(m)
        m.save(out)
        _open_browser(out)
    _open_or_build("isochrone_map", _build)


# ============================================================
#  PICK ONE TO RUN (uncomment the one you want):
# ============================================================
if __name__ == "__main__":
    #street_network()
    #walking_network()
    building_footprints()
    #shortest_path()
    #network_stats()
    #points_of_interest()
    #isochrone_map()