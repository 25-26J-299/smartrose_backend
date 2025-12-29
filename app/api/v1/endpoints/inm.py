"""Endpoints for INM model interactions and sensor data CRUD."""

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
            }
        }
    
    latest = readings[0]
    current_ec = float(latest.get("ec", 0.0))
    current_ph = float(latest.get("ph", 7.0))
    current_n = float(latest.get("N", 0.0))
    current_p = float(latest.get("P", 0.0))
    current_k = float(latest.get("K", 0.0))
    
    # Random Forest prediction simulation
    # TODO: Replace with actual RF model prediction
    predicted_ec_24h = _predict_ec_rf(current_ec, current_n, current_p, current_k)
    
    # Generate status and recommendations
    ec_status, ec_action = _get_ec_status_and_action(current_ec)
    ph_action = _get_ph_action(current_ph)
    npk_recommendation = _get_npk_recommendation(current_n, current_p, current_k, current_ec)
    
    return {
        "status": "ok",
        "data": {
            "current_ec": round(current_ec, 2),
            "predicted_ec_24h": round(predicted_ec_24h, 2),
            "ec_status": ec_status,
            "ec_action": ec_action,
            "ph_action": ph_action,
            "npk_recommendation": npk_recommendation,
        }
    }


def _predict_ec_rf(ec: float, n: float, p: float, k: float) -> float:
    """Simulate Random Forest EC prediction for 24h ahead.
    
    TODO: Replace with actual trained RF model inference.
    """
    # Simple prediction logic (placeholder for RF model)
    # Based on current nutrient levels and EC trend
    base_change = 0.02  # Base daily change
    nutrient_factor = (n + p + k) / 3000  # Normalize nutrient impact
    predicted = ec + (base_change * ec) + nutrient_factor
    return max(0.1, min(predicted, 10.0))  # Clamp between 0.1 and 10.0


def _get_ec_status_and_action(ec: float) -> tuple[str, str]:
    """Get EC status label and recommended action."""
    if ec < 0.5:
        return "critical_low", "Critical: EC too low. Immediately increase fertilizer concentration by 50%. Monitor closely for nutrient deficiency symptoms."
    elif ec < 1.0:
        return "low", "Low EC detected. Increase fertilizer application by 25%. Consider adding balanced NPK solution."
    elif ec <= 2.0:
        return "optimal", "EC levels are optimal for rose cultivation. Maintain current fertilization schedule and continue monitoring."
    elif ec <= 3.0:
        return "high", "High EC detected. Reduce fertilizer by 25% and increase irrigation frequency to flush excess salts."
    else:
        return "critical_high", "Critical: EC dangerously high! Stop fertilization immediately. Flush growing medium with clean water for 24 hours."


def _get_ph_action(ph: float) -> str:
    """Get pH management recommendation."""
    if ph < 5.5:
        return "pH too acidic. Add lime or dolomite to raise pH. Target range: 6.0-6.5 for optimal nutrient uptake."
    elif ph < 6.0:
        return "pH slightly low. Consider adding small amounts of calcium carbonate to gradually raise pH."
    elif ph <= 6.5:
        return "pH is optimal for rose cultivation. Maintain current management practices."
    elif ph <= 7.0:
        return "pH slightly high. Add sulfur or acidifying fertilizer to lower pH gradually."
    else:
        return "pH too alkaline. Apply elemental sulfur or iron sulfate to lower pH. High pH can cause iron and manganese deficiency."


def _get_npk_recommendation(n: float, p: float, k: float, ec: float) -> str:
    """Generate NPK fertilizer recommendation based on nutrient levels."""
    recommendations = []
    
    # Nitrogen recommendation
    if n < 50:
        recommendations.append("N: Low nitrogen. Apply urea or ammonium nitrate (20-30 kg/ha).")
    elif n < 100:
        recommendations.append("N: Nitrogen adequate. Maintain current application rate.")
    else:
        recommendations.append("N: Nitrogen sufficient. Reduce nitrogen application to prevent excess vegetative growth.")
    
    # Phosphorus recommendation
    if p < 30:
        recommendations.append("P: Low phosphorus. Apply superphosphate or DAP (15-20 kg/ha) for root development and flowering.")
    elif p < 60:
        recommendations.append("P: Phosphorus adequate. Continue current phosphorus regime.")
    else:
        recommendations.append("P: Phosphorus sufficient. No additional P needed.")
    
    # Potassium recommendation
    if k < 100:
        recommendations.append("K: Low potassium. Apply potassium sulfate or MOP (25-30 kg/ha) for flower quality and disease resistance.")
    elif k < 200:
        recommendations.append("K: Potassium adequate. Maintain current potassium levels.")
    else:
        recommendations.append("K: Potassium sufficient. Monitor for potential imbalance with other nutrients.")
    
    return " | ".join(recommendations)


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

