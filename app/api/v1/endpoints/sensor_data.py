"""Endpoints for ingesting sensor readings."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections.sensor_readings import insert_sensor_reading
from app.db.mongodb import get_db
from app.models.sensor_models import SensorData
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

