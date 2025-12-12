"""FastAPI endpoints for Freshness Monitoring (FM) component."""

import logging
from typing import Dict

from fastapi import APIRouter, HTTPException, Path, Response

from app.models.fm_models import FMPredictionResponse, FMSensorInput
from app.services.fm_service import get_latest, predict_from_reading, save_reading

router = APIRouter(prefix="/fm", tags=["FM"])
logger = logging.getLogger(__name__)


@router.post("/upload", summary="Upload sensor reading")
async def upload_sensor_reading(payload: FMSensorInput) -> Dict[str, str]:
    """Upload and save a sensor reading to MongoDB.

    Accepts FMSensorInput with sensor data (temperature, humidity, gas_value,
    water_level, device_id, timestamp) and saves it to the database.

    Args:
        payload: FMSensorInput model instance with sensor reading data

    Returns:
        Dictionary with "message" set to "saved" and "id" containing the
        inserted document ID

    Raises:
        HTTPException: If database insertion fails (500 status code)
    """
    try:
        logger.info(
            "Sensor reading upload received",
            extra={
                "device_id": payload.device_id,
                "timestamp": payload.timestamp.isoformat(),
            },
        )

        inserted_id = await save_reading(payload)

        return {"message": "saved", "id": inserted_id}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to upload sensor reading",
            extra={"device_id": payload.device_id},
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to save sensor reading due to an error",
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
    """Get the latest sensor reading with freshness prediction from ML model.

    Fetches the most recent sensor reading from the database (sorted by timestamp
    descending) and generates a freshness prediction using the ML model (or heuristic
    fallback if model is not available).

    Args:
        device_id: Device identifier to query

    Returns:
        Dictionary containing:
            - reading: Latest sensor reading data
            - prediction: Freshness prediction (freshness_score, vase_life_hours, alerts)

    Raises:
        HTTPException: If no reading found (404) or prediction fails (500)
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

        # Generate prediction using ML model (or heuristic fallback)
        prediction = predict_from_reading(reading)

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


@router.post("/predict", summary="Predict freshness from sensor reading")
async def predict_freshness(payload: FMSensorInput) -> FMPredictionResponse:
    """Generate freshness prediction from sensor reading data.

    Accepts FMSensorInput and uses either the ML model (if available) or
    a heuristic fallback to predict freshness score, vase life hours, and
    generate alerts for conditions like low water or high gas values.

    Args:
        payload: FMSensorInput model instance with sensor reading data

    Returns:
        FMPredictionResponse containing:
            - freshness_score: Predicted freshness score (0-100)
            - vase_life_hours: Predicted vase life in hours
            - alerts: List of alert messages for detected issues

    Raises:
        HTTPException: If prediction fails (500 status code)
    """
    try:
        logger.info(
            "Freshness prediction requested",
            extra={"device_id": payload.device_id},
        )

        prediction = predict_from_reading(payload)

        return prediction
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to generate freshness prediction",
            extra={"device_id": payload.device_id},
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to generate freshness prediction due to an error",
        ) from exc
