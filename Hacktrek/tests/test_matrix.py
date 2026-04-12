# tests/test_matrix.py

import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from Hacktrek.core.graph.matrix import build_distance_matrix  

def make_graph(directed=True):
    
    import networkx as nx
    G = nx.DiGraph() if directed else nx.Graph()
    G.add_edge(0, 1, travel_time=5)
    G.add_edge(1, 2, travel_time=3)
    G.add_edge(2, 0, travel_time=1)
    return G


LOCATIONS = [
    {"lat": 0.0, "lon": 0.0},  
    {"lat": 1.0, "lon": 1.0},
    {"lat": 2.0, "lon": 2.0},  
]


SNAPPED_NODES = [0, 1, 2]


@pytest.fixture()
def matrix_and_nodes():
    G = make_graph()
    with patch("your_module.nearest_node", side_effect=SNAPPED_NODES):
        mat, nodes = build_distance_matrix(G, LOCATIONS)
    return mat, nodes


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMatrixShape:
    def test_shape_is_n_by_n(self, matrix_and_nodes):
        mat, _ = matrix_and_nodes
        n = len(LOCATIONS)
        assert mat.shape == (n, n), (
            f"Expected ({n}, {n}), got {mat.shape}"
        )

    def test_returns_numpy_array(self, matrix_and_nodes):
        mat, _ = matrix_and_nodes
        assert isinstance(mat, np.ndarray)

    def test_nodes_list_length_matches_locations(self, matrix_and_nodes):
        _, nodes = matrix_and_nodes
        assert len(nodes) == len(LOCATIONS)


class TestDiagonal:
    def test_diagonal_is_all_zeros(self, matrix_and_nodes):
        mat, _ = matrix_and_nodes
        diagonal = np.diag(mat)
        assert np.all(diagonal == 0), (
            f"Expected all-zero diagonal, got {diagonal}"
        )

    def test_diagonal_zero_for_single_location(self):
        """Edge case: 1×1 matrix should still have a zero diagonal."""
        G = make_graph()
        locations = [LOCATIONS[0]]
        with patch("your_module.nearest_node", return_value=0):
            mat, _ = build_distance_matrix(G, locations)
        assert mat.shape == (1, 1)
        assert mat[0][0] == 0


class TestNoNegativeValues:
    def test_no_negative_values(self, matrix_and_nodes):
        mat, _ = matrix_and_nodes
        assert np.all(mat >= 0), (
            f"Found negative travel times:\n{mat}"
        )

    def test_off_diagonal_non_negative(self, matrix_and_nodes):
        """Explicitly check only off-diagonal cells."""
        mat, _ = matrix_and_nodes
        n = mat.shape[0]
        mask = ~np.eye(n, dtype=bool)
        assert np.all(mat[mask] >= 0)


class TestAsymmetry:
    def test_matrix_is_not_necessarily_symmetric(self, matrix_and_nodes):
        """
        On a directed graph, matrix[i][j] need not equal matrix[j][i].
        Our fixture graph has:
            0→1 = 5,  1→0 = 5+3+1 = 9  (no direct back-edge, goes 1→2→0)
        At least one such pair must differ.
        """
        mat, _ = matrix_and_nodes
        n = mat.shape[0]
        found_asymmetric_pair = False
        for i in range(n):
            for j in range(n):
                if i != j and mat[i][j] != mat[j][i]:
                    found_asymmetric_pair = True
                    break
        assert found_asymmetric_pair, (
            "Expected at least one asymmetric pair on a directed graph, "
            "but matrix[i][j] == matrix[j][i] for all i, j.\n"
            f"Matrix:\n{mat}"
        )

    def test_specific_asymmetric_values(self, matrix_and_nodes):
        """
        Pin the exact values from our fixture graph so regressions are obvious.
            node 0 → node 1: weight 5
            node 1 → node 0: 1→2 (3) + 2→0 (1) = 4   ← shorter than 5
        """
        mat, _ = matrix_and_nodes
        assert mat[0][1] == 5,  f"Expected mat[0][1]=5, got {mat[0][1]}"
        assert mat[1][0] == 4,  f"Expected mat[1][0]=4, got {mat[1][0]}"
        assert mat[0][1] != mat[1][0], "mat[0][1] should differ from mat[1][0]"


class TestUnreachableNodes:
    def test_unreachable_pair_gets_penalty(self):
        """
        Isolated graph: node 0 has no path to node 1.
        Expect the penalty value (10_000_000) instead of a crash.
        """
        import networkx as nx
        G = nx.DiGraph()
        G.add_node(0)
        G.add_node(1) 

        locations = [{"lat": 0.0, "lon": 0.0}, {"lat": 1.0, "lon": 1.0}]
        with patch("your_module.nearest_node", side_effect=[0, 1]):
            mat, _ = build_distance_matrix(G, locations)