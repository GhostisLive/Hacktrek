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

    start_time = time.time()

    manager = pywrapcp.RoutingIndexManager(
        len(distance_matrix), num_vehicles, 0
    )

    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(distance_matrix[from_node][to_node])

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    time_dimension_name = "Time"
    routing.AddDimension(
        transit_callback_index,
        0,
        max_route_time,
        True,
        time_dimension_name,
    )
    time_dimension = routing.GetDimensionOrDie(time_dimension_name)

    if vehicle_capacity > 0:
        def demand_callback(from_index: int) -> int:
            node = manager.IndexToNode(from_index)
            if node < len(stops):
                return stops[node].demand
            return 0

        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimension(
            demand_callback_index,
            0,
            vehicle_capacity,
            True,
            "Capacity",
        )
        capacity_dimension = routing.GetDimensionOrDie("Capacity")

        for vehicle_id in range(num_vehicles):
            capacity_dimension.CumulVar(routing.End(vehicle_id)).SetMax(0)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )

    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )

    search_parameters.time_limit.seconds = solver_time_limit

    assignment = routing.SolveFromAssignmentWithParameters(
        routing.ReadAssignmentFromRoutes(
            [[] for _ in range(num_vehicles)],
            ignore_inactive_indices=False,
        ),
        search_parameters,
    )

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

            node = manager.IndexToNode(index)
            route_indices.append(node)

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
            total_stops_visited=len(stops) - 1,
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
