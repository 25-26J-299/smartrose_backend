import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.collections.edas_sensor_data import (
    create_edas_reading,
    delete_edas_reading,
    get_all_edas_readings,
    get_edas_reading_by_id,
    get_edas_readings_by_device,
    get_latest_edas_reading,
    update_edas_reading,
)
from app.db.mongodb import get_db
from app.ml.edas.edas_inference import predict
from app.models.edas_models import EDASSensorData, EDASSensorDataUpdate
from app.utils.response_builder import success_response

router = APIRouter()
logger = logging.getLogger(__name__)




@router.post("/predict", summary="Run EDAS prediction for disease detection")
async def edas_predict(payload: dict) -> dict:

    return predict(payload)



@router.post(
    "/sensor-data",
    summary="Ingest sensor data from IoT device",
    status_code=201,
    tags=["edas", "iot"],
)
async def create_sensor_data(payload: EDASSensorData, db=Depends(get_db)) -> dict:

    try:
        data = payload.model_dump()
        record_id = await create_edas_reading(db, data)
        return {
            "status": "created",
            "id": record_id,
            "message": "EDAS sensor reading created successfully",
            "data": {
                "temperature_difference": data.get("temperature_difference"),
            },
        }
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to create EDAS sensor reading",
            extra={"device_id": payload.device_id},
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to create EDAS sensor reading due to internal error",
        )


@router.get(
    "/sensor-data",
    summary="Get all EDAS sensor readings",
    tags=["edas"],
)
async def get_all_sensor_data(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    device_id: str | None = Query(None, description="Filter by device ID"),
    db=Depends(get_db),
) -> dict:

    try:
        if device_id:
            # Filter by specific device
            readings = await get_edas_readings_by_device(
                db, device_id=device_id, skip=skip, limit=limit
            )
        else:
            # Get all readings
            readings = await get_all_edas_readings(db, skip=skip, limit=limit)
        
        return {
            "status": "ok",
            "count": len(readings),
            "skip": skip,
            "limit": limit,
            "data": readings,
        }
    except Exception:  # noqa: BLE001
        logger.exception("Failed to fetch EDAS sensor readings")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch EDAS sensor readings",
        )


@router.get(
    "/sensor-data/latest",
    summary="Get the latest EDAS sensor reading",
    tags=["edas"],
)
async def get_latest_sensor_data(
    device_id: str | None = Query(None, description="Filter by device ID"),
    db=Depends(get_db),
) -> dict:

    try:
        reading = await get_latest_edas_reading(db, device_id=device_id)
        if not reading:
            raise HTTPException(
                status_code=404,
                detail="No EDAS sensor readings found",
            )
        return success_response(message="ok", data=reading)
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        logger.exception("Failed to fetch latest EDAS sensor reading")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch latest EDAS sensor reading",
        )


@router.get(
    "/sensor-data/{reading_id}",
    summary="Get EDAS sensor reading by ID",
    tags=["edas"],
)
async def get_sensor_data_by_id(reading_id: str, db=Depends(get_db)) -> dict:

    try:
        reading = await get_edas_reading_by_id(db, reading_id)
        if not reading:
            raise HTTPException(
                status_code=404,
                detail=f"EDAS sensor reading with id '{reading_id}' not found",
            )
        return {"status": "ok", "data": reading}
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to fetch EDAS sensor reading",
            extra={"id": reading_id},
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch EDAS sensor reading",
        )


@router.put(
    "/sensor-data/{reading_id}",
    summary="Update EDAS sensor reading",
    tags=["edas"],
)
async def update_sensor_data(
    reading_id: str, data: EDASSensorDataUpdate, db=Depends(get_db)
) -> dict:

    try:
        # Check if reading exists first
        existing = await get_edas_reading_by_id(db, reading_id)
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"EDAS sensor reading with id '{reading_id}' not found",
            )

        update_data = data.model_dump(exclude_unset=True)
        updated = await update_edas_reading(db, reading_id, update_data)
        return {
            "status": "updated",
            "message": "EDAS sensor reading updated successfully",
            "data": updated,
        }
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to update EDAS sensor reading",
            extra={"id": reading_id},
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to update EDAS sensor reading",
        )


@router.delete(
    "/sensor-data/{reading_id}",
    summary="Delete EDAS sensor reading",
    tags=["edas"],
)
async def delete_sensor_data(reading_id: str, db=Depends(get_db)) -> dict:

    try:
        deleted = await delete_edas_reading(db, reading_id)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"EDAS sensor reading with id '{reading_id}' not found",
            )
        return {
            "status": "deleted",
            "message": f"EDAS sensor reading '{reading_id}' deleted successfully",
        }
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to delete EDAS sensor reading",
            extra={"id": reading_id},
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to delete EDAS sensor reading",
        )
