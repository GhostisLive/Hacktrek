import asyncio
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Optional
from loguru import logger


class DriverState(Enum):
    IDLE = "idle"
    ASSIGNED = "assigned"
    ENROUTE = "enroute"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DriverStatus:
    driver_id: int
    state: DriverState
    current_location: tuple[float, float] | None = None
    route_stops: list[int] = field(default_factory=list)
    completed_stops: list[int] = field(default_factory=list)
    eta_seconds: int = 0
    total_route_time: int = 0
    current_load: int = 0
    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    is_delayed: bool = False


class DriverAgent:

    def __init__(self, driver_id: int):
        self.driver_id = driver_id
        self.state = DriverState.IDLE
        self.route_stops: list[int] = []
        self.completed_stops: list[int] = []
        self.current_stop_index = 0
        self.current_location: tuple[float, float] | None = None
        self.eta_seconds = 0
        self.total_route_time = 0
        self.current_load = 0
        self.assigned_at: Optional[datetime] = None
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.failure_reason: Optional[str] = None

    def assign_route(
        self,
        route_stops: list[int],
        total_route_time: int,
        initial_load: int,
    ):

        if self.state != DriverState.IDLE:
            logger.warning(f"Driver {self.driver_id} cannot accept route; state={self.state}")
            return

        self.route_stops = route_stops
        self.total_route_time = total_route_time
        self.current_load = initial_load
        self.eta_seconds = total_route_time
        self.state = DriverState.ASSIGNED
        self.assigned_at = datetime.now()
        self.current_stop_index = 0
        self.completed_stops = []
        logger.info(f"Driver {self.driver_id} assigned route: {len(route_stops)} stops")

    def start_route(self, current_location: tuple[float, float]):

        if self.state != DriverState.ASSIGNED:
            logger.warning(f"Driver {self.driver_id} cannot start; state={self.state}")
            return

        self.state = DriverState.ENROUTE
        self.started_at = datetime.now()
        self.current_location = current_location
        logger.info(f"Driver {self.driver_id} started route at {current_location}")

    def complete_stop(self, stop_id: int, items_delivered: int, time_elapsed: int):

        if self.state not in (DriverState.ENROUTE, DriverState.ASSIGNED):
            return

        if stop_id not in self.completed_stops:
            self.completed_stops.append(stop_id)

        self.current_load -= items_delivered
        self.eta_seconds = max(0, self.total_route_time - time_elapsed)
        logger.debug(f"Driver {self.driver_id} completed stop {stop_id}, ETA {self.eta_seconds}s")

    def complete_route(self, final_location: tuple[float, float]):

        if self.state != DriverState.ENROUTE:
            return

        self.state = DriverState.COMPLETED
        self.completed_at = datetime.now()
        self.current_location = final_location
        self.eta_seconds = 0
        logger.info(f"Driver {self.driver_id} completed route")

    def mark_failed(self, reason: str):

        self.state = DriverState.FAILED
        self.failure_reason = reason
        logger.error(f"Driver {self.driver_id} failed: {reason}")

    def get_status(self) -> DriverStatus:

        return DriverStatus(
            driver_id=self.driver_id,
            state=self.state,
            current_location=self.current_location,
            route_stops=self.route_stops,
            completed_stops=self.completed_stops,
            eta_seconds=self.eta_seconds,
            total_route_time=self.total_route_time,
            current_load=self.current_load,
            assigned_at=self.assigned_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            is_delayed=self.is_delayed,
        )

    @property
    def is_delayed(self) -> bool:

        if self.state != DriverState.ENROUTE or not self.started_at:
            return False

        elapsed = (datetime.now() - self.started_at).total_seconds()
        return elapsed > (self.total_route_time * 0.7) and self.state != DriverState.COMPLETED

    @property
    def progress_pct(self) -> float:

        if not self.route_stops:
            return 0.0
        non_depot_stops = [s for s in self.route_stops if s != 0]
        if not non_depot_stops:
            return 0.0
        completed = len([s for s in self.completed_stops if s != 0])
        return (completed / len(non_depot_stops)) * 100.0

    def reset(self):

        self.state = DriverState.IDLE
        self.route_stops = []
        self.completed_stops = []
        self.current_stop_index = 0
        self.current_location = None
        self.eta_seconds = 0
        self.total_route_time = 0
        self.current_load = 0
        self.assigned_at = None
        self.started_at = None
        self.completed_at = None
        self.failure_reason = None
        logger.info(f"Driver {self.driver_id} reset to IDLE")
