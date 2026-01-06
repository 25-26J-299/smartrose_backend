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

    # Generate alerts based on sensor readings (not from ML status)
    alerts = []
    
    # Water level alerts
    if reading.water_level < 20:
        alerts.append("Low water level detected")
    
    # Gas value alerts
    if reading.gas_value > 100:
        alerts.append("High gas value detected")
    
    # Air temperature alerts
    if reading.air_temperature > 25.0:
        alerts.append("High air temperature detected")
    if reading.air_temperature < 15.0:
        alerts.append("Low air temperature detected")
    
    # Water temperature alerts
    if reading.water_temperature > 25.0:
        alerts.append("High water temperature detected")
    if reading.water_temperature < 15.0:
        alerts.append("Low water temperature detected")
    
    # Humidity alerts
    if reading.humidity > 80.0:
        alerts.append("High humidity detected")
    if reading.humidity < 40.0:
        alerts.append("Low humidity detected")
    
    return FMPredictionResponse(
        freshness_score=ml_response["freshness_score"],
        vase_life_hours=ml_response["vase_life_hours"],
        alerts=alerts,
    )


@router.post("/upload", summary="Upload sensor reading from ESP32")
async def upload_sensor_reading(payload: FMSensorInput) -> Dict[str, str]:

    try:
        logger.info(
            "Sensor reading upload received from ESP32",
            extra={
                "device_id": payload.device_id,
                "air_temperature": payload.air_temperature,
                "water_temperature": payload.water_temperature,
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
            "air_temperature": payload.air_temperature,
            "water_temperature": payload.water_temperature,
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

    try:
        logger.info(
            "Latest reading requested",
            extra={"device_id": device_id},
        )

        reading_doc = await get_latest(device_id)

        if reading_doc is None:
            raise HTTPException(
                status_code=404,
                detail=f"No readings found for device_id: {device_id}",
            )

        # Convert to FMSensorInput format to ensure proper field names
        # The model_validator will handle backward compatibility automatically
        from app.models.fm_models import FMSensorInput
        
        try:
            # Create a copy to avoid modifying the original document
            reading_data = dict(reading_doc)
            # Remove MongoDB _id field as it's not part of FMSensorInput
            _id = reading_data.pop("_id", None)
            
            # Pydantic will use model_validator to handle old 'temperature' field
            reading = FMSensorInput(**reading_data)
            
            # Convert back to dict and add _id back
            # Use mode='json' to ensure datetime objects are serialized as ISO strings
            result = reading.model_dump(mode='json')
            result["_id"] = _id
            return result
        except Exception as exc:
            logger.exception(
                "Failed to parse reading document",
                extra={
                    "device_id": device_id,
                    "document_keys": list(reading_doc.keys()),
                    "error": str(exc),
                },
            )
            # Fallback: return raw document if parsing fails
            return reading_doc
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
        # The model_validator will handle backward compatibility automatically
        from app.models.fm_models import FMSensorInput
        
        try:
            # Let Pydantic handle the conversion, including backward compatibility
            # Create a copy to avoid modifying the original document
            reading_data = dict(reading_doc)
            # Remove MongoDB _id field as it's not part of FMSensorInput
            reading_data.pop("_id", None)
            
            # Pydantic will use model_validator to handle old 'temperature' field
            reading = FMSensorInput(**reading_data)
        except Exception as exc:
            logger.exception(
                "Failed to parse reading document",
                extra={
                    "device_id": device_id,
                    "document_keys": list(reading_doc.keys()),
                    "error": str(exc),
                },
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse sensor reading: {exc}",
            ) from exc

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

        # Return the converted reading (with proper field names) instead of raw doc
        # This ensures frontend receives air_temperature and water_temperature
        # Use mode='json' to ensure datetime objects are serialized as ISO strings
        reading_dict = reading.model_dump(mode='json')
        # Add back the _id for frontend reference
        reading_dict["_id"] = reading_doc.get("_id")

        return {
            "reading": reading_dict,
            "prediction": prediction.model_dump(mode='json'),
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
