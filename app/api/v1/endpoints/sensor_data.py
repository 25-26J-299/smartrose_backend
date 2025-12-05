"""Endpoints for ingesting sensor readings."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections.sensor_readings import insert_sensor_reading
from app.db.mongodb import get_db
from app.models.sensor_models import SensorData
from app.utils.response_builder import success_response

router = APIRouter()


@router.post(
    "/",
    summary="Ingest a new sensor reading",
)
async def ingest_sensor_data(
    payload: SensorData, db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    """Validate and persist a sensor reading payload."""

    record = payload.model_dump()
    record["created_at"] = datetime.utcnow()

    inserted_id = await insert_sensor_reading(db, record)
    if not inserted_id:
        raise HTTPException(status_code=500, detail="Unable to store sensor data")

    return success_response(
        message="Sensor data stored successfully", data={"id": inserted_id}
    )

