
import pytest
import asyncio
from datetime import datetime, timedelta
from core.agents.driver import DriverAgent, DriverState, DriverStatus
from core.agents.coordinator import CoordinatorAgent
from core.vrp.models import Route

class TestDriverAgent:

    def test_driver_creation(self):
        driver = DriverAgent(driver_id=0)
        assert driver.driver_id == 0
        assert driver.state == DriverState.IDLE

    def test_driver_assign_route(self):
        driver = DriverAgent(0)
        route_stops = [0, 1, 2, 3, 0]
        total_time = 300
        load = 5

        driver.assign_route(route_stops, total_time, load)

        assert driver.state == DriverState.ASSIGNED
        assert driver.route_stops == route_stops
        assert driver.total_route_time == total_time
        assert driver.current_load == load
        assert driver.assigned_at is not None

    def test_driver_state_transition_idle_to_assigned(self):
        driver = DriverAgent(0)
        assert driver.state == DriverState.IDLE

        driver.assign_route([0, 1, 0], 100, 1)

        assert driver.state == DriverState.ASSIGNED

    def test_driver_state_transition_assigned_to_enroute(self):
        driver = DriverAgent(0)
        driver.assign_route([0, 1, 0], 100, 1)
        assert driver.state == DriverState.ASSIGNED

        driver.start_route((22.5726, 88.3639))

        assert driver.state == DriverState.ENROUTE
        assert driver.started_at is not None
        assert driver.current_location == (22.5726, 88.3639)

    def test_driver_cannot_assign_to_non_idle(self):
        driver = DriverAgent(0)
        driver.assign_route([0, 1, 0], 100, 1)
        assert driver.state == DriverState.ASSIGNED

        driver.assign_route([0, 2, 0], 200, 2)

        assert driver.route_stops == [0, 1, 0]

    def test_driver_complete_stop(self):
        driver = DriverAgent(0)
        driver.assign_route([0, 1, 2, 0], 300, 5)
        driver.start_route((22.5726, 88.3639))

        driver.complete_stop(1, 2, 50)

        assert 1 in driver.completed_stops
        assert driver.current_load == 3

    def test_driver_complete_route(self):
        driver = DriverAgent(0)
        driver.assign_route([0, 1, 0], 100, 1)
        driver.start_route((22.5726, 88.3639))

        driver.complete_route((22.5726, 88.3639))

        assert driver.state == DriverState.COMPLETED
        assert driver.completed_at is not None
        assert driver.eta_seconds == 0

    def test_driver_mark_failed(self):
        driver = DriverAgent(0)
        driver.assign_route([0, 1, 2, 0], 300, 5)
        driver.start_route((22.5726, 88.3639))

        driver.mark_failed("Vehicle breakdown")

        assert driver.state == DriverState.FAILED
        assert driver.failure_reason == "Vehicle breakdown"

    def test_driver_progress_percentage(self):
        driver = DriverAgent(0)
        driver.assign_route([0, 1, 2, 3, 0], 300, 5)
        driver.start_route((22.5726, 88.3639))

        driver.complete_stop(1, 1, 50)
        driver.complete_stop(2, 1, 100)

        progress = driver.progress_pct
        assert progress == pytest.approx(66.6, abs=1.0)

    def test_driver_reset(self):
        driver = DriverAgent(0)
        driver.assign_route([0, 1, 0], 100, 1)
        driver.start_route((22.5726, 88.3639))
        driver.complete_route((22.5726, 88.3639))

        driver.reset()

        assert driver.state == DriverState.IDLE
        assert driver.route_stops == []
        assert driver.current_location is None

    def test_driver_get_status(self):
        driver = DriverAgent(0)
        driver.assign_route([0, 1, 2, 0], 300, 5)
        driver.start_route((22.5726, 88.3639))

        status = driver.get_status()

        assert isinstance(status, DriverStatus)
        assert status.driver_id == 0
        assert status.state == DriverState.ENROUTE
        assert status.current_location == (22.5726, 88.3639)

class TestCoordinatorAgent:

    @pytest.mark.asyncio
    async def test_coordinator_creation(self):
        coord = CoordinatorAgent(num_drivers=5)
        assert len(coord.drivers) == 5
        assert not coord.is_running

    @pytest.mark.asyncio
    async def test_coordinator_dispatch_solution(self):
        from core.vrp.models import Solution

        coord = CoordinatorAgent(num_drivers=2)

        routes = [
            Route(vehicle_id=0, stops=[0, 1, 2, 0], total_distance=300, total_demand=5),
            Route(vehicle_id=1, stops=[0, 3, 4, 0], total_distance=250, total_demand=3),
        ]
        solution = Solution(routes=routes)

        await coord.dispatch_solution(solution)

        assert coord.drivers[0].state == DriverState.ASSIGNED
        assert coord.drivers[1].state == DriverState.ASSIGNED
        assert coord.drivers[0].route_stops == [0, 1, 2, 0]
        assert coord.drivers[1].route_stops == [0, 3, 4, 0]

    @pytest.mark.asyncio
    async def test_coordinator_polling_loop(self):
        coord = CoordinatorAgent(num_drivers=2)
        coord.polling_interval_sec = 0.1

        routes = [
            Route(vehicle_id=0, stops=[0, 1, 0], total_distance=100, total_demand=1),
        ]
        from core.vrp.models import Solution
        solution = Solution(routes=routes)
        await coord.dispatch_solution(solution)

        await coord.start_polling()

        await asyncio.sleep(0.2)

        status = coord.get_fleet_status()
        assert status["summary"]["total_drivers"] == 2
        assert status["summary"]["idle"] == 1
        assert status["summary"]["enroute"] == 0

        await coord.stop_polling()

    @pytest.mark.asyncio
    async def test_coordinator_get_fleet_status(self):
        coord = CoordinatorAgent(num_drivers=3)

        status = coord.get_fleet_status()

        assert status["summary"]["total_drivers"] == 3
        assert status["summary"]["idle"] == 3
        assert status["summary"]["enroute"] == 0
        assert len(status["drivers"]) == 3

    @pytest.mark.asyncio
    async def test_coordinator_detects_delays(self):
        coord = CoordinatorAgent(num_drivers=1)
        coord.delay_threshold_sec = 5

        driver = coord.drivers[0]
        driver.assign_route([0, 1, 0], 10, 1)
        driver.start_route((22.5726, 88.3639))

        driver.started_at = datetime.now() - timedelta(seconds=20)

        driver.eta_seconds = 5

        assert driver.is_delayed

    @pytest.mark.asyncio
    async def test_coordinator_detects_imbalance(self):
        coord = CoordinatorAgent(num_drivers=2)

        driver0 = coord.drivers[0]
        driver1 = coord.drivers[1]

        driver0.assign_route([0, 1, 2, 3, 0], 300, 10)
        driver1.assign_route([0, 4, 0], 100, 1)

        driver0.start_route((22.5726, 88.3639))
        driver1.start_route((22.5726, 88.3639))

        statuses = [driver0.get_status(), driver1.get_status()]

        loads = [s.current_load for s in statuses]
        avg_load = sum(loads) / len(loads)
        max_load = max(loads)

        if avg_load > 0:
            imbalance = (max_load - avg_load) / avg_load
            assert imbalance > 0.3

    @pytest.mark.asyncio
    async def test_coordinator_handles_failures(self):
        coord = CoordinatorAgent(num_drivers=1)

        driver = coord.drivers[0]
        driver.assign_route([0, 1, 2, 0], 300, 5)
        driver.start_route((22.5726, 88.3639))

        driver.mark_failed("Engine failure")
        assert driver.state == DriverState.FAILED

        statuses = [driver.get_status()]
        assert statuses[0].state == DriverState.FAILED

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
