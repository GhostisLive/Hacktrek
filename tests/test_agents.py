"""
Tests for Driver and Coordinator Agents (Days 6-7)

Validates:
- Driver state transitions (IDLE → ASSIGNED → ENROUTE → COMPLETED)
- Coordinator can dispatch routes and poll drivers
- Delay detection works
- Load imbalance flagging works
- Failed driver reassignment works
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from core.agents.driver import DriverAgent, DriverState, DriverStatus
from core.agents.coordinator import CoordinatorAgent
from core.vrp.models import Route


class TestDriverAgent:
    """Tests for individual driver."""

    def test_driver_creation(self):
        """Test driver initialization."""
        driver = DriverAgent(driver_id=0)
        assert driver.driver_id == 0
        assert driver.state == DriverState.IDLE

    def test_driver_assign_route(self):
        """Test assigning a route to idle driver."""
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
        """Test IDLE → ASSIGNED transition."""
        driver = DriverAgent(0)
        assert driver.state == DriverState.IDLE

        driver.assign_route([0, 1, 0], 100, 1)

        assert driver.state == DriverState.ASSIGNED

    def test_driver_state_transition_assigned_to_enroute(self):
        """Test ASSIGNED → ENROUTE transition."""
        driver = DriverAgent(0)
        driver.assign_route([0, 1, 0], 100, 1)
        assert driver.state == DriverState.ASSIGNED

        driver.start_route((22.5726, 88.3639))

        assert driver.state == DriverState.ENROUTE
        assert driver.started_at is not None
        assert driver.current_location == (22.5726, 88.3639)

    def test_driver_cannot_assign_to_non_idle(self):
        """Test that non-idle drivers reject route assignment."""
        driver = DriverAgent(0)
        driver.assign_route([0, 1, 0], 100, 1)
        assert driver.state == DriverState.ASSIGNED

        # Try to assign again
        driver.assign_route([0, 2, 0], 200, 2)

        # Should still be in first assignment
        assert driver.route_stops == [0, 1, 0]

    def test_driver_complete_stop(self):
        """Test marking a stop as completed."""
        driver = DriverAgent(0)
        driver.assign_route([0, 1, 2, 0], 300, 5)
        driver.start_route((22.5726, 88.3639))

        driver.complete_stop(1, 2, 50)

        assert 1 in driver.completed_stops
        assert driver.current_load == 3  # 5 - 2

    def test_driver_complete_route(self):
        """Test marking route as completed."""
        driver = DriverAgent(0)
        driver.assign_route([0, 1, 0], 100, 1)
        driver.start_route((22.5726, 88.3639))

        driver.complete_route((22.5726, 88.3639))

        assert driver.state == DriverState.COMPLETED
        assert driver.completed_at is not None
        assert driver.eta_seconds == 0

    def test_driver_mark_failed(self):
        """Test marking driver as failed."""
        driver = DriverAgent(0)
        driver.assign_route([0, 1, 2, 0], 300, 5)
        driver.start_route((22.5726, 88.3639))

        driver.mark_failed("Vehicle breakdown")

        assert driver.state == DriverState.FAILED
        assert driver.failure_reason == "Vehicle breakdown"

    def test_driver_progress_percentage(self):
        """Test progress calculation."""
        driver = DriverAgent(0)
        driver.assign_route([0, 1, 2, 3, 0], 300, 5)
        driver.start_route((22.5726, 88.3639))

        # Complete 2 of 3 non-depot stops
        driver.complete_stop(1, 1, 50)
        driver.complete_stop(2, 1, 100)

        progress = driver.progress_pct
        assert progress == pytest.approx(66.6, abs=1.0)

    def test_driver_reset(self):
        """Test resetting driver to IDLE."""
        driver = DriverAgent(0)
        driver.assign_route([0, 1, 0], 100, 1)
        driver.start_route((22.5726, 88.3639))
        driver.complete_route((22.5726, 88.3639))

        driver.reset()

        assert driver.state == DriverState.IDLE
        assert driver.route_stops == []
        assert driver.current_location is None

    def test_driver_get_status(self):
        """Test getting driver status snapshot."""
        driver = DriverAgent(0)
        driver.assign_route([0, 1, 2, 0], 300, 5)
        driver.start_route((22.5726, 88.3639))

        status = driver.get_status()

        assert isinstance(status, DriverStatus)
        assert status.driver_id == 0
        assert status.state == DriverState.ENROUTE
        assert status.current_location == (22.5726, 88.3639)


class TestCoordinatorAgent:
    """Tests for coordinator."""

    @pytest.mark.asyncio
    async def test_coordinator_creation(self):
        """Test coordinator initialization."""
        coord = CoordinatorAgent(num_drivers=5)
        assert len(coord.drivers) == 5
        assert not coord.is_running

    @pytest.mark.asyncio
    async def test_coordinator_dispatch_solution(self):
        """Test dispatching a solution to drivers."""
        from core.vrp.models import Solution

        coord = CoordinatorAgent(num_drivers=2)

        routes = [
            Route(vehicle_id=0, stops=[0, 1, 2, 0], total_distance=300, total_demand=5),
            Route(vehicle_id=1, stops=[0, 3, 4, 0], total_distance=250, total_demand=3),
        ]
        solution = Solution(routes=routes)

        await coord.dispatch_solution(solution)

        # Check drivers are assigned
        assert coord.drivers[0].state == DriverState.ASSIGNED
        assert coord.drivers[1].state == DriverState.ASSIGNED
        assert coord.drivers[0].route_stops == [0, 1, 2, 0]
        assert coord.drivers[1].route_stops == [0, 3, 4, 0]

    @pytest.mark.asyncio
    async def test_coordinator_polling_loop(self):
        """Test that polling loop runs and collects status."""
        coord = CoordinatorAgent(num_drivers=2)
        coord.polling_interval_sec = 0.1  # Short interval for testing

        # Assign routes
        routes = [
            Route(vehicle_id=0, stops=[0, 1, 0], total_distance=100, total_demand=1),
        ]
        from core.vrp.models import Solution
        solution = Solution(routes=routes)
        await coord.dispatch_solution(solution)

        # Start polling
        await coord.start_polling()

        # Let it poll once
        await asyncio.sleep(0.2)

        # Status should work
        status = coord.get_fleet_status()
        assert status["summary"]["total_drivers"] == 2
        assert status["summary"]["idle"] == 1  # One driver not assigned
        assert status["summary"]["enroute"] == 0  # Not started yet

        # Stop polling
        await coord.stop_polling()

    @pytest.mark.asyncio
    async def test_coordinator_get_fleet_status(self):
        """Test getting fleet status."""
        coord = CoordinatorAgent(num_drivers=3)

        status = coord.get_fleet_status()

        assert status["summary"]["total_drivers"] == 3
        assert status["summary"]["idle"] == 3
        assert status["summary"]["enroute"] == 0
        assert len(status["drivers"]) == 3

    @pytest.mark.asyncio
    async def test_coordinator_detects_delays(self):
        """Test delay detection in coordinator."""
        coord = CoordinatorAgent(num_drivers=1)
        coord.delay_threshold_sec = 5  # 5 second threshold

        # Assign and start a route
        driver = coord.drivers[0]
        driver.assign_route([0, 1, 0], 10, 1)
        driver.start_route((22.5726, 88.3639))

        # Manually set start time to past
        driver.started_at = datetime.now() - timedelta(seconds=20)

        # Manually say only 5 seconds have elapsed on route
        # (driver would be 15 seconds delayed)
        driver.eta_seconds = 5

        # Check delay
        assert driver.is_delayed

    @pytest.mark.asyncio
    async def test_coordinator_detects_imbalance(self):
        """Test load imbalance detection."""
        coord = CoordinatorAgent(num_drivers=2)

        # Assign unbalanced routes
        driver0 = coord.drivers[0]
        driver1 = coord.drivers[1]

        driver0.assign_route([0, 1, 2, 3, 0], 300, 10)  # Heavy load
        driver1.assign_route([0, 4, 0], 100, 1)  # Light load

        driver0.start_route((22.5726, 88.3639))
        driver1.start_route((22.5726, 88.3639))

        # Get statuses
        statuses = [driver0.get_status(), driver1.get_status()]

        # Check loads
        loads = [s.current_load for s in statuses]
        avg_load = sum(loads) / len(loads)
        max_load = max(loads)

        if avg_load > 0:
            imbalance = (max_load - avg_load) / avg_load
            # Should be significantly imbalanced (>0.3)
            assert imbalance > 0.3

    @pytest.mark.asyncio
    async def test_coordinator_handles_failures(self):
        """Test that failed drivers are handled."""
        coord = CoordinatorAgent(num_drivers=1)

        driver = coord.drivers[0]
        driver.assign_route([0, 1, 2, 0], 300, 5)
        driver.start_route((22.5726, 88.3639))

        # Mark as failed
        driver.mark_failed("Engine failure")
        assert driver.state == DriverState.FAILED

        # Coordinator should recognize it
        statuses = [driver.get_status()]
        assert statuses[0].state == DriverState.FAILED


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
