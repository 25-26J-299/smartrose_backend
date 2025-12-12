"""Endpoints for ingesting sensor readings."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections.sensor_readings import (
    find_recent_sensor_readings,
    insert_sensor_reading,
)
from app.db.mongodb import get_db
from app.models.sensor_models import LoRaSensorIngest, SensorData
from app.services.iot_service import ingest_lora_reading
from app.utils.response_builder import success_response

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/",
    summary="Ingest a new sensor reading",
)
async def ingest_sensor_data(
    payload: SensorData, db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    """Validate and persist a sensor reading payload."""

    # Structured-ish log for ingestion to help trace device level issues.
    logger.info(
        "Sensor ingestion received",
        extra={
            "sensor_id": payload.sensor_id,
            "timestamp": payload.timestamp.isoformat(),
        },
    )

    # Additional runtime guardrails beyond pydantic ranges.
    if payload.humidity is None or payload.temperature is None:
        raise HTTPException(status_code=400, detail="Missing sensor reading values")

    record = payload.model_dump()
    record["created_at"] = datetime.utcnow()

    try:
        inserted_id = await insert_sensor_reading(db, record)
    except HTTPException:
        # Already logged upstream; re-raise.
        raise
    except Exception:  # noqa: BLE001
        logger.exception(
            "Unexpected failure while inserting sensor reading",
            extra={"sensor_id": payload.sensor_id},
        )
        raise HTTPException(
            status_code=500, detail="Unable to store sensor data due to an error"
        )

    if not inserted_id:
        logger.error(
            "Insert returned empty id",
            extra={"sensor_id": payload.sensor_id},
        )
        raise HTTPException(status_code=500, detail="Unable to store sensor data")

    return success_response(
        message="Sensor data stored successfully", data={"id": inserted_id}
    )


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

