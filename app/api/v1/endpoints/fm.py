"""FastAPI endpoints for Freshness Monitoring (FM) component."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Path, Response

from app.db.mongodb import get_database
from app.models.fm_models import FMPredictionResponse, FMSensorInput
from app.services.fm_service import get_latest, save_reading
from app.services.fm_ml_service import FMMLError, get_ml_prediction
from app.db.collections.fm_predictions import COLLECTION_NAME as FM_PREDICTIONS_COLLECTION

router = APIRouter(prefix="/fm", tags=["FM"])
logger = logging.getLogger(__name__)


def _ml_response_to_prediction(
    ml_response: Dict[str, Any], reading: FMSensorInput
) -> FMPredictionResponse:
    """Convert ML service response to FMPredictionResponse format.
    
    Args:
        ml_response: Dict from ML service with freshness_score, vase_life_hours, status
        reading: Original sensor reading for generating alerts
        
    Returns:
        FMPredictionResponse with alerts generated from sensor readings
    """
    # Generate alerts based on sensor readings (not from ML status)
    alerts = []
    if reading.water_level < 20:
        alerts.append("Low water level detected")
    if reading.gas_value > 100:
        alerts.append("High gas value detected")
    if reading.temperature > 25.0:
        alerts.append("High temperature detected")
    if reading.temperature < 15.0:
        alerts.append("Low temperature detected")
    
    return FMPredictionResponse(
        freshness_score=ml_response["freshness_score"],
        vase_life_hours=ml_response["vase_life_hours"],
        alerts=alerts,
    )


@router.post("/upload", summary="Upload sensor reading from ESP32")
async def upload_sensor_reading(payload: FMSensorInput) -> Dict[str, str]:
    """Upload a sensor reading, call external ML service, and store both in MongoDB.

    Workflow:
    - Save raw sensor data to the `fm_sensor_data` collection.
    - Call the external FM ML microservice for prediction.
    - Save prediction (freshness_score, vase_life_hours, status) to `fm_predictions`.
    """
    try:
        logger.info(
            "Sensor reading upload received from ESP32",
            extra={
                "device_id": payload.device_id,
                "temperature": payload.temperature,
                "humidity": payload.humidity,
                "gas_value": payload.gas_value,
                "water_level": payload.water_level,
                "timestamp": payload.timestamp.isoformat(),
            },
        )

        # 1) Save raw sensor data
        inserted_id = await save_reading(payload)

        logger.info(
            "Sensor reading saved successfully",
            extra={
                "device_id": payload.device_id,
                "inserted_id": inserted_id,
            },
        )

        # 2) Call external ML service for prediction
        try:
            prediction = await get_ml_prediction(payload)
        except FMMLError as exc:
            # Raw data is already stored; surface ML error to caller.
            logger.exception(
                "Failed to get prediction from FM ML service",
                extra={"device_id": payload.device_id, "sensor_id": inserted_id},
            )
            raise HTTPException(
                status_code=502,
                detail=f"Sensor reading saved but prediction failed: {exc}",
            ) from exc

        # 3) Store prediction result in MongoDB
        db = get_database()
        collection = db[FM_PREDICTIONS_COLLECTION]

        prediction_doc = {
            "sensor_id": inserted_id,
            "device_id": payload.device_id,
            "timestamp": payload.timestamp,
            "temperature": payload.temperature,
            "humidity": payload.humidity,
            "gas_value": payload.gas_value,
            "water_level": payload.water_level,
            "freshness_score": prediction.get("freshness_score"),
            "vase_life_hours": prediction.get("vase_life_hours"),
            "status": prediction.get("status"),
        }

        pred_result = await collection.insert_one(prediction_doc)
        prediction_id = str(pred_result.inserted_id)

        logger.info(
            "FM prediction saved successfully",
            extra={
                "device_id": payload.device_id,
                "sensor_id": inserted_id,
                "prediction_id": prediction_id,
            },
        )

        return {
            "message": "saved",
            "id": inserted_id,
            "prediction_id": prediction_id,
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to upload sensor reading with prediction",
            extra={"device_id": payload.device_id},
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to save sensor reading and prediction due to an error",
        ) from exc


@router.get("/latest-debug/{device_id}", summary="Debug: Get all readings for device")
async def get_all_readings_debug(
    device_id: str = Path(..., description="Device ID to retrieve all readings for"),
    limit: int = 10,
) -> Dict:
    """Debug endpoint to see all readings for a device sorted by timestamp."""
    from app.services.fm_service import COLLECTION_NAME
    from app.db.mongodb import get_database
    
    db = get_database()
    collection = db[COLLECTION_NAME]
    
    cursor = collection.find(
        {"device_id": device_id}
    ).sort([("timestamp", -1), ("_id", -1)]).limit(limit)
    
    docs = await cursor.to_list(length=limit)
    
    result = []
    for doc in docs:
        doc["_id"] = str(doc["_id"])
        result.append(doc)
    
    return {"device_id": device_id, "count": len(result), "readings": result}


@router.get("/latest/{device_id}", summary="Get latest sensor reading")
async def get_latest_reading(
    device_id: str = Path(..., description="Device ID to retrieve latest reading for")
) -> Dict:
    """Get the latest sensor reading for a specific device.

    Queries MongoDB for the most recent sensor reading document matching
    the provided device_id, sorted by timestamp descending (latest update first).

    Args:
        device_id: Device identifier to query

    Returns:
        Latest sensor reading document as a dictionary

    Raises:
        HTTPException: If no reading found (404) or database query fails (500)
    """
    try:
        logger.info(
            "Latest reading requested",
            extra={"device_id": device_id},
        )

        reading = await get_latest(device_id)

        if reading is None:
            raise HTTPException(
                status_code=404,
                detail=f"No readings found for device_id: {device_id}",
            )

        return reading
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to retrieve latest reading",
            extra={"device_id": device_id},
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve latest reading due to an error",
        ) from exc


@router.get("/latest-with-prediction/{device_id}", summary="Get latest reading with ML prediction")
async def get_latest_with_prediction(
    response: Response,
    device_id: str = Path(..., description="Device ID to retrieve latest reading and prediction for"),
) -> Dict:
    """Get the latest sensor reading with freshness prediction from ML service only.

    Fetches the most recent sensor reading from the database (sorted by timestamp
    descending) and generates a freshness prediction using the external ML service.
    No heuristic fallback - predictions come exclusively from the ML service.

    Args:
        device_id: Device identifier to query

    Returns:
        Dictionary containing:
            - reading: Latest sensor reading data
            - prediction: Freshness prediction from ML service (freshness_score, vase_life_hours, alerts)

    Raises:
        HTTPException: If no reading found (404) or ML service fails (502)
    """
    try:
        logger.info(
            "Latest reading with prediction requested",
            extra={"device_id": device_id},
        )

        # Get latest reading from database (sorted by timestamp descending)
        reading_doc = await get_latest(device_id)

        if reading_doc is None:
            raise HTTPException(
                status_code=404,
                detail=f"No readings found for device_id: {device_id}",
            )

        # Log the timestamp to verify we're getting the latest
        logger.info(
            "Latest reading retrieved for prediction",
            extra={
                "device_id": device_id,
                "timestamp": str(reading_doc.get("timestamp", "unknown")),
                "document_id": reading_doc.get("_id", "unknown"),
            },
        )

        # Convert database document to FMSensorInput for prediction
        from app.models.fm_models import FMSensorInput
        from datetime import datetime

        # Motor/MongoDB returns datetime objects directly, but handle string conversion if needed
        timestamp = reading_doc["timestamp"]
        if isinstance(timestamp, str):
            # Parse ISO format string if needed
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

        reading = FMSensorInput(
            device_id=reading_doc["device_id"],
            temperature=reading_doc["temperature"],
            humidity=reading_doc["humidity"],
            gas_value=reading_doc["gas_value"],
            water_level=reading_doc["water_level"],
            timestamp=timestamp,
        )

        # Get prediction from ML service only (no fallback)
        try:
            ml_prediction = await get_ml_prediction(reading)
            prediction = _ml_response_to_prediction(ml_prediction, reading)
        except FMMLError as exc:
            logger.exception(
                "ML service error when getting prediction",
                extra={"device_id": device_id},
            )
            raise HTTPException(
                status_code=502,
                detail=f"ML service unavailable: {exc}",
            ) from exc

        # Set cache-control headers to prevent caching
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return {
            "reading": reading_doc,
            "prediction": prediction.model_dump(),
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to retrieve latest reading with prediction",
            extra={"device_id": device_id},
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve latest reading with prediction due to an error",
        ) from exc


@router.post("/predict", summary="Predict freshness from sensor reading using ML service")
async def predict_freshness(payload: FMSensorInput) -> FMPredictionResponse:
    """Generate freshness prediction from sensor reading data using ML service only.

    Accepts FMSensorInput and calls the external ML service to get predictions.
    No heuristic fallback - predictions come exclusively from the ML service.

    Args:
        payload: FMSensorInput model instance with sensor reading data

    Returns:
        FMPredictionResponse containing:
            - freshness_score: Predicted freshness score from ML service
            - vase_life_hours: Predicted vase life in hours from ML service
            - alerts: List of alert messages generated from sensor readings

    Raises:
        HTTPException: If ML service fails (502) or other error occurs (500)
    """
    try:
        logger.info(
            "Freshness prediction requested from ML service",
            extra={"device_id": payload.device_id},
        )

        # Get prediction from ML service only (no fallback)
        try:
            ml_prediction = await get_ml_prediction(payload)
            prediction = _ml_response_to_prediction(ml_prediction, payload)
            return prediction
        except FMMLError as exc:
            logger.exception(
                "ML service error when generating prediction",
                extra={"device_id": payload.device_id},
            )
            raise HTTPException(
                status_code=502,
                detail=f"ML service unavailable: {exc}",
            ) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to generate freshness prediction",
            extra={"device_id": payload.device_id},
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to generate freshness prediction due to an error",
        ) from exc
