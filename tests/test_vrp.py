
import pytest
import numpy as np
from core.vrp.models import Stop, Route, Solution
from core.vrp.solver import solve_vrp

@pytest.fixture
def simple_distance_matrix():
    return np.array([
        [0,    100,  200,  150,  120],
        [100,  0,    50,   100,  80],
        [200,  50,   0,    120,  110],
        [150,  100,  120,  0,    60],
        [120,  80,   110,  60,   0],
    ], dtype=np.int64)

@pytest.fixture
def simple_stops():
    return [
        Stop(id=0, lat=22.5726, lon=88.3639, demand=0),
        Stop(id=1, lat=22.5750, lon=88.3650, demand=2),
        Stop(id=2, lat=22.5800, lon=88.3700, demand=3),
        Stop(id=3, lat=22.5850, lon=88.3750, demand=2),
        Stop(id=4, lat=22.5900, lon=88.3800, demand=1),
    ]

def test_solution_creation():
    routes = [
        Route(vehicle_id=0, stops=[0, 1, 2, 0], total_distance=350, total_demand=5),
        Route(vehicle_id=1, stops=[0, 3, 4, 0], total_distance=240, total_demand=3),
    ]
    solution = Solution(routes=routes, total_distance=590)
    assert len(solution.routes) == 2
    assert solution.total_distance == 590
    assert solution.vehicle_count() == 2

def test_route_validity():
    valid_route = Route(vehicle_id=0, stops=[0, 1, 2, 0], total_distance=250, total_demand=2)
    assert valid_route.is_valid

    invalid_route = Route(vehicle_id=0, stops=[1, 2, 3], total_distance=200, total_demand=2)
    assert not invalid_route.is_valid

def test_solution_completeness():
    routes = [
        Route(vehicle_id=0, stops=[0, 1, 2, 0], total_distance=300, total_demand=2),
        Route(vehicle_id=1, stops=[0, 3, 4, 0], total_distance=250, total_demand=2),
    ]
    solution = Solution(routes=routes)
    assert solution.is_complete(4)
    assert not solution.is_complete(5)

def test_solve_vrp_basic(simple_distance_matrix, simple_stops):
    solution = solve_vrp(
        distance_matrix=simple_distance_matrix,
        stops=simple_stops,
        num_vehicles=2,
        max_route_time=600,
        vehicle_capacity=10,
        solver_time_limit=5,
    )

    assert solution is not None
    assert isinstance(solution.routes, list)

    if solution.routes:
        assert solution.vehicle_count() > 0
        assert solution.total_stops_visited == 4

def test_solve_vrp_vehicle_count(simple_distance_matrix, simple_stops):
    solution = solve_vrp(
        distance_matrix=simple_distance_matrix,
        stops=simple_stops,
        num_vehicles=3,
        max_route_time=600,
        vehicle_capacity=10,
        solver_time_limit=5,
    )

    assert len(solution.routes) <= 3

def test_solve_vrp_time_limit_respected(simple_distance_matrix, simple_stops):
    import time
    start = time.time()

    solution = solve_vrp(
        distance_matrix=simple_distance_matrix,
        stops=simple_stops,
        num_vehicles=2,
        max_route_time=600,
        vehicle_capacity=10,
        solver_time_limit=2,
    )

    elapsed = time.time() - start
    assert elapsed < 5.0
    assert solution.solve_time_ms < 5000

def test_solve_vrp_capacity_respected(simple_distance_matrix, simple_stops):
    solution = solve_vrp(
        distance_matrix=simple_distance_matrix,
        stops=simple_stops,
        num_vehicles=3,
        max_route_time=600,
        vehicle_capacity=5,
        solver_time_limit=5,
    )

    for route in solution.routes:
        assert route.total_demand <= 5

def test_solve_vrp_all_routes_valid(simple_distance_matrix, simple_stops):
    solution = solve_vrp(
        distance_matrix=simple_distance_matrix,
        stops=simple_stops,
        num_vehicles=2,
        max_route_time=600,
        vehicle_capacity=10,
        solver_time_limit=5,
    )

    for route in solution.routes:
        assert route.is_valid
        assert route.stops[0] == 0
        assert route.stops[-1] == 0

def test_solve_vrp_no_duplicate_stops():
    matrix = np.array([
        [0,   100, 200, 300],
        [100, 0,   50,  100],
        [200, 50,  0,   120],
        [300, 100, 120, 0],
    ], dtype=np.int64)

    stops = [
        Stop(id=0, lat=0, lon=0, demand=0),
        Stop(id=1, lat=1, lon=1, demand=1),
        Stop(id=2, lat=2, lon=2, demand=1),
        Stop(id=3, lat=3, lon=3, demand=1),
    ]

    solution = solve_vrp(
        distance_matrix=matrix,
        stops=stops,
        num_vehicles=2,
        max_route_time=500,
        vehicle_capacity=10,
        solver_time_limit=5,
    )

    all_visited = []
    for route in solution.routes:
        for stop_id in route.stops:
            if stop_id != 0:
                all_visited.append(stop_id)

    assert len(all_visited) == len(set(all_visited))

def test_route_duration(simple_distance_matrix, simple_stops):
    route = Route(
        vehicle_id=0,
        stops=[0, 1, 2, 0],
        total_distance=250,
        total_demand=5,
        start_time=0,
        end_time=250,
    )

    assert route.duration == 250

def test_solution_total_load(simple_distance_matrix, simple_stops):
    routes = [
        Route(vehicle_id=0, stops=[0, 1, 2, 0], total_distance=300, total_demand=5),
        Route(vehicle_id=1, stops=[0, 3, 4, 0], total_distance=250, total_demand=3),
    ]
    solution = Solution(routes=routes)

    assert solution.total_load() == 8

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
