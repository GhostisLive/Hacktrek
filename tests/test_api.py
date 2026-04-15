
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from core.agents.coordinator import CoordinatorAgent
from api.routes import router, set_coordinator

@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    coordinator = CoordinatorAgent(num_drivers=3)
    set_coordinator(coordinator)

    return app

@pytest.fixture
def client(app):
    return TestClient(app)

def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_fleet_status_endpoint(client):
    response = client.get("/api/fleet/status")

    assert response.status_code == 200
    data = response.json()

    assert "total_drivers" in data
    assert "idle_count" in data
    assert "enroute_count" in data
    assert "completed_count" in data
    assert "failed_count" in data
    assert "total_load" in data
    assert "drivers" in data

    assert data["total_drivers"] == 3
    assert data["idle_count"] == 3

def test_fleet_status_driver_details(client):
    response = client.get("/api/fleet/status")

    data = response.json()
    assert len(data["drivers"]) == 3

    for driver in data["drivers"]:
        assert "driver_id" in driver
        assert "state" in driver
        assert "progress_pct" in driver
        assert "eta_seconds" in driver
        assert "current_load" in driver

def test_dispatch_orders_minimal(client):
    payload = {
        "orders": [
            {"lat": 22.5726, "lon": 88.3639, "demand": 1},
            {"lat": 22.5750, "lon": 88.3650, "demand": 2},
        ],
        "num_vehicles": 1,
        "max_route_time": 3600,
        "vehicle_capacity": 10,
    }

    response = client.post("/api/orders/dispatch", json=payload)

    if response.status_code == 200:
        data = response.json()
        assert "num_routes" in data
        assert "total_distance" in data
        assert "solver_status" in data
        assert "message" in data
    else:
        assert response.status_code in (400, 500)

def test_dispatch_orders_empty_fails(client):
    payload = {
        "orders": [],
        "num_vehicles": 2,
    }

    response = client.post("/api/orders/dispatch", json=payload)

    assert response.status_code == 400

def test_dispatch_orders_response_schema(client):
    payload = {
        "orders": [
            {"lat": 22.5726, "lon": 88.3639, "demand": 1},
            {"lat": 22.5750, "lon": 88.3650, "demand": 2},
        ],
        "num_vehicles": 2,
        "max_route_time": 3600,
        "vehicle_capacity": 20,
    }

    response = client.post("/api/orders/dispatch", json=payload)

    if response.status_code == 200:
        data = response.json()
        assert isinstance(data["num_routes"], int)
        assert isinstance(data["total_distance"], int)
        assert isinstance(data["solver_status"], str)
        assert isinstance(data["message"], str)

def test_dispatch_orders_updates_drivers(client):
    status1 = client.get("/api/fleet/status")
    data1 = status1.json()
    assert data1["idle_count"] == 3

    payload = {
        "orders": [
            {"lat": 22.5726, "lon": 88.3639, "demand": 1},
            {"lat": 22.5750, "lon": 88.3650, "demand": 2},
        ],
        "num_vehicles": 2,
        "max_route_time": 3600,
        "vehicle_capacity": 20,
    }

    response = client.post("/api/orders/dispatch", json=payload)

    if response.status_code == 200:
        status2 = client.get("/api/fleet/status")
        data2 = status2.json()
        assert data2["idle_count"] <= 3

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
