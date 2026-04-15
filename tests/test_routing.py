
import pytest
import networkx as nx
from core.graph.loader import load_graph
from core.routing.path import (
    full_path_between_nodes,
    reconstruct_osm_route,
    route_summary,
)

@pytest.fixture
def test_graph():
    return load_graph()

def test_full_path_between_nodes_simple(test_graph):
    nodes = list(test_graph.nodes())
    if len(nodes) < 2:
        pytest.skip("Graph has fewer than 2 nodes")

    source = nodes[0]
    target = nodes[1]

    path = full_path_between_nodes(test_graph, source, target)

    assert isinstance(path, list)
    assert len(path) > 0

    assert path[0] == source

    assert path[-1] == target

    for node in path:
        assert node in test_graph.nodes()

def test_full_path_same_node(test_graph):
    nodes = list(test_graph.nodes())
    node = nodes[0]

    path = full_path_between_nodes(test_graph, node, node)

    assert path == [node]

def test_full_path_disconnected():
    G = nx.DiGraph()
    G.add_node(1)
    G.add_node(2)

    path = full_path_between_nodes(G, 1, 2)

    assert path == []

def test_reconstruct_osm_route_empty():
    G = load_graph()
    path = reconstruct_osm_route(G, [])

    assert path == []

def test_reconstruct_osm_route_single_node():
    G = load_graph()
    nodes = list(G.nodes())
    single_node = nodes[0]

    path = reconstruct_osm_route(G, [single_node])

    assert len(path) == 0 or len(path) == 1

def test_reconstruct_osm_route_simple():
    G = load_graph()
    nodes = list(G.nodes())[:3]

    if len(nodes) < 2:
        pytest.skip("Not enough nodes in graph")

    path = reconstruct_osm_route(G, nodes)

    assert isinstance(path, list)

    for coord in path:
        assert isinstance(coord, tuple)
        assert len(coord) == 2
        lat, lon = coord
        assert isinstance(lat, float)
        assert isinstance(lon, float)

def test_reconstruct_osm_route_no_duplicates():
    G = load_graph()
    nodes = list(G.nodes())[:2]

    if len(nodes) < 2:
        pytest.skip("Not enough nodes")

    path = reconstruct_osm_route(G, nodes)

    for i in range(len(path) - 1):
        assert path[i] != path[i + 1]

def test_route_summary_empty():
    summary = route_summary([])

    assert summary["num_points"] == 0
    assert summary["start"] is None
    assert summary["end"] is None
    assert summary["bbox"] is None

def test_route_summary_single_point():
    path = [(22.5726, 88.3639)]
    summary = route_summary(path)

    assert summary["num_points"] == 1
    assert summary["start"] == (22.5726, 88.3639)
    assert summary["end"] == (22.5726, 88.3639)
    assert summary["bbox"] == (22.5726, 88.3639, 22.5726, 88.3639)

def test_route_summary_multiple_points():
    path = [
        (22.5700, 88.3600),
        (22.5726, 88.3639),
        (22.5800, 88.3700),
    ]
    summary = route_summary(path)

    assert summary["num_points"] == 3
    assert summary["start"] == (22.5700, 88.3600)
    assert summary["end"] == (22.5800, 88.3700)

    min_lat, min_lon, max_lat, max_lon = summary["bbox"]
    assert min_lat == 22.5700
    assert max_lat == 22.5800
    assert min_lon == 88.3600
    assert max_lon == 88.3700

def test_reconstruct_osm_route_coordinates_valid(test_graph):
    nodes = list(test_graph.nodes())[:2]
    if len(nodes) < 2:
        pytest.skip("Not enough nodes")

    path = reconstruct_osm_route(test_graph, nodes)

    for lat, lon in path:
        assert 8 < lat < 35
        assert 68 < lon < 97

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
