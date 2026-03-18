"""
main.py

Day 1 entry point — smoke-tests the graph loader.
This file will grow as we add the API, simulation, and dashboard runners.
"""

from loguru import logger
from core.graph.loader import load_graph, graph_summary


def smoke_test():
    """Quick sanity check: download/load the city graph and print a summary."""
    logger.info("=== FleetMind — Day 1 smoke test ===")

    G = load_graph()
    summary = graph_summary(G)

    logger.success(f"Nodes   : {summary['nodes']:,}")
    logger.success(f"Edges   : {summary['edges']:,}")
    logger.success(f"CRS     : {summary['crs']}")
    logger.info("Graph load OK — ready for Day 2 (distance matrix)")


if __name__ == "__main__":
    smoke_test()