"""
VRP Solver using Google OR-Tools

Solves Vehicle Routing Problem with distance matrix input.
Supports capacity constraints, time window constraints, and time limits.
"""

import time
from loguru import logger
import numpy as np
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from core.vrp.models import Stop, Route, Solution


def solve_vrp(
    distance_matrix: np.ndarray,
    stops: list[Stop],
    num_vehicles: int,
    max_route_time: int,
    vehicle_capacity: int,
    solver_time_limit: int = 30,
) -> Solution:
    """
    Solve VRP using OR-Tools with PATH_CHEAPEST_ARC heuristic and GUIDED_LOCAL_SEARCH metaheuristic.

    Parameters
    ----------
    distance_matrix : np.ndarray
        NxN matrix of travel times in seconds between stops.
        Typically from build_distance_matrix(). First row/column is depot.
    stops : list[Stop]
        List of Stop objects with id, lat, lon, demand, time windows.
        stops[0] must be the depot.
    num_vehicles : int
        Number of delivery vehicles available.
    max_route_time : int
        Maximum route duration in seconds (e.g., 14400 = 4 hours).
    vehicle_capacity : int
        Vehicle load capacity (e.g., 20 items).
    solver_time_limit : int
        Maximum solver runtime in seconds.

    Returns
    -------
    Solution
        Solution object with routes, total distance, solver status.
    """
    start_time = time.time()

    # Create the routing index manager
    manager = pywrapcp.RoutingIndexManager(
        len(distance_matrix), num_vehicles, 0  # 0-indexed depot
    )

    # Create the routing model
    routing = pywrapcp.RoutingModel(manager)

    # Add distance callback
    def distance_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(distance_matrix[from_node][to_node])

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Add time dimension (travel time)
    time_dimension_name = "Time"
    routing.AddDimension(
        transit_callback_index,
        0,  # slack = 0 (no waiting between deliveries, but could be added)
        max_route_time,  # vehicle max time
        True,  # start cumul to zero (start clock at 0 for each vehicle)
        time_dimension_name,
    )
    time_dimension = routing.GetDimensionOrDie(time_dimension_name)

    # Add capacity dimension if needed
    if vehicle_capacity > 0:
        def demand_callback(from_index: int) -> int:
            node = manager.IndexToNode(from_index)
            if node < len(stops):
                return stops[node].demand
            return 0

        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimension(
            demand_callback_index,
            0,  # null capacity slack
            vehicle_capacity,  # vehicle capacity
            True,  # start cumul to zero
            "Capacity",
        )
        capacity_dimension = routing.GetDimensionOrDie("Capacity")

        # Prevent backhauls: end must have same cumul as max along route
        for vehicle_id in range(num_vehicles):
            capacity_dimension.CumulVar(routing.End(vehicle_id)).SetMax(0)

    # Set first solution strategy
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )

    # Metaheuristic: GUIDED_LOCAL_SEARCH (good balance of speed and quality)
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )

    # Time limit in seconds
    search_parameters.time_limit.seconds = solver_time_limit

    # Solve
    assignment = routing.SolveFromAssignmentWithParameters(
        routing.ReadAssignmentFromRoutes(
            [[] for _ in range(num_vehicles)],  # empty starting routes
            ignore_inactive_indices=False,
        ),
        search_parameters,
    )

    # Extract solution
    if assignment:
        routes = []
        total_distance = 0

        for vehicle_id in range(num_vehicles):
            route_indices = []
            route_distance = 0

            index = routing.Start(vehicle_id)
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                route_indices.append(node)
                previous_index = index
                index = assignment.Value(routing.NextVar(index))
                route_distance += routing.GetArcCostForVehicle(
                    previous_index, index, vehicle_id
                )

            # Add final depot return
            node = manager.IndexToNode(index)
            route_indices.append(node)

            # Only add non-empty routes
            if len(route_indices) > 2 or (len(route_indices) == 2 and route_indices[0] == 0):
                total_demand = sum(
                    stops[idx].demand for idx in route_indices if idx < len(stops) and idx > 0
                )

                route = Route(
                    vehicle_id=vehicle_id,
                    stops=route_indices,
                    total_distance=route_distance,
                    total_demand=total_demand,
                    start_time=0,
                    end_time=route_distance,
                )
                routes.append(route)
                total_distance += route_distance

        solve_time_ms = (time.time() - start_time) * 1000
        solution = Solution(
            routes=routes,
            total_distance=total_distance,
            total_stops_visited=len(stops) - 1,  # exclude depot
            solve_time_ms=solve_time_ms,
            solver_status="OPTIMAL" if assignment else "PARTIAL",
        )

        logger.info(
            f"VRP solved: {len(routes)} routes, {solution.total_stops_visited} stops, "
            f"{total_distance}s total time, {solve_time_ms:.1f}ms solver time"
        )

        return solution
    else:
        logger.warning("VRP solver failed to find a solution.")
        return Solution(
            routes=[],
            total_distance=0,
            total_stops_visited=0,
            solve_time_ms=(time.time() - start_time) * 1000,
            solver_status="FAILED",
        )
