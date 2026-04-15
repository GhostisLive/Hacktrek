import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger
import uvicorn

from core.graph.loader import load_graph, graph_summary
from core.agents.coordinator import CoordinatorAgent
from api.routes import router, set_coordinator
import config


def smoke_test():
    logger.info("=== FleetMind — Smoke Test ===")

    G = load_graph()
    summary = graph_summary(G)

    logger.success(f"Nodes   : {summary['nodes']:,}")
    logger.success(f"Edges   : {summary['edges']:,}")
    logger.success(f"CRS     : {summary['crs']}")
    logger.info("✓ Graph load OK")


coordinator: CoordinatorAgent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global coordinator

    logger.info("=== FleetMind API Starting ===")
    smoke_test()

    coordinator = CoordinatorAgent(num_drivers=config.MAX_DRIVERS)
    set_coordinator(coordinator)
    await coordinator.start_polling()

    logger.success(f"✓ Coordinator running with {config.MAX_DRIVERS} drivers")

    yield

    logger.info("Shutting down coordinator...")
    await coordinator.stop_polling()
    logger.success("✓ Coordinator stopped")


def start_api():
    app = FastAPI(
        title="FleetMind",
        description="Multi-driver delivery routing with agent coordination",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(router, prefix="/api")

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    logger.info(f"Starting API on {config.API_HOST}:{config.API_PORT}")
    uvicorn.run(
        app,
        host=config.API_HOST,
        port=config.API_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "api":
        start_api()
    else:
        smoke_test()