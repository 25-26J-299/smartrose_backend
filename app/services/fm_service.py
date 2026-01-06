"""Service layer for Freshness Monitoring (FM) predictions and sensor data."""

import logging
import os
from typing import Optional

import joblib

from app.core.config import settings
from app.db.mongodb import get_database
from app.models.fm_models import FMPredictionResponse, FMSensorInput

logger = logging.getLogger(__name__)

# MongoDB collection name
COLLECTION_NAME = "fm_sensor_data"

# Model path from settings (which loads from environment variable or uses default)
MODEL_PATH = settings.FM_MODEL_PATH

# Cached model instance
_model: Optional[object] = None


def _load_model() -> Optional[object]:

    global _model

    # Return cached model if already loaded
    if _model is not None:
        return _model

    try:
        if not os.path.exists(MODEL_PATH):
            logger.warning(
                f"FM model not found at {MODEL_PATH}, will use fallback prediction"
            )
            return None

        _model = joblib.load(MODEL_PATH)
        logger.info(f"FM model loaded successfully from {MODEL_PATH}")
        return _model
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Failed to load FM model from {MODEL_PATH}")
        return None


async def save_reading(reading: FMSensorInput) -> str:

    db = get_database()
    collection = db[COLLECTION_NAME]

    try:
        # Convert Pydantic model to dict for MongoDB
        record = reading.model_dump()
        result = await collection.insert_one(record)
        inserted_id = str(result.inserted_id)

        logger.info(
            "Sensor reading saved to MongoDB",
            extra={
                "device_id": reading.device_id,
                "inserted_id": inserted_id,
                "collection": COLLECTION_NAME,
            },
        )
        return inserted_id
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to save sensor reading to MongoDB",
            extra={
                "device_id": reading.device_id,
                "collection": COLLECTION_NAME,
            },
        )
        raise exc


async def get_latest(device_id: str) -> Optional[dict]:
  
    db = get_database()
    collection = db[COLLECTION_NAME]

    try:
        # Sort by timestamp descending, then by _id descending as tiebreaker
        # This ensures we always get the most recent document
        cursor = collection.find(
            {"device_id": device_id}
        ).sort([("timestamp", -1), ("_id", -1)]).limit(1)

        # Get the first (and only) document from the cursor
        doc_list = await cursor.to_list(length=1)
        
        if doc_list and len(doc_list) > 0:
            doc = doc_list[0]
            # Convert ObjectId to string for JSON serialization
            doc["_id"] = str(doc["_id"])
            
            # Log the timestamp of the retrieved document for debugging
            timestamp_str = str(doc.get("timestamp", "unknown"))
            logger.info(
                "Retrieved latest reading for device",
                extra={
                    "device_id": device_id,
                    "timestamp": timestamp_str,
                    "document_id": doc["_id"],
                    "air_temperature": doc.get("air_temperature"),
                    "humidity": doc.get("humidity"),
                },
            )
            return doc

        logger.info(
            "No readings found for device", extra={"device_id": device_id}
        )
        return None
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to retrieve latest reading from MongoDB",
            extra={"device_id": device_id, "collection": COLLECTION_NAME},
        )
        raise exc


def predict_from_reading(reading: FMSensorInput) -> FMPredictionResponse:
    """Predict freshness score and vase life from sensor reading.

    If model is available, uses ML model prediction. Otherwise, uses
    a heuristic fallback with basic alerts for low water or high gas.

    Args:
        reading: FMSensorInput model instance with sensor data

    Returns:
        FMPredictionResponse with freshness_score, vase_life_hours, and alerts
    """
    model = _load_model()

    if model is not None:
        try:
            # Prepare features: [air_temperature, humidity, gas_value, water_level]
            # Note: ML model still expects "temperature" parameter, so we pass air_temperature
            features = [
                [
                    reading.air_temperature,
                    reading.humidity,
                    reading.gas_value,
                    reading.water_level,
                ]
            ]

            # Get prediction from model
            prediction = model.predict(features)

            # Assuming model returns [freshness_score, vase_life_hours]
            # Adjust based on actual model output format
            if isinstance(prediction, (list, tuple)) and len(prediction) > 0:
                if isinstance(prediction[0], (list, tuple)) and len(prediction[0]) >= 2:
                    freshness_score = float(prediction[0][0])
                    vase_life_hours = float(prediction[0][1])
                else:
                    # Single value prediction, estimate vase life
                    freshness_score = float(prediction[0])
                    vase_life_hours = freshness_score * 0.5  # Rough estimate
            else:
                # Handle scalar values or non-indexable predictions
                # Try to convert directly to float if it's a scalar
                try:
                    freshness_score = float(prediction)
                    vase_life_hours = freshness_score * 0.5
                except (TypeError, ValueError):
                    # If conversion fails, use fallback values
                    logger.warning(
                        "Unexpected prediction format, using fallback values",
                        extra={"prediction_type": type(prediction).__name__},
                    )
                    freshness_score = 50.0
                    vase_life_hours = 25.0

            # Clamp values to reasonable ranges
            freshness_score = max(0.0, min(100.0, freshness_score))
            vase_life_hours = max(0.0, vase_life_hours)

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

            logger.info(
                "Prediction generated using ML model",
                extra={
                    "device_id": reading.device_id,
                    "freshness_score": freshness_score,
                    "vase_life_hours": vase_life_hours,
                },
            )

            return FMPredictionResponse(
                freshness_score=freshness_score,
                vase_life_hours=vase_life_hours,
                alerts=alerts,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Error during ML model prediction, falling back to heuristic",
                extra={"device_id": reading.device_id},
            )
            # Fall through to heuristic fallback

    # Heuristic fallback when model is not available or prediction fails
    try:
        # Simple heuristic: base score on optimal conditions
        # Optimal: air_temp ~20C, humidity ~60%, gas <50, water >50
        temp_score = 100.0 - abs(reading.air_temperature - 20.0) * 2.0
        humidity_score = 100.0 - abs(reading.humidity - 60.0) * 1.5
        gas_score = max(0.0, 100.0 - reading.gas_value * 0.5)
        water_score = min(100.0, reading.water_level * 2.0)

        # Weighted average
        freshness_score = (
            temp_score * 0.3
            + humidity_score * 0.3
            + gas_score * 0.2
            + water_score * 0.2
        )

        # Clamp to 0-100
        freshness_score = max(0.0, min(100.0, freshness_score))

        # Estimate vase life: higher freshness = longer life
        # Base estimate: 24-72 hours depending on freshness
        vase_life_hours = 24.0 + (freshness_score / 100.0) * 48.0

        # Generate alerts
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

        logger.info(
            "Prediction generated using heuristic fallback",
            extra={
                "device_id": reading.device_id,
                "freshness_score": freshness_score,
                "vase_life_hours": vase_life_hours,
            },
        )

        return FMPredictionResponse(
            freshness_score=freshness_score,
            vase_life_hours=vase_life_hours,
            alerts=alerts,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Error in heuristic fallback prediction",
            extra={"device_id": reading.device_id},
        )
        # Return safe default values
        return FMPredictionResponse(
            freshness_score=50.0,
            vase_life_hours=36.0,
            alerts=["Prediction error occurred"],
        )
