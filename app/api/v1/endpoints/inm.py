"""Endpoints for INM model interactions and sensor data CRUD."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.collections.inm_growth_stage import get_growth_stage_state
from app.db.collections.inm_predictions import create_inm_prediction
from app.db.collections.inm_readings import (
    create_inm_reading,
    delete_inm_reading,
    get_all_inm_readings,
    get_inm_reading_by_id,
    update_inm_reading,
)
from app.db.mongodb import get_db
from app.ml.inm.inm_inference import predict, predict_ec_24h
from app.models.inm_models import (
    GrowthStageUpdateRequest,
    INMSensorData,
    INMSensorDataUpdate,
)
from app.services.inm_growth_stage_service import get_current_growth_stage, set_current_growth_stage
from app.services.inm_service import generate_inm_recommendation

router = APIRouter()


# -----------------------------------------------------------------------------
# Status Endpoint (Random Forest ML Model)
# -----------------------------------------------------------------------------


@router.get("/status", summary="Get INM status with EC prediction and recommendations")
async def get_inm_status(db=Depends(get_db)) -> dict:
    """Get current INM status including EC values and fertilizer recommendations.
    
    Uses Random Forest ML model for EC prediction.
    
    Returns:
        - current_ec: Current EC value from latest sensor reading
        - predicted_ec_24h: Predicted EC value for 24 hours ahead (RF model)
        - ec_status: Status label (optimal, low, high, critical)
        - ec_action: Recommended action for EC management
        - ph_action: Recommended action for pH management
        - npk_recommendation: NPK fertilizer recommendation
    """
    growth_stage = await get_current_growth_stage(db)

    # Get the latest sensor reading
    readings = await get_all_inm_readings(db, skip=0, limit=1)
    
    if not readings:
        return {
            "status": "ok",
            "data": {
                "current_ec": 0.0,
                "predicted_ec_24h": 0.0,
                "ec_status": "unknown",
                "ec_action": "No sensor data available. Please ensure sensors are connected.",
                "ph_action": "No pH data available.",
                "npk_recommendation": "Unable to provide NPK recommendation without sensor data.",
                "growth_stage_used": growth_stage.value,
            }
        }
    
    latest = readings[0]
    current_ec = float(latest.get("ec", 0.0))
    current_ph = float(latest.get("ph", 7.0))
    current_n = float(latest.get("N", 0.0))
    current_p = float(latest.get("P", 0.0))
    current_k = float(latest.get("K", 0.0))
    soil_temp = float(latest.get("soil_temp", 25.0))
    soil_moisture = float(latest.get("soil_moisture", 0.0))
    air_temp = float(latest.get("air_temp", 25.0))
    air_hum = float(latest.get("air_hum", 50.0))
    
    # Random Forest EC prediction (24h ahead)
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
    # Keep response stable: if model isn't available, fall back to current_ec
    if predicted_ec_24h is None:
        predicted_ec_24h = current_ec
    
    # Generate status and recommendations
    recommendation = generate_inm_recommendation(
        current_ec=current_ec,
        predicted_ec=predicted_ec_24h,
        ph=current_ph,
        nitrogen=current_n,
        phosphorus=current_p,
        potassium=current_k,
        growth_stage=growth_stage,
    )

    # Persist the computed status output for history/audit
    await create_inm_prediction(
        db,
        {
            "reading_id": latest.get("_id"),
            "device_id": latest.get("device_id"),
            "reading_timestamp": latest.get("timestamp"),
            "current_ec": current_ec,
            "predicted_ec_24h": float(predicted_ec_24h),
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
            "current_ec": round(current_ec, 2),
            "predicted_ec_24h": round(predicted_ec_24h, 2),
            "ec_status": recommendation.ec_status,
            "ec_action": recommendation.ec_action,
            "ph_action": recommendation.ph_action,
            # Keep old response key for compatibility
            "npk_recommendation": recommendation.npk_action,
            "growth_stage_used": growth_stage.value,
        }
    }


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
async def create_sensor_data(payload: INMSensorData, db=Depends(get_db)) -> dict:
    """Create a new INM sensor reading from ESP32 full sensor payload.
    
    Accepts: device_id, N, P, K, ec, ph, soil_temp, soil_moisture, air_temp, air_hum
    Timestamp is set by the backend automatically.
    """
    data = payload.model_dump()
    record_id = await create_inm_reading(db, data)
    return {
        "status": "created",
        "id": record_id,
        "message": "INM sensor reading created successfully",
    }


# -----------------------------------------------------------------------------
# Persistent Growth Stage Endpoint
# -----------------------------------------------------------------------------


@router.post("/growth-stage", summary="Set the persistent INM growth stage")
async def set_growth_stage(payload: GrowthStageUpdateRequest, db=Depends(get_db)) -> dict:
    """Persist the current growth stage context (singleton state).

    Overwrites the previous stage and updates updated_at.
    """
    doc = await set_current_growth_stage(db, payload.growth_stage)
    return {
        "status": "ok",
        "message": "Growth stage updated successfully",
        "data": {
            "current_growth_stage": doc.get("current_growth_stage"),
            "updated_at": doc.get("updated_at"),
        },
    }


@router.get("/growth-stage", summary="Get the persistent INM growth stage")
async def get_growth_stage(db=Depends(get_db)) -> dict:
    """Return the current growth stage context (singleton state).

    Defaults to vegetative if no stage has been set.
    """
    stage = await get_current_growth_stage(db)
    state_doc = await get_growth_stage_state(db)
    return {
        "status": "ok",
        "data": {
            "current_growth_stage": stage.value,
            "updated_at": (state_doc or {}).get("updated_at"),
        },
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

