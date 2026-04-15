from dataclasses import dataclass
from typing import List


@dataclass
class Stop:
    id: int
    lat: float
    lon: float
    demand: int = 1
    time_window_start: int | None = None
    time_window_end: int | None = None


@dataclass
class Route:
    vehicle_id: int
    stops: List[int]
    total_distance: int
    total_demand: int
    start_time: int = 0
    end_time: int = 0

    @property
    def duration(self) -> int:
        return self.end_time - self.start_time

    @property
    def is_valid(self) -> bool:
        return len(self.stops) >= 2 and self.stops[0] == 0 and self.stops[-1] == 0


@dataclass
class Solution:
    routes: List[Route]
    total_distance: int = 0
    total_stops_visited: int = 0
    solve_time_ms: float = 0.0
    solver_status: str = "UNKNOWN"

    def is_complete(self, num_orders: int) -> bool:
        visited = set()
        for route in self.routes:
            for stop_id in route.stops:
                if stop_id != 0:
                    visited.add(stop_id)
        return len(visited) == num_orders

    def vehicle_count(self) -> int:
        return len(self.routes)

    def total_load(self) -> int:
        return sum(r.total_demand for r in self.routes)
