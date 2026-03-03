"""Endpoints for INM model interactions and sensor data CRUD.

Multi-user / multi-greenhouse design:
- POST /sensor-data  : No JWT (ESP32 posts directly). Device must be registered.
                       Reading is enriched with location_id + user_id from devices table.
- GET  /status       : JWT required. Scoped to device_id. Ownership enforced.
- GET  /sensor-data  : JWT required. Scoped to device_id. Ownership enforced.
- GET/POST /growth-stage : JWT required. Scoped to device_id. Ownership enforced.
- GET  /health-check : Open (dev/admin use).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user
from app.db.collections import devices as device_repo
from app.db.collections.inm_growth_stage import get_growth_stage_state
from app.db.collections.inm_predictions import create_inm_prediction
from app.db.collections.inm_readings import (
    create_inm_reading,
    delete_inm_reading,
    get_all_inm_readings,
    get_inm_reading_by_id,
    get_inm_readings_by_device,
    get_latest_inm_reading_by_device,
    update_inm_reading,
)
from app.db.mongodb import get_db
from app.ml.inm.inm_inference import is_model_available, predict, predict_ec_24h
from app.models.inm_models import (
    GrowthStageUpdateRequest,
    INMSensorData,
    INMSensorDataUpdate,
)
from app.services.inm_growth_stage_service import (
    get_current_growth_stage,
    set_current_growth_stage,
)
from app.services.inm_service import generate_inm_recommendation

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ownership helper
# ---------------------------------------------------------------------------

async def _verify_device_ownership(
    db: AsyncIOMotorDatabase,
    device_id: str,
    current_user: dict,
) -> dict:
    """Look up the device and verify it belongs to the current user.

    Returns the device document on success.
    Raises 404 if device not found, 403 if it belongs to another user.
    """
    device = await device_repo.get_device_by_serial(db, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found. Please check the device ID.",
        )
    if device.get("user_id") != current_user["_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this device.",
        )
    return device


# ---------------------------------------------------------------------------
# INM Sensor Data Ingest (ESP32 → backend, no JWT needed)
# ---------------------------------------------------------------------------

@router.post("/sensor-data", summary="Create INM sensor reading (ESP32)", status_code=201)
async def create_sensor_data(payload: INMSensorData, db=Depends(get_db)) -> dict:
    """Ingest an INM sensor reading from ESP32.

    - Device must be registered in the devices collection.
    - Reading is enriched with location_id and user_id from the device record
      so per-greenhouse / per-user queries are accurate even if the device is
      later reassigned.
    """
    device = await device_repo.get_device_by_serial(db, payload.device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Device '{payload.device_id}' is not registered. "
                "Ask your admin to register and assign this device first."
            ),
        )

    data = payload.model_dump()
    # Enrich with ownership context so readings can be queried by greenhouse/user
    data["location_id"] = device.get("location_id", "")
    data["user_id"] = device.get("user_id", "")

    record_id = await create_inm_reading(db, data)
    logger.info(
        "INM sensor reading created",
        extra={
            "id": record_id,
            "device_id": data.get("device_id"),
            "location_id": data.get("location_id"),
            "user_id": data.get("user_id"),
        },
    )

    # Background ML log on ingest (does not affect response)
    growth_stage = await get_current_growth_stage(db, payload.device_id)
    if is_model_available():
        predicted = predict_ec_24h(
            soil_temp=float(data.get("soil_temp", 25.0)),
            soil_moisture=float(data.get("soil_moisture", 0.0)),
            ec=float(data.get("ec", 0.0)),
            ph=float(data.get("ph", 7.0)),
            nitrogen=float(data.get("N", 0.0)),
            phosphorus=float(data.get("P", 0.0)),
            potassium=float(data.get("K", 0.0)),
            air_temp=float(data.get("air_temp", 25.0)),
            air_humidity=float(data.get("air_hum", 50.0)),
            growth_stage=growth_stage.value,
        )
        logger.info(
            "INM ML prediction executed on ingest",
            extra={"record_id": record_id, "predicted_ec_24h": predicted},
        )

    return {
        "status": "created",
        "id": record_id,
        "message": "INM sensor reading created successfully",
    }


# ---------------------------------------------------------------------------
# Status (device-scoped, JWT required)
# ---------------------------------------------------------------------------

@router.get("/status", summary="Get INM status for a specific device")
async def get_inm_status(
    device_id: str = Query(..., description="Device ID to get status for"),
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Get INM status (EC prediction + recommendations) for the given device.

    Requires JWT. The device must belong to the logged-in user.
    """
    await _verify_device_ownership(db, device_id, current_user)

    growth_stage = await get_current_growth_stage(db, device_id)
    latest = await get_latest_inm_reading_by_device(db, device_id)

    if not latest:
        return {
            "status": "ok",
            "data": {
                "device_id": device_id,
                "has_sensor_data": False,
                "current_ec": 0.0,
                "predicted_ec_24h": None,
                "ec_status": "unknown",
                "ec_action": "No sensor data available. Please ensure the device is connected.",
                "ph_action": "No pH data available.",
                "npk_recommendation": "Unable to provide NPK recommendation without sensor data.",
                "growth_stage_used": growth_stage.value,
            },
        }

    current_ec = float(latest.get("ec", 0.0))
    current_ph = float(latest.get("ph", 7.0))
    current_n = float(latest.get("N", 0.0))
    current_p = float(latest.get("P", 0.0))
    current_k = float(latest.get("K", 0.0))
    soil_temp = float(latest.get("soil_temp", 25.0))
    soil_moisture = float(latest.get("soil_moisture", 0.0))
    air_temp = float(latest.get("air_temp", 25.0))
    air_hum = float(latest.get("air_hum", 50.0))

    predicted_ec_24h = None
    if is_model_available():
        predicted_ec_24h = predict_ec_24h(
            soil_temp=soil_temp,
            soil_moisture=soil_moisture,
            ec=current_ec,
            ph=current_ph,
            nitrogen=current_n,
            phosphorus=current_p,
            potassium=current_k,
            air_temp=air_temp,
            air_humidity=air_hum,
            growth_stage=growth_stage.value,
        )

    recommendation = generate_inm_recommendation(
        current_ec=current_ec,
        predicted_ec=predicted_ec_24h,
        ph=current_ph,
        nitrogen=current_n,
        phosphorus=current_p,
        potassium=current_k,
        growth_stage=growth_stage,
    )

    await create_inm_prediction(
        db,
        {
            "reading_id": latest.get("_id"),
            "device_id": device_id,
            "location_id": latest.get("location_id", ""),
            "user_id": latest.get("user_id", ""),
            "reading_timestamp": latest.get("timestamp"),
            "current_ec": current_ec,
            "predicted_ec_24h": float(predicted_ec_24h) if predicted_ec_24h is not None else None,
            "ec_status": recommendation.ec_status,
            "ec_action": recommendation.ec_action,
            "ph_action": recommendation.ph_action,
            "npk_recommendation": recommendation.npk_action,
            "growth_stage_used": growth_stage.value,
        },
    )

    return {
        "status": "ok",
        "data": {
            "device_id": device_id,
            "has_sensor_data": True,
            "current_ec": round(current_ec, 2),
            "predicted_ec_24h": round(predicted_ec_24h, 2) if predicted_ec_24h is not None else None,
            "ec_status": recommendation.ec_status,
            "ec_action": recommendation.ec_action,
            "ph_action": recommendation.ph_action,
            "npk_recommendation": recommendation.npk_action,
            "growth_stage_used": growth_stage.value,
        },
    }


# ---------------------------------------------------------------------------
# Sensor Data Read (device-scoped, JWT required)
# ---------------------------------------------------------------------------

@router.get("/sensor-data", summary="Get INM sensor readings for a device")
async def get_sensor_data(
    device_id: str = Query(..., description="Device ID to fetch readings for"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Return paginated INM sensor readings for a specific device.

    Requires JWT. The device must belong to the logged-in user.
    """
    await _verify_device_ownership(db, device_id, current_user)
    readings = await get_inm_readings_by_device(db, device_id, skip=skip, limit=limit)
    return {
        "status": "ok",
        "device_id": device_id,
        "count": len(readings),
        "skip": skip,
        "limit": limit,
        "data": readings,
    }


@router.get("/sensor-data/{reading_id}", summary="Get INM sensor reading by ID")
async def get_sensor_data_by_id(
    reading_id: str,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Return a single INM sensor reading by its MongoDB ID.

    Requires JWT. Ownership is verified via the reading's user_id field.
    """
    reading = await get_inm_reading_by_id(db, reading_id)
    if not reading:
        raise HTTPException(status_code=404, detail=f"Reading '{reading_id}' not found.")
    if reading.get("user_id") and reading["user_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="You do not have access to this reading.")
    return {"status": "ok", "data": reading}


@router.put("/sensor-data/{reading_id}", summary="Update INM sensor reading")
async def update_sensor_data(
    reading_id: str,
    data: INMSensorDataUpdate,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Update an INM sensor reading. Requires JWT and ownership."""
    existing = await get_inm_reading_by_id(db, reading_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Reading '{reading_id}' not found.")
    if existing.get("user_id") and existing["user_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="You do not have access to this reading.")
    update_data = data.model_dump(exclude_unset=True)
    updated = await update_inm_reading(db, reading_id, update_data)
    return {"status": "updated", "message": "INM sensor reading updated successfully", "data": updated}


@router.delete("/sensor-data/{reading_id}", summary="Delete INM sensor reading")
async def delete_sensor_data(
    reading_id: str,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Delete an INM sensor reading. Requires JWT and ownership."""
    existing = await get_inm_reading_by_id(db, reading_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Reading '{reading_id}' not found.")
    if existing.get("user_id") and existing["user_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="You do not have access to this reading.")
    deleted = await delete_inm_reading(db, reading_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Reading '{reading_id}' not found.")
    return {"status": "deleted", "message": f"INM sensor reading '{reading_id}' deleted successfully"}


# ---------------------------------------------------------------------------
# Growth Stage (device-scoped, JWT required)
# ---------------------------------------------------------------------------

@router.post("/growth-stage", summary="Set the INM growth stage for a device")
async def set_growth_stage(
    payload: GrowthStageUpdateRequest,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Persist the growth stage for a specific device.

    Requires JWT. The device must belong to the logged-in user.
    """
    await _verify_device_ownership(db, payload.device_id, current_user)
    doc = await set_current_growth_stage(db, payload.growth_stage, payload.device_id)
    return {
        "status": "ok",
        "message": "Growth stage updated successfully",
        "data": {
            "device_id": payload.device_id,
            "current_growth_stage": doc.get("current_growth_stage"),
            "updated_at": doc.get("updated_at"),
        },
    }


@router.get("/growth-stage", summary="Get the INM growth stage for a device")
async def get_growth_stage(
    device_id: str = Query(..., description="Device ID to get growth stage for"),
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Return the current growth stage for a specific device.

    Requires JWT. The device must belong to the logged-in user.
    """
    await _verify_device_ownership(db, device_id, current_user)
    stage = await get_current_growth_stage(db, device_id)
    state_doc = await get_growth_stage_state(db, device_id)
    return {
        "status": "ok",
        "data": {
            "device_id": device_id,
            "current_growth_stage": stage.value,
            "updated_at": (state_doc or {}).get("updated_at"),
        },
    }


# ---------------------------------------------------------------------------
# Stub predict (unchanged)
# ---------------------------------------------------------------------------

@router.post("/predict", summary="Run INM prediction (stub)")
async def inm_predict(payload: dict) -> dict:
    return predict(payload)


# ---------------------------------------------------------------------------
# Health check (open, dev/admin use)
# ---------------------------------------------------------------------------

@router.get("/health-check", summary="DEV ONLY: INM internal health check")
async def inm_health_check(db=Depends(get_db)) -> dict:
    """Lightweight verification endpoint for the INM subsystem."""
    ml_loaded = False
    try:
        ml_loaded = is_model_available()
    except Exception:  # noqa: BLE001
        ml_loaded = False

    sensor_count = await db["inm_sensor_data"].count_documents({})
    last_sensor = (
        await db["inm_sensor_data"]
        .find({}, {"timestamp": 1})
        .sort("timestamp", -1)
        .limit(1)
        .to_list(length=1)
    )
    action_count = await db["inm_actions"].count_documents({})

    return {
        "ml_model_loaded": bool(ml_loaded),
        "last_sensor_timestamp": last_sensor[0].get("timestamp") if last_sensor else None,
        "total_sensor_records": sensor_count,
        "total_action_records": action_count,
    }

