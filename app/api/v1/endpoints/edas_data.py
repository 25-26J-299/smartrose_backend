"""EDAS data endpoints matching frontend expectations.

This module provides endpoints for the disease detection card and other frontend components.
Routes are structured to match the frontend API calls: /api/v1/edas-data/

Read endpoints require a valid JWT and are scoped to the authenticated user. Optional
``greenhouseId`` (greenhouse / location id) or ``device_id`` further narrow results
after ownership checks. IoT POST ingest remains open for devices.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user
from app.db.collections import devices as device_repo
from app.db.collections import locations as locations_repo
from app.db.collections.edas_sensor_data import (
    get_edas_reading_by_id,
    get_edas_readings_by_device,
    get_edas_readings_by_location,
    get_edas_readings_by_user,
    get_latest_edas_reading,
)
from app.db.mongodb import get_db
from app.models.edas_models import EDASSensorData
from app.services.edas_service import ingest_edas_sensor_reading
from app.utils.response_builder import success_response

router = APIRouter()
logger = logging.getLogger(__name__)


async def _verify_edas_device_ownership(
    db: AsyncIOMotorDatabase,
    device_id: str,
    current_user: dict,
) -> dict:
    dev = await device_repo.get_device_by_serial(db, device_id)
    if not dev:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found.",
        )
    if str(dev.get("type", "")).upper() != "EDAS":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Device '{device_id}' is not an EDAS device.",
        )
    if dev.get("user_id") != current_user["_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this device.",
        )
    return dev


async def _verify_location_ownership(
    db: AsyncIOMotorDatabase,
    location_id: str,
    current_user: dict,
) -> dict:
    loc = await locations_repo.get_location_by_id(db, location_id)
    if not loc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Greenhouse / location not found.",
        )
    if loc.get("user_id") != current_user["_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this location.",
        )
    return loc


@router.get(
    "/",
    summary="List EDAS sensor data with pagination",
    response_model=dict,
    tags=["edas-data"],
)
async def list_edas_data(
    limit: int = Query(120, ge=1, le=2000, description="Maximum records to return"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    device_id: str | None = Query(None, description="Filter by EDAS device serial"),
    location_id: str | None = Query(
        None,
        alias="greenhouseId",
        description="Filter by greenhouse (location) ID",
    ),
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Return EDAS sensor readings for the current user.

    - If ``device_id`` is set: that device must belong to the user.
    - Else if ``greenhouseId`` is set: that location must belong to the user.
    - Else: all readings for the user's EDAS devices (by stored ``user_id``).
    """
    try:
        uid = str(current_user["_id"])
        if device_id:
            await _verify_edas_device_ownership(db, device_id, current_user)
            readings = await get_edas_readings_by_device(
                db, device_id=device_id, skip=skip, limit=limit
            )
        elif location_id:
            await _verify_location_ownership(db, location_id, current_user)
            readings = await get_edas_readings_by_location(
                db, location_id=location_id, skip=skip, limit=limit
            )
        else:
            readings = await get_edas_readings_by_user(
                db, user_id=uid, skip=skip, limit=limit
            )

        return success_response(
            message="EDAS sensor data retrieved successfully",
            data={"items": readings, "count": len(readings)},
        )
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        logger.exception("Failed to fetch EDAS sensor data list")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch EDAS sensor data",
        )


def _rule_based_prediction_payload(latest_reading: dict) -> dict:
    plant_temp = latest_reading.get("plant_temperature", 0)
    air_temp = latest_reading.get("air_temperature", 0)
    humidity = latest_reading.get("humidity", 0)
    temp_diff = latest_reading.get("temperature_difference", 0)
    is_day = latest_reading.get("is_day", True)
    time_period = latest_reading.get("time_period", "unknown")

    risk_level = "low"
    risk_score = 0
    recommendations = []
    alerts = []

    if not is_day and humidity > 75:
        risk_level = "high"
        risk_score = 85
        alerts.append("High fungal disease risk detected (nighttime + high humidity)")
        recommendations.append("Consider improving ventilation overnight")
        recommendations.append("Monitor for early signs of powdery mildew or botrytis")
    elif abs(temp_diff) > 3:
        if temp_diff > 3:
            risk_level = "medium"
            risk_score = 65
            alerts.append(
                "Plant temperature significantly higher than air (possible heat stress)"
            )
            recommendations.append("Check irrigation system and water availability")
        else:
            risk_level = "medium"
            risk_score = 60
            alerts.append("Plant temperature lower than expected (check plant health)")
            recommendations.append("Inspect plants for disease symptoms")
    elif is_day and plant_temp > 30 and humidity > 70:
        risk_level = "medium"
        risk_score = 70
        alerts.append("High temperature and humidity during day (stress conditions)")
        recommendations.append("Increase ventilation to reduce humidity")
        recommendations.append("Ensure adequate shading during peak hours")
    else:
        risk_level = "low"
        risk_score = 25
        alerts.append("Environmental conditions within normal range")
        recommendations.append("Continue current monitoring schedule")

    return {
        "sensor_data": latest_reading,
        "reading": latest_reading,
        "prediction": {
            "disease_risk_level": risk_level,
            "risk_score": risk_score,
            "confidence": 0.85,
            "alerts": alerts,
            "recommendations": recommendations,
            "analysis_time": latest_reading.get("timestamp"),
            "time_context": {
                "is_day": is_day,
                "time_period": time_period,
                "hour": latest_reading.get("hour"),
            },
        },
        "key_metrics": {
            "plant_temperature": plant_temp,
            "air_temperature": air_temp,
            "humidity": humidity,
            "temperature_difference": temp_diff,
        },
    }


async def _resolve_latest_reading_for_user(
    db: AsyncIOMotorDatabase,
    current_user: dict,
    device_id: str | None,
    location_id: str | None,
) -> dict | None:
    uid = str(current_user["_id"])
    if device_id:
        await _verify_edas_device_ownership(db, device_id, current_user)
        return await get_latest_edas_reading(db, device_id=device_id)
    if location_id:
        await _verify_location_ownership(db, location_id, current_user)
        return await get_latest_edas_reading(db, location_id=location_id)
    return await get_latest_edas_reading(db, user_id=uid)


@router.get(
    "/latest-sensor-data",
    summary="Get latest EDAS sensor row for the current user",
    response_model=dict,
    tags=["edas-data"],
)
async def get_latest_sensor_data(
    device_id: str | None = Query(None, description="Filter by EDAS device serial"),
    location_id: str | None = Query(
        None,
        alias="greenhouseId",
        description="Filter by greenhouse (location) ID",
    ),
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    try:
        latest_reading = await _resolve_latest_reading_for_user(
            db, current_user, device_id, location_id
        )
        if not latest_reading:
            raise HTTPException(
                status_code=404,
                detail="No EDAS sensor data found for your account.",
            )
        return success_response(
            message="Latest EDAS sensor data retrieved successfully",
            data=latest_reading,
        )
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        logger.exception("Failed to fetch latest EDAS sensor data")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch latest EDAS sensor data",
        )


@router.get(
    "/latest-with-prediction",
    summary="Get latest EDAS sensor data with disease prediction",
    response_model=dict,
    tags=["edas-data", "disease-detection"],
)
async def get_latest_with_prediction(
    device_id: str | None = Query(None, description="Filter by EDAS device serial"),
    location_id: str | None = Query(
        None,
        alias="greenhouseId",
        description="Filter by greenhouse (location) ID",
    ),
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Latest sensor row for the authenticated user, plus rule-based risk text."""
    try:
        latest_reading = await _resolve_latest_reading_for_user(
            db, current_user, device_id, location_id
        )
        if not latest_reading:
            raise HTTPException(
                status_code=404,
                detail="No EDAS sensor data found for your account.",
            )

        response_data = _rule_based_prediction_payload(latest_reading)

        logger.info(
            "Disease prediction generated for latest reading",
            extra={
                "device_id": latest_reading.get("device_id"),
                "risk_level": response_data["prediction"]["disease_risk_level"],
                "risk_score": response_data["prediction"]["risk_score"],
            },
        )

        return success_response(
            message="Latest EDAS data with disease prediction retrieved successfully",
            data=response_data,
        )

    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        logger.exception("Failed to generate disease prediction")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve EDAS data with prediction",
        )


@router.post(
    "/",
    summary="Ingest EDAS sensor data from IoT device",
    status_code=201,
    tags=["edas-data", "iot"],
)
async def create_edas_data(
    payload: EDASSensorData,
    db=Depends(get_db),
) -> dict:
    """Ingest EDAS sensor data from ESP32 device.

    This endpoint receives data from IoT devices and processes it:
    - Validates sensor values
    - Captures Sri Lankan local time
    - Calculates temperature difference
    - Calculates ML time features (hour, is_day, time_period)
    - Stores as UTC in MongoDB
    - **Broadcasts to WebSocket clients for instant frontend updates!**

    No timestamp needed from Arduino - backend handles everything!
    """
    try:
        result = await ingest_edas_sensor_reading(payload, db)
        from app.api.v1.endpoints.edas_websocket import broadcast_new_sensor_data

        inserted_id = None
        if isinstance(result, dict):
            inner = result.get("data") or {}
            inserted_id = inner.get("id")

        if inserted_id:
            reading = await get_edas_reading_by_id(db, str(inserted_id))
            if reading:
                await broadcast_new_sensor_data(reading)

        return result
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to ingest EDAS sensor data",
            extra={"device_id": payload.device_id},
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to ingest EDAS sensor data",
        )
