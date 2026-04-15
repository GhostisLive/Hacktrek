"""
VRP Solver Data Models

Defines the core dataclasses for representing delivery stops, vehicle routes, and solutions.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class Stop:
    """
    A single delivery location.

    Attributes:
        id: Unique identifier (0 = depot, >0 = delivery orders)
        lat: Latitude coordinate
        lon: Longitude coordinate
        demand: Items to deliver (units, weight, etc.)
        time_window_start: Earliest arrival time (seconds since start, or None)
        time_window_end: Latest arrival time (seconds since start, or None)
    """
    id: int
    lat: float
    lon: float
    demand: int = 1
    time_window_start: int | None = None
    time_window_end: int | None = None


@dataclass
class Route:
    """
    One vehicle's complete journey from depot → stops → depot.

    Attributes:
        vehicle_id: Unique vehicle identifier
        stops: Ordered list of Stop IDs visited (includes depot at start/end)
        total_distance: Sum of travel times in seconds
        total_demand: Sum of items delivered
        start_time: Time vehicle departs depot (seconds)
        end_time: Time vehicle returns to depot (seconds)
    """
    vehicle_id: int
    stops: List[int]  # [0, stop1, stop2, ..., 0]
    total_distance: int  # travel time in seconds
    total_demand: int
    start_time: int = 0
    end_time: int = 0

    @property
    def duration(self) -> int:
        """Total route duration (end_time - start_time)."""
        return self.end_time - self.start_time

    @property
    def is_valid(self) -> bool:
        """Route is valid if it starts and ends at depot (0)."""
        return len(self.stops) >= 2 and self.stops[0] == 0 and self.stops[-1] == 0


@dataclass
class Solution:
    """
    Complete solution: all vehicle routes for a dispatch problem.

    Attributes:
        routes: List of Route objects
        total_distance: Sum of all route distances
        total_stops_visited: Count of unique delivery stops
        solve_time_ms: Solver runtime in milliseconds
        solver_status: Status from OR-Tools (OPTIMAL, ROUTING_NOT_MADE, ROUTING_PARTIAL, ...)
    """
    routes: List[Route]
    total_distance: int = 0
    total_stops_visited: int = 0
    solve_time_ms: float = 0.0
    solver_status: str = "UNKNOWN"

    def is_complete(self, num_orders: int) -> bool:
        """
        Check if solution covers all delivery stops (excluding depot).
        Returns True if every order ID from 1..num_orders is visited exactly once.
        """
        visited = set()
        for route in self.routes:
            for stop_id in route.stops:
                if stop_id != 0:  # exclude depot
                    visited.add(stop_id)
        return len(visited) == num_orders

    def vehicle_count(self) -> int:
        """Number of vehicles with assigned routes."""
        return len(self.routes)

    def total_load(self) -> int:
        """Sum of all demand across all routes."""
        return sum(r.total_demand for r in self.routes)
