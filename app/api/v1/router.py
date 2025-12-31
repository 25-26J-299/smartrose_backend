"""API router that collects all v1 endpoints."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    edas,
    eosm_predictions,
    eosm_sensor_data,
    fm,
    health,
    inm,
)
from app.core.config import settings

# Prefix routes with the configured API version (e.g., /api/v1)
api_router = APIRouter(prefix=f"/{settings.api_version}")

api_router.include_router(
    eosm_sensor_data.router, prefix="/eosm-data", tags=["sensor-data"]
)
api_router.include_router(
    eosm_predictions.router, prefix="/eosm-predictions", tags=["eosm-predictions"]
)
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(inm.router, prefix="/inm", tags=["inm"])
api_router.include_router(fm.router)  # Router has prefix="/fm" and tags=["FM"], combined with api_router prefix="/api/v1" = "/api/v1/fm"
api_router.include_router(edas.router, prefix="/edas", tags=["edas"])
