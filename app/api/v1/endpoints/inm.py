"""Endpoints for INM model interactions and sensor data CRUD."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.collections.inm_readings import (
    create_inm_reading,
    delete_inm_reading,
    get_all_inm_readings,
    get_inm_reading_by_id,
    update_inm_reading,
)
from app.db.mongodb import get_db
from app.ml.inm.inm_inference import predict
from app.models.inm_models import INMSensorData, INMSensorDataUpdate

router = APIRouter()


# -----------------------------------------------------------------------------
# Prediction Endpoint
# -----------------------------------------------------------------------------


@router.post("/predict", summary="Run INM prediction (stub)")
async def inm_predict(payload: dict) -> dict:
    """Invoke the INM stub prediction.

    TODO: Replace with real model inputs/outputs once INM model is integrated.
    """
    return predict(payload)


# -----------------------------------------------------------------------------
# INM Sensor Data CRUD Endpoints
# -----------------------------------------------------------------------------


@router.post("/sensor-data", summary="Create INM sensor reading", status_code=201)
async def create_sensor_data(data: INMSensorData, db=Depends(get_db)) -> dict:
    """Create a new INM sensor reading.

    If timestamp is not provided, it will be set to the current UTC time.
    """
    payload = data.model_dump()
    if payload.get("timestamp") is None:
        payload["timestamp"] = datetime.now(timezone.utc)

    reading_id = await create_inm_reading(db, payload)
    return {
        "status": "created",
        "id": reading_id,
        "message": "INM sensor reading created successfully",
    }


@router.get("/sensor-data", summary="Get all INM sensor readings")
async def get_all_sensor_data(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    db=Depends(get_db),
) -> dict:
    """Retrieve all INM sensor readings with pagination."""
    readings = await get_all_inm_readings(db, skip=skip, limit=limit)
    return {
        "status": "ok",
        "count": len(readings),
        "skip": skip,
        "limit": limit,
        "data": readings,
    }


@router.get("/sensor-data/{reading_id}", summary="Get INM sensor reading by ID")
async def get_sensor_data_by_id(reading_id: str, db=Depends(get_db)) -> dict:
    """Retrieve a single INM sensor reading by its ID."""
    reading = await get_inm_reading_by_id(db, reading_id)
    if not reading:
        raise HTTPException(
            status_code=404,
            detail=f"INM sensor reading with id '{reading_id}' not found",
        )
    return {"status": "ok", "data": reading}


@router.put("/sensor-data/{reading_id}", summary="Update INM sensor reading")
async def update_sensor_data(
    reading_id: str, data: INMSensorDataUpdate, db=Depends(get_db)
) -> dict:
    """Update an existing INM sensor reading by its ID."""
    # Check if reading exists first
    existing = await get_inm_reading_by_id(db, reading_id)
    if not existing:
        raise HTTPException(
            status_code=404,
            detail=f"INM sensor reading with id '{reading_id}' not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    updated = await update_inm_reading(db, reading_id, update_data)
    return {
        "status": "updated",
        "message": "INM sensor reading updated successfully",
        "data": updated,
    }


@router.delete("/sensor-data/{reading_id}", summary="Delete INM sensor reading")
async def delete_sensor_data(reading_id: str, db=Depends(get_db)) -> dict:
    """Delete an INM sensor reading by its ID."""
    deleted = await delete_inm_reading(db, reading_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"INM sensor reading with id '{reading_id}' not found",
        )
    return {
        "status": "deleted",
        "message": f"INM sensor reading '{reading_id}' deleted successfully",
    }

