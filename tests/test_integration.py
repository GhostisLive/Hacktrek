"""
End-to-End Integration Test (Day 9)

Full workflow validation:
1. Load city graph
2. Build distance matrix
3. Solve VRP
4. Dispatch to coordinator
5. Monitor fleet status
6. Verify all orders are routed
"""

import pytest
import asyncio
import numpy as np
from core.graph.loader import load_graph, nearest_node
from core.graph.matrix import build_distance_matrix
from core.vrp.models import Stop
from core.vrp.solver import solve_vrp
from core.routing.path import reconstruct_all_routes
from core.agents.coordinator import CoordinatorAgent


@pytest.mark.asyncio
async def test_end_to_end_minimal():
    """
    Minimal end-to-end: load graph, build matrix, solve VRP, dispatch to coordinator.
    """
    # Step 1: Load graph
    G = load_graph()
    assert G is not None
    assert len(G.nodes()) > 0

    # Step 2: Create simple test locations (depot + 3 orders in Kolkata)
    depot = {"lat": 22.5726, "lon": 88.3639}
    orders = [
        {"lat": 22.5750, "lon": 88.3650},
        {"lat": 22.5800, "lon": 88.3700},
        {"lat": 22.5850, "lon": 88.3750},
    ]

    locations = [depot] + orders

    # Step 3: Build distance matrix
    matrix, osm_nodes = build_distance_matrix(G, locations)
    assert matrix.shape == (4, 4)
    assert len(osm_nodes) == 4

    # Diagonal should be 0
    assert np.diag(matrix).sum() == 0

    # All values should be non-negative
    assert (matrix >= 0).all()

    # Step 4: Create Stop objects
    stops = [
        Stop(id=0, lat=depot["lat"], lon=depot["lon"], demand=0),
    ]
    for i, order in enumerate(orders, 1):
        stops.append(
            Stop(
                id=i,
                lat=order["lat"],
                lon=order["lon"],
                demand=1,
            )
        )

    # Step 5: Solve VRP
    solution = solve_vrp(
        distance_matrix=matrix,
        stops=stops,
        num_vehicles=2,
        max_route_time=3600,
        vehicle_capacity=10,
        solver_time_limit=10,
    )

    assert solution is not None
    assert len(solution.routes) > 0
    assert solution.vehicle_count() > 0

    # All routes should be valid
    for route in solution.routes:
        assert route.is_valid
        assert route.stops[0] == 0  # Start at depot
        assert route.stops[-1] == 0  # End at depot

    # Step 6: Reconstruct routes
    reconstructed = reconstruct_all_routes(G, osm_nodes, [r.stops for r in solution.routes])
    assert len(reconstructed) == len(solution.routes)

    # Each reconstructed route should be non-empty
    for path in reconstructed:
        if len(path) > 0:
            assert all(isinstance(p, tuple) and len(p) == 2 for p in path)

    # Step 7: Dispatch to coordinator
    coordinator = CoordinatorAgent(num_drivers=2)
    await coordinator.dispatch_solution(solution)

    # Check drivers are assigned
    assigned_drivers = [
        d for d in coordinator.drivers.values()
        if d.route_stops
    ]
    assert len(assigned_drivers) > 0

    # Step 8: Get fleet status
    status = coordinator.get_fleet_status()
    assert status["summary"]["total_drivers"] == 2
    assert status["summary"]["idle"] == max(0, 2 - len(assigned_drivers))


@pytest.mark.asyncio
async def test_end_to_end_with_polling():
    """
    Full integration with coordinator polling loop.
    """
    # Load graph and create orders
    G = load_graph()

    depot = {"lat": 22.5726, "lon": 88.3639}
    orders = [
        {"lat": 22.5750, "lon": 88.3650},
        {"lat": 22.5800, "lon": 88.3700},
    ]

    locations = [depot] + orders

    # Build matrix and solve
    matrix, osm_nodes = build_distance_matrix(G, locations)

    stops = [
        Stop(id=0, lat=depot["lat"], lon=depot["lon"], demand=0),
    ]
    for i, order in enumerate(orders, 1):
        stops.append(
            Stop(id=i, lat=order["lat"], lon=order["lon"], demand=1)
        )

    solution = solve_vrp(
        distance_matrix=matrix,
        stops=stops,
        num_vehicles=2,
        max_route_time=3600,
        vehicle_capacity=10,
        solver_time_limit=10,
    )

    # Setup coordinator with polling
    coordinator = CoordinatorAgent(num_drivers=2)
    coordinator.polling_interval_sec = 0.1  # Short interval for testing

    # Dispatch
    await coordinator.dispatch_solution(solution)

    # Start polling
    await coordinator.start_polling()

    # Let it poll a couple times
    await asyncio.sleep(0.3)

    # Check status
    status = coordinator.get_fleet_status()
    assert status["summary"]["total_drivers"] == 2

    # Simulate drivers starting their routes
    for driver in coordinator.drivers.values():
        if driver.route_stops:
            driver.start_route((22.5726, 88.3639))

    # Check again
    status = coordinator.get_fleet_status()
    enroute = len([d for d in coordinator.drivers.values() if d.state.value == "enroute"])
    assert enroute > 0 or len(coordinator.drivers) == 0

    # Stop polling
    await coordinator.stop_polling()


@pytest.mark.asyncio
async def test_vrp_covers_all_stops():
    """
    Verify that VRP solution covers all delivery stops.
    """
    G = load_graph()

    depot = {"lat": 22.5726, "lon": 88.3639}
    orders = [
        {"lat": 22.5750, "lon": 88.3650},
        {"lat": 22.5800, "lon": 88.3700},
        {"lat": 22.5850, "lon": 88.3750},
        {"lat": 22.5900, "lon": 88.3800},
    ]

    locations = [depot] + orders
    matrix, osm_nodes = build_distance_matrix(G, locations)

    stops = [
        Stop(id=0, lat=depot["lat"], lon=depot["lon"], demand=0),
    ]
    for i, order in enumerate(orders, 1):
        stops.append(
            Stop(id=i, lat=order["lat"], lon=order["lon"], demand=1)
        )

    solution = solve_vrp(
        distance_matrix=matrix,
        stops=stops,
        num_vehicles=3,
        max_route_time=3600,
        vehicle_capacity=10,
        solver_time_limit=10,
    )

    # Collect all visited stops
    visited = set()
    for route in solution.routes:
        for stop_id in route.stops:
            if stop_id != 0:  # Exclude depot
                visited.add(stop_id)

    # Should visit all 4 orders
    assert len(visited) == 4
    assert visited == {1, 2, 3, 4}


@pytest.mark.asyncio
async def test_route_respects_constraints():
    """
    Verify that routes respect capacity and time constraints.
    """
    G = load_graph()

    depot = {"lat": 22.5726, "lon": 88.3639}
    orders = [
        {"lat": 22.5750, "lon": 88.3650},
        {"lat": 22.5800, "lon": 88.3700},
    ]

    locations = [depot] + orders
    matrix, osm_nodes = build_distance_matrix(G, locations)

    stops = [
        Stop(id=0, lat=depot["lat"], lon=depot["lon"], demand=0),
        Stop(id=1, lat=orders[0]["lat"], lon=orders[0]["lon"], demand=3),
        Stop(id=2, lat=orders[1]["lat"], lon=orders[1]["lon"], demand=2),
    ]

    capacity = 5  # Tight constraint
    max_time = 3600

    solution = solve_vrp(
        distance_matrix=matrix,
        stops=stops,
        num_vehicles=2,
        max_route_time=max_time,
        vehicle_capacity=capacity,
        solver_time_limit=10,
    )

    # Check capacity constraint
    for route in solution.routes:
        assert route.total_demand <= capacity

    # Check time constraint
    for route in solution.routes:
        assert route.total_distance <= max_time


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
