"""Service layer for EOSM ML prediction orchestration.

Coordinates between sensor readings, ML model inference, and prediction storage.
"""

import logging
from datetime import datetime
from typing import Optional

from app.db.collections.eosm_predictions import insert_stress_prediction
from app.ml.eosm.eosm_inference import predict_stress
from app.models.eosm_prediction_models import (
    EOSMStressPredictionRequest,
    EOSMStressPredictionResponse,
)

# ================= eosm component start: ML service =================

logger = logging.getLogger(__name__)


async def generate_stress_prediction(
    request: EOSMStressPredictionRequest,
    db=None,
    basestation_id: Optional[str] = None,
    greenhouse_id: Optional[str] = None,
    sensor_reading_id: Optional[str] = None,
    save_to_db: bool = True,
) -> Optional[EOSMStressPredictionResponse]:
    """Generate stress prediction from sensor data.
    
    Args:
        request: Prediction request with sensor readings
        db: MongoDB database instance (required if save_to_db is True)
        basestation_id: Base station identifier
        greenhouse_id: Greenhouse identifier
        sensor_reading_id: Associated sensor reading ID
        save_to_db: Whether to save prediction to database
    
    Returns:
        Prediction response or None if prediction fails
    """
    try:
        # Get prediction from ML model
        prediction_result = predict_stress(
            temperature=request.temperature,
            humidity=request.humidity,
            uv_voltage=request.uv_voltage,
            soil_voltage=request.soil_voltage,
            mq_voltage=request.mq_voltage,
        )
        
        if prediction_result is None:
            logger.warning("ML model prediction returned None")
            return None
        
        # Create prediction response
        prediction = EOSMStressPredictionResponse(
            stress_label=prediction_result["stress_label"],
            stress_probabilities=prediction_result["stress_probabilities"],
            timestamp=datetime.utcnow(),
        )
        
        # Save to database if requested
        if save_to_db and db is not None:
            prediction_dict = prediction.model_dump()
            prediction_dict["basestation_id"] = basestation_id or request.basestation_id
            prediction_dict["greenhouse_id"] = greenhouse_id or request.greenhouse_id
            prediction_dict["sensor_reading_id"] = sensor_reading_id
            prediction_dict["created_at"] = datetime.utcnow()
            
            # Convert datetime to timestamp for MongoDB
            if isinstance(prediction_dict["timestamp"], datetime):
                prediction_dict["timestamp"] = int(prediction_dict["timestamp"].timestamp())
            if isinstance(prediction_dict["created_at"], datetime):
                prediction_dict["created_at"] = int(prediction_dict["created_at"].timestamp())
            
            await insert_stress_prediction(db, prediction_dict)
            logger.info(
                "EOSM stress prediction saved to database",
                extra={
                    "stress_label": prediction.stress_label,
                    "basestation_id": basestation_id,
                    "greenhouse_id": greenhouse_id,
                },
            )
        
        return prediction
        
    except Exception:  # noqa: BLE001
        logger.exception("Failed to generate EOSM stress prediction")
        return None


async def predict_from_sensor_reading(
    reading_data: dict,
    db=None,
    save_to_db: bool = True,
) -> Optional[EOSMStressPredictionResponse]:
    """Generate prediction from a sensor reading document.
    
    Args:
        reading_data: Sensor reading document from database
        db: MongoDB database instance (required if save_to_db is True)
        save_to_db: Whether to save prediction to database
    
    Returns:
        Prediction response or None if prediction fails
    """
    try:
        # Extract sensor values
        request = EOSMStressPredictionRequest(
            temperature=float(reading_data.get("temperature", 20.0)),
            humidity=float(reading_data.get("humidity", 50.0)),
            soil_voltage=float(reading_data.get("soil_voltage", 2.0)),
            uv_voltage=float(reading_data.get("uv_voltage", 0.5)),
            mq_voltage=float(reading_data.get("mq_voltage", 0.5)),
            basestation_id=reading_data.get("basestation_id"),
            greenhouse_id=reading_data.get("greenhouse_id"),
        )
        
        return await generate_stress_prediction(
            request=request,
            db=db,
            basestation_id=reading_data.get("basestation_id"),
            greenhouse_id=reading_data.get("greenhouse_id"),
            sensor_reading_id=str(reading_data.get("_id", "")),
            save_to_db=save_to_db,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to generate prediction from sensor reading")
        return None

# ================= eosm component end =================


