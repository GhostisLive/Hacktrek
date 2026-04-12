import numpy as np
import networkx as nx
from Hacktrek.core.graph.loader import nearest_node
    
def build_distance_matrix(G, locations: list[dict]) -> tuple[np.ndarray, list[int]]:
   
    PENALTY = 10_000_000
    n = len(locations)


    nodes = [nearest_node(G, loc["lat"], loc["lon"]) for loc in locations]

    
    matrix = np.full((n, n), PENALTY, dtype=np.int64)

    for i, source in enumerate(nodes):
        lengths = nx.single_source_dijkstra_path_length(G, source, weight="travel_time")
        for j, target in enumerate(nodes):
            if target in lengths:
                matrix[i][j] = int(lengths[target])
            
    np.fill_diagonal(matrix, 0)

    return matrix, nodes