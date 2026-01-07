"""EDAS data endpoints matching frontend expectations.

This module provides endpoints for the disease detection card and other frontend components.
Routes are structured to match the frontend API calls: /api/v1/edas-data/
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections.edas_sensor_data import (
    get_all_edas_readings,
    get_latest_edas_reading,
)
from app.db.mongodb import get_db
from app.models.edas_models import EDASSensorData
from app.services.edas_service import ingest_edas_sensor_reading
from app.utils.response_builder import success_response

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/",
    summary="List EDAS sensor data with pagination",
    response_model=dict,
    tags=["edas-data"],
)
async def list_edas_data(
    limit: int = Query(120, ge=1, le=2000, description="Maximum records to return"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    device_id: str | None = Query(None, description="Filter by device ID"),
    db=Depends(get_db),
) -> dict:
    """Return EDAS sensor readings with pagination.
    
    This endpoint is used by the frontend dashboard to display sensor data history.
    Returns data in descending order (most recent first).
    
    Query Parameters:
        - limit: Maximum number of records (default: 120)
        - skip: Pagination offset (default: 0)
        - device_id: Optional filter by specific device
        
    Returns:
        Standard response with sensor data items including:
        - timestamp (converted to Sri Lankan local time)
        - sensor values (plant_temperature, air_temperature, humidity)
        - calculated fields (temperature_difference)
        - ML time features (hour, is_day, time_period)
    """
    try:
        if device_id:
            from app.db.collections.edas_sensor_data import get_edas_readings_by_device
            readings = await get_edas_readings_by_device(
                db, device_id=device_id, skip=skip, limit=limit
            )
        else:
            readings = await get_all_edas_readings(db, skip=skip, limit=limit)
        
        return success_response(
            message="EDAS sensor data retrieved successfully",
            data={"items": readings, "count": len(readings)}
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to fetch EDAS sensor data list")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch EDAS sensor data",
        )


@router.get(
    "/latest-with-prediction",
    summary="Get latest EDAS sensor data with disease prediction",
    response_model=dict,
    tags=["edas-data", "disease-detection"],
)
async def get_latest_with_prediction(
    device_id: str | None = Query(None, description="Filter by device ID"),
    db=Depends(get_db),
) -> dict:
    """Get the latest EDAS sensor reading with disease prediction analysis.
    
    This endpoint is specifically designed for the disease detection card in the frontend.
    It returns the most recent sensor data along with ML-based disease risk assessment.
    
    Query Parameters:
        - device_id: Optional filter for specific device/zone
        
    Returns:
        Latest sensor data with:
        - timestamp (Sri Lankan local time)
        - sensor readings (plant_temperature, air_temperature, humidity)
        - temperature_difference (key metric for disease detection)
        - ML time features (hour, is_day, time_period)
        - disease_risk_level (calculated based on patterns)
        - recommendations (actionable insights)
        
    Use Cases:
        - Disease detection dashboard card
        - Real-time monitoring displays
        - Alert system integration
        - Mobile app current status
    """
    try:
        # Get latest sensor reading
        latest_reading = await get_latest_edas_reading(db, device_id=device_id)
        
        if not latest_reading:
            raise HTTPException(
                status_code=404,
                detail="No EDAS sensor data found" + (f" for device {device_id}" if device_id else ""),
            )
        
        # =====================================================================
        # Disease Risk Assessment (Rule-Based for now)
        # =====================================================================
        # TODO: Replace with actual ML model prediction once trained
        
        plant_temp = latest_reading.get("plant_temperature", 0)
        air_temp = latest_reading.get("air_temperature", 0)
        humidity = latest_reading.get("humidity", 0)
        temp_diff = latest_reading.get("temperature_difference", 0)
        is_day = latest_reading.get("is_day", True)
        time_period = latest_reading.get("time_period", "unknown")
        
        # Rule-based disease risk assessment
        risk_level = "low"
        risk_score = 0
        recommendations = []
        alerts = []
        
        # Night + High Humidity = Fungal Risk
        if not is_day and humidity > 75:
            risk_level = "high"
            risk_score = 85
            alerts.append("High fungal disease risk detected (nighttime + high humidity)")
            recommendations.append("Consider improving ventilation overnight")
            recommendations.append("Monitor for early signs of powdery mildew or botrytis")
        
        # Large Temperature Difference = Plant Stress
        elif abs(temp_diff) > 3:
            if temp_diff > 3:
                risk_level = "medium"
                risk_score = 65
                alerts.append("Plant temperature significantly higher than air (possible heat stress)")
                recommendations.append("Check irrigation system and water availability")
            else:
                risk_level = "medium"
                risk_score = 60
                alerts.append("Plant temperature lower than expected (check plant health)")
                recommendations.append("Inspect plants for disease symptoms")
        
        # Day + High Temperature + High Humidity
        elif is_day and plant_temp > 30 and humidity > 70:
            risk_level = "medium"
            risk_score = 70
            alerts.append("High temperature and humidity during day (stress conditions)")
            recommendations.append("Increase ventilation to reduce humidity")
            recommendations.append("Ensure adequate shading during peak hours")
        
        # Normal conditions
        else:
            risk_level = "low"
            risk_score = 25
            alerts.append("Environmental conditions within normal range")
            recommendations.append("Continue current monitoring schedule")
        
        # =====================================================================
        # Build Response
        # =====================================================================
        response_data = {
            "sensor_data": latest_reading,
            "prediction": {
                "disease_risk_level": risk_level,
                "risk_score": risk_score,
                "confidence": 0.85,  # Rule-based confidence
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
        
        logger.info(
            "Disease prediction generated for latest reading",
            extra={
                "device_id": latest_reading.get("device_id"),
                "risk_level": risk_level,
                "risk_score": risk_score,
            },
        )
        
        return success_response(
            message="Latest EDAS data with disease prediction retrieved successfully",
            data=response_data
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
        
        # =====================================================================
        # INSTANT UPDATE: Broadcast to WebSocket clients
        # =====================================================================
        # Get the latest data that was just inserted
        from app.api.v1.endpoints.edas_websocket import broadcast_new_sensor_data
        
        latest = await get_latest_edas_reading(db)
        if latest:
            # Broadcast to all connected WebSocket clients for instant updates!
            await broadcast_new_sensor_data(latest)
            logger.info(
                "Broadcasted new sensor data to WebSocket clients",
                extra={"device_id": payload.device_id}
            )
        
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

