"""Endpoints for ingesting eosm LoRa sensor readings."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections.eosm_readings import find_recent_sensor_readings
from app.db.mongodb import get_db
from app.models.eosm_sensor_models import LoRaSensorIngest
from app.services.eosm_iot_service import ingest_lora_reading
from app.utils.response_builder import success_response

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/",
    summary="List recent sensor readings",
    response_model=dict,
    tags=["sensor-data"],
)
async def list_sensor_readings(
    limit: int = Query(20, ge=1, le=200),
    basestation_id: str | None = Query(None, alias="basestationId"),
    greenhouse_id: str | None = Query(None, alias="greenhouseId"),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Return the most recent sensor readings for dashboards."""
    readings = await find_recent_sensor_readings(
        db,
        limit=limit,
        basestation_id=basestation_id,
        greenhouse_id=greenhouse_id,
    )
    return success_response(message="ok", data={"items": readings})


@router.post(
    "/ingest",
    summary="Ingest sensor reading from LoRa gateway",
    status_code=status.HTTP_201_CREATED,
    tags=["sensor-data", "iot"],
)
async def ingest_lora_sensor_reading(
    payload: LoRaSensorIngest, db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    """Validate and persist a LoRa gateway sensor reading."""
    # ================= eosm component start: LoRa ingestion endpoint =================
    try:
        return await ingest_lora_reading(payload, db)
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        logger.exception(
            "Unexpected failure while inserting LoRa sensor reading",
            extra={"basestation_id": payload.basestation_id},
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to ingest sensor data due to an internal error",
        )
    # ================= eosm component end =================

