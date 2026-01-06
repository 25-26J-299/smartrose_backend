"""Service layer for EDAS ML prediction orchestration.

Coordinates between sensor readings, ML model inference, and prediction storage.
"""

import logging
from datetime import datetime
from typing import Optional

from app.db.collections.edas_predictions import insert_disease_prediction
from app.ml.edas.edas_inference import predict_disease_risk

# ================= edas component start: ML service =================

logger = logging.getLogger(__name__)


async def generate_disease_prediction(
    plant_temperature: float,
    air_temperature: float,
    humidity: float,
    timestamp: Optional[datetime] = None,
    device_id: Optional[str] = None,
    sensor_reading_id: Optional[str] = None,
    db=None,
    save_to_db: bool = True,
) -> Optional[dict]:
    """Generate disease risk prediction from sensor data.
    
    Args:
        plant_temperature: Plant temperature in Celsius
        air_temperature: Air temperature in Celsius
        humidity: Humidity percentage (0-100)
        timestamp: Timestamp for time feature calculation
        device_id: Device identifier
        sensor_reading_id: Associated sensor reading ID
        db: MongoDB database instance (required if save_to_db is True)
        save_to_db: Whether to save prediction to database
    
    Returns:
        Prediction dictionary or None if prediction fails
    """
    try:
        # Get prediction from ML model
        prediction_result = predict_disease_risk(
            plant_temperature=plant_temperature,
            air_temperature=air_temperature,
            humidity=humidity,
            timestamp=timestamp,
        )
        
        if prediction_result is None:
            logger.warning("EDAS ML model prediction returned None")
            return None
        
        # Prepare prediction record
        prediction = {
            "disease_risk": prediction_result["disease_risk"],
            "disease_probability": prediction_result["disease_probability"],
            "risk_probabilities": prediction_result["risk_probabilities"],
            "timestamp": timestamp or datetime.utcnow(),
            "device_id": device_id,
            "sensor_reading_id": sensor_reading_id,
            "created_at": datetime.utcnow(),
        }
        
        # Save to database if requested
        if save_to_db and db is not None:
            # Convert datetime objects to UTC timestamps for MongoDB storage
            prediction_dict = prediction.copy()
            if isinstance(prediction_dict["timestamp"], datetime):
                prediction_dict["timestamp"] = prediction_dict["timestamp"]
            if isinstance(prediction_dict["created_at"], datetime):
                prediction_dict["created_at"] = prediction_dict["created_at"]
            
            await insert_disease_prediction(db, prediction_dict)
            logger.info(
                "EDAS disease prediction saved to database",
                extra={
                    "disease_risk": prediction["disease_risk"],
                    "device_id": device_id,
                    "disease_probability": prediction["disease_probability"],
                },
            )
        
        return prediction
        
    except Exception:  # noqa: BLE001
        logger.exception("Failed to generate EDAS disease prediction")
        return None


async def predict_from_sensor_reading(
    reading_data: dict,
    db=None,
    save_to_db: bool = True,
) -> Optional[dict]:
    """Generate prediction from a sensor reading document.
    
    Args:
        reading_data: Sensor reading document from database
        db: MongoDB database instance (required if save_to_db is True)
        save_to_db: Whether to save prediction to database
    
    Returns:
        Prediction dictionary or None if prediction fails
    """
    try:
        # Extract sensor values
        plant_temperature = float(reading_data.get("plant_temperature", 25.0))
        air_temperature = float(reading_data.get("air_temperature", 25.0))
        humidity = float(reading_data.get("humidity", 50.0))
        device_id = reading_data.get("device_id")
        
        # Extract timestamp
        timestamp = reading_data.get("timestamp")
        if timestamp and not isinstance(timestamp, datetime):
            # Convert if needed
            if isinstance(timestamp, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        
        return await generate_disease_prediction(
            plant_temperature=plant_temperature,
            air_temperature=air_temperature,
            humidity=humidity,
            timestamp=timestamp,
            device_id=device_id,
            sensor_reading_id=str(reading_data.get("_id", "")),
            db=db,
            save_to_db=save_to_db,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to generate prediction from sensor reading")
        return None

# ================= edas component end =================

