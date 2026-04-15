"""
Coordinator Agent

Manages a fleet of drivers, dispatches routes, and monitors performance.
Detects delays, load imbalances, and triggers driver reassignment.
"""

import asyncio
from datetime import datetime
from typing import Optional
from loguru import logger

from core.agents.driver import DriverAgent, DriverState, DriverStatus
from core.vrp.models import Solution, Route
from config import COORDINATOR_POLL_SEC, DELAY_THRESHOLD_SEC, IMBALANCE_THRESHOLD


class CoordinatorAgent:
    """
    Central coordinator for a delivery fleet.

    Responsibilities:
    - Dispatch routes to idle drivers
    - Poll drivers every 5 seconds for status updates
    - Detect delays (actual time > ETA + threshold)
    - Flag load imbalances and trigger rebalancing
    - Reassign routes from failed drivers
    """

    def __init__(self, num_drivers: int):
        self.drivers = {i: DriverAgent(i) for i in range(num_drivers)}
        self.current_solution: Optional[Solution] = None
        self.polling_interval_sec = COORDINATOR_POLL_SEC
        self.delay_threshold_sec = DELAY_THRESHOLD_SEC
        self.imbalance_threshold = IMBALANCE_THRESHOLD
        self.is_running = False
        self._polling_task: Optional[asyncio.Task] = None
        logger.info(f"Coordinator initialized with {num_drivers} drivers")

    async def dispatch_solution(self, solution: Solution):
        """
        Assign all routes from a solution to available drivers.

        Parameters
        ----------
        solution : Solution
            VRP solution with routes ready for dispatch
        """
        self.current_solution = solution

        available_drivers = [
            d for d in self.drivers.values() if d.state == DriverState.IDLE
        ]

        if len(solution.routes) > len(available_drivers):
            logger.warning(
                f"More routes ({len(solution.routes)}) than available drivers ({len(available_drivers)}). "
                "Some drivers will be idle."
            )

        for route, driver in zip(solution.routes, available_drivers):
            # Convert stop indices to stop IDs (assuming 0 = depot)
            route_stop_ids = route.stops

            driver.assign_route(
                route_stops=route_stop_ids,
                total_route_time=route.total_distance,
                initial_load=route.total_demand,
            )
            logger.info(
                f"Assigned route to driver {driver.driver_id}: "
                f"{len(route_stop_ids)} stops, {route.total_distance}s"
            )

    async def start_polling(self):
        """
        Start the main coordinator polling loop (runs every COORDINATOR_POLL_SEC).

        Call this once at startup; it runs indefinitely until stop_polling() is called.
        """
        if self.is_running:
            logger.warning("Coordinator already polling")
            return

        self.is_running = True
        self._polling_task = asyncio.create_task(self._polling_loop())
        logger.info(f"Coordinator polling started (interval={self.polling_interval_sec}s)")

    async def stop_polling(self):
        """Stop the polling loop gracefully."""
        self.is_running = False
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        logger.info("Coordinator polling stopped")

    async def _polling_loop(self):
        """
        Main polling loop: every COORDINATOR_POLL_SEC seconds,
        check driver statuses and run intelligence routines.
        """
        while self.is_running:
            try:
                await asyncio.sleep(self.polling_interval_sec)

                # Collect status from all drivers
                statuses = [d.get_status() for d in self.drivers.values()]

                # Run intelligence checks
                await self._check_delays(statuses)
                await self._check_imbalances(statuses)
                await self._handle_failures(statuses)

                logger.debug(
                    f"Polling cycle: {self._summarize_fleet(statuses)}"
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")

    async def _check_delays(self, statuses: list[DriverStatus]):
        """
        Detect drivers that are delayed beyond DELAY_THRESHOLD_SEC.

        Parameters
        ----------
        statuses : list[DriverStatus]
            Current status of all drivers
        """
        delayed_drivers = []

        for status in statuses:
            if status.state != DriverState.ENROUTE or not status.started_at:
                continue

            elapsed = (datetime.now() - status.started_at).total_seconds()
            expected_eta = status.total_route_time
            delay = elapsed - expected_eta

            if delay > self.delay_threshold_sec:
                delayed_drivers.append({
                    "driver_id": status.driver_id,
                    "delay_sec": delay,
                    "eta_original": expected_eta,
                    "elapsed": elapsed,
                })

        if delayed_drivers:
            logger.warning(f"Delayed drivers detected: {delayed_drivers}")
            # In production: send alerts, check for breakdown, reroute, etc.

    async def _check_imbalances(self, statuses: list[DriverStatus]):
        """
        Detect load imbalances across active routes.
        Flag if any driver has >30% more load than average.

        Parameters
        ----------
        statuses : list[DriverStatus]
            Current status of all drivers
        """
        enroute = [s for s in statuses if s.state == DriverState.ENROUTE]
        if len(enroute) < 2:
            return

        loads = [s.current_load for s in enroute]
        avg_load = sum(loads) / len(loads)
        max_load = max(loads)

        if avg_load > 0:
            imbalance = (max_load - avg_load) / avg_load
            if imbalance > self.imbalance_threshold:
                logger.warning(
                    f"Load imbalance detected: max_load={max_load}, "
                    f"avg={avg_load:.1f}, imbalance={imbalance*100:.1f}%"
                )
                # In production: trigger load redistribution

    async def _handle_failures(self, statuses: list[DriverStatus]):
        """
        Handle failed routes by resetting driver and flagging for reassignment.

        Parameters
        ----------
        statuses : list[DriverStatus]
            Current status of all drivers
        """
        for status in statuses:
            if status.driver_id in self.drivers:
                driver = self.drivers[status.driver_id]
                if driver.state == DriverState.FAILED:
                    logger.error(
                        f"Driver {driver.driver_id} failed: {driver.failure_reason}. "
                        "Reassignment needed."
                    )
                    # Mark incomplete stops for reassignment
                    incomplete = [s for s in driver.route_stops if s not in driver.completed_stops]
                    logger.info(f"Incomplete stops to reassign: {incomplete}")
                    # Reset driver for next assignment
                    driver.reset()

    def _summarize_fleet(self, statuses: list[DriverStatus]) -> str:
        """Compact fleet summary for logging."""
        idle = len([s for s in statuses if s.state == DriverState.IDLE])
        enroute = len([s for s in statuses if s.state == DriverState.ENROUTE])
        completed = len([s for s in statuses if s.state == DriverState.COMPLETED])
        failed = len([s for s in statuses if s.state == DriverState.FAILED])
        return f"IDLE={idle}, ENROUTE={enroute}, COMPLETED={completed}, FAILED={failed}"

    def get_fleet_status(self) -> dict:
        """
        Get snapshot of entire fleet.

        Returns
        -------
        dict
            {
                "drivers": [{ driver_id, state, progress%, eta, ... }],
                "summary": { idle_count, enroute_count, completed_count, failed_count },
                "timestamp": ISO 8601
            }
        """
        statuses = [d.get_status() for d in self.drivers.values()]
        driver_data = [
            {
                "driver_id": s.driver_id,
                "state": s.state.value,
                "progress_pct": self.drivers[s.driver_id].progress_pct,
                "eta_seconds": s.eta_seconds,
                "current_load": s.current_load,
                "is_delayed": s.is_delayed,
                "completed_stops": len(s.completed_stops),
                "total_stops": len(s.route_stops),
            }
            for s in statuses
        ]

        summary = {
            "total_drivers": len(self.drivers),
            "idle": len([s for s in statuses if s.state == DriverState.IDLE]),
            "enroute": len([s for s in statuses if s.state == DriverState.ENROUTE]),
            "completed": len([s for s in statuses if s.state == DriverState.COMPLETED]),
            "failed": len([s for s in statuses if s.state == DriverState.FAILED]),
            "total_load": sum(s.current_load for s in statuses),
        }

        return {
            "drivers": driver_data,
            "summary": summary,
            "timestamp": datetime.now().isoformat(),
        }

    def get_driver(self, driver_id: int) -> Optional[DriverAgent]:
        """Get a specific driver agent by ID."""
        return self.drivers.get(driver_id)
