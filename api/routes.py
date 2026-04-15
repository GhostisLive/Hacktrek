from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from loguru import logger

from core.agents.coordinator import CoordinatorAgent

router = APIRouter()

coordinator: Optional[CoordinatorAgent] = None


def set_coordinator(coord: CoordinatorAgent):
    global coordinator
    coordinator = coord


class OrderLocation(BaseModel):
    lat: float
    lon: float
    demand: int = 1


class DispatchRequest(BaseModel):
    orders: list[OrderLocation]
    num_vehicles: int = 5
    max_route_time: int = 14400
    vehicle_capacity: int = 20


class DispatchResponse(BaseModel):
    num_routes: int
    total_distance: int
    solver_status: str
    message: str


@router.post("/orders/dispatch", response_model=DispatchResponse)
async def dispatch_orders(request: DispatchRequest):
    if not coordinator:
        raise HTTPException(status_code=500, detail="Coordinator not initialized")

    if not request.orders:
        raise HTTPException(status_code=400, detail="No orders provided")

    try:
        from core.graph.loader import load_graph
        from core.graph.matrix import build_distance_matrix
        from core.vrp.models import Stop
        from core.vrp.solver import solve_vrp

        logger.info(f"Dispatching {len(request.orders)} orders...")
        G = load_graph()

        depot_lat = sum(o.lat for o in request.orders) / len(request.orders)
        depot_lon = sum(o.lon for o in request.orders) / len(request.orders)

        locations = [{"lat": depot_lat, "lon": depot_lon}]
        locations.extend([{"lat": o.lat, "lon": o.lon} for o in request.orders])

        matrix, osm_nodes = build_distance_matrix(G, locations)
        logger.info(f"Distance matrix built: {matrix.shape}")

        stops = [
            Stop(
                id=0,
                lat=depot_lat,
                lon=depot_lon,
                demand=0,
            )
        ]
        for i, order in enumerate(request.orders, 1):
            stops.append(
                Stop(
                    id=i,
                    lat=order.lat,
                    lon=order.lon,
                    demand=order.demand,
                )
            )

        solution = solve_vrp(
            distance_matrix=matrix,
            stops=stops,
            num_vehicles=request.num_vehicles,
            max_route_time=request.max_route_time,
            vehicle_capacity=request.vehicle_capacity,
            solver_time_limit=30,
        )

        if not solution.routes:
            raise HTTPException(status_code=500, detail="VRP solver failed to find solution")

        await coordinator.dispatch_solution(solution)

        logger.success(
            f"Dispatched {len(solution.routes)} routes, "
            f"{solution.total_stops_visited} stops, "
            f"{solution.total_distance}s total time"
        )

        return DispatchResponse(
            num_routes=len(solution.routes),
            total_distance=solution.total_distance,
            solver_status=solution.solver_status,
            message=f"Dispatched {len(solution.routes)} routes to {len(solution.routes)} drivers",
        )

    except Exception as e:
        logger.error(f"Dispatch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class FleetStatusResponse(BaseModel):
    total_drivers: int
    idle_count: int
    enroute_count: int
    completed_count: int
    failed_count: int
    total_load: int
    drivers: list[dict]


@router.get("/fleet/status", response_model=FleetStatusResponse)
async def get_fleet_status():
    if not coordinator:
        raise HTTPException(status_code=500, detail="Coordinator not initialized")

    status = coordinator.get_fleet_status()

    return FleetStatusResponse(
        total_drivers=status["summary"]["total_drivers"],
        idle_count=status["summary"]["idle"],
        enroute_count=status["summary"]["enroute"],
        completed_count=status["summary"]["completed"],
        failed_count=status["summary"]["failed"],
        total_load=status["summary"]["total_load"],
        drivers=status["drivers"],
    )
