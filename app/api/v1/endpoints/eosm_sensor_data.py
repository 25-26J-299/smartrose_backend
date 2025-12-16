"""Endpoints for ingesting eosm LoRa sensor readings."""

import logging
from datetime import datetime, timezone

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
    summary="List sensor readings with optional date range filtering",
    response_model=dict,
    tags=["sensor-data"],
)
async def list_sensor_readings(
    limit: int = Query(20, ge=1, le=2000),
    basestation_id: str | None = Query(None, alias="basestationId"),
    greenhouse_id: str | None = Query(None, alias="greenhouseId"),
    start_date: str | None = Query(None, alias="startDate", description="Start date in YYYY-MM-DD format"),
    end_date: str | None = Query(None, alias="endDate", description="End date in YYYY-MM-DD format"),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Return sensor readings with optional filters.
    
    Supports date range filtering using startDate and endDate (YYYY-MM-DD format).
    Dates are converted to epoch timestamps for querying the timestamp field.
    """
    start_timestamp = None
    end_timestamp = None
    
    if start_date:
        try:
            # Parse date as UTC to avoid timezone issues
            # Interpret the date string as a date in UTC (start of day UTC)
            dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            start_timestamp = int(dt.timestamp())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid startDate format. Expected YYYY-MM-DD, got: {start_date}"
            )
    
    if end_date:
        try:
            # Parse date as UTC and set to end of day (23:59:59 UTC)
            dt = datetime.strptime(end_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
            end_timestamp = int(dt.timestamp())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid endDate format. Expected YYYY-MM-DD, got: {end_date}"
            )
    
    readings = await find_recent_sensor_readings(
        db,
        limit=limit,
        basestation_id=basestation_id,
        greenhouse_id=greenhouse_id,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
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

