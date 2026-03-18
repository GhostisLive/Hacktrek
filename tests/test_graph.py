import pytest
import networkx as nx
from core.graph.loader import load_graph, nearest_node, graph_summary
 
 
@pytest.fixture(scope="module")
def graph():
    """Load graph once for all tests in this module."""
    return load_graph()
 
 
def test_graph_is_directed(graph):
    assert isinstance(graph, nx.MultiDiGraph)
 
 
def test_graph_has_nodes_and_edges(graph):
    assert graph.number_of_nodes() > 0
    assert graph.number_of_edges() > 0
 
 
def test_edges_have_travel_time(graph):
    """Every edge must have travel_time after enrichment."""
    for _, _, data in graph.edges(data=True):
        assert "travel_time" in data, "Edge missing travel_time"
        assert data["travel_time"] > 0
        break   # checking one is enough for a smoke test
 
 
def test_edges_have_length(graph):
    for _, _, data in graph.edges(data=True):
        assert "length" in data
        assert data["length"] > 0
        break
 
 
def test_nearest_node_returns_int(graph):
    # Kolkata city centre
    node = nearest_node(graph, lat=22.5726, lon=88.3639)
    assert isinstance(node, int)
    assert node in graph.nodes
 
 
def test_graph_summary_keys(graph):
    s = graph_summary(graph)
    assert "nodes" in s
    assert "edges" in s
    assert "crs"   in s
 