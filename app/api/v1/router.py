"""API router that collects all v1 endpoints."""

from fastapi import APIRouter

from app.api.v1.endpoints import edas, eosm, fm, inm, sensor_data
from app.core.config import settings

# Prefix routes with the configured API version (e.g., /api/v1)
api_router = APIRouter(prefix=f"/{settings.api_version}")

api_router.include_router(
    sensor_data.router, prefix="/sensor-data", tags=["sensor-data"]
)
api_router.include_router(eosm.router, prefix="/eosm", tags=["eosm"])
api_router.include_router(inm.router, prefix="/inm", tags=["inm"])
api_router.include_router(fm.router, prefix="/fm", tags=["fm"])
api_router.include_router(edas.router, prefix="/edas", tags=["edas"])

