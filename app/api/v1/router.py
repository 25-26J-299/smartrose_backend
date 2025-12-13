"""API router that collects all v1 endpoints."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, edas, fm, health, inm, eosm_sensor_data
from app.core.config import settings

# Prefix routes with the configured API version (e.g., /api/v1)
api_router = APIRouter(prefix=f"/{settings.api_version}")

api_router.include_router(
    eosm_sensor_data.router, prefix="/eosm-data", tags=["sensor-data"]
)
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(inm.router, prefix="/inm", tags=["inm"])
api_router.include_router(fm.router, prefix="/fm", tags=["fm"])
api_router.include_router(edas.router, prefix="/edas", tags=["edas"])

