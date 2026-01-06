import logging
from typing import Dict

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections.edas_sensor_data import create_edas_reading
from app.models.edas_models import EDASSensorData
from app.services.edas_ml_service import generate_disease_prediction
from app.utils import time_utils
from app.utils.response_builder import success_response

logger = logging.getLogger(__name__)


async def ingest_edas_sensor_reading(
    payload: EDASSensorData, db: AsyncIOMotorDatabase
) -> Dict[str, any]:

    # ================= EDAS component start: sensor ingestion service =================
    try:
        # Convert Pydantic model to dict
        record = payload.model_dump()
        
        # Ensure timestamp is set (backend-controlled for consistency)
        if record.get("timestamp") is None:
            record["timestamp"] = time_utils.utc_now()
        
        # Calculate temperature difference if not already set
        # This is the primary metric for disease detection
        if record.get("temperature_difference") is None:
            record["temperature_difference"] = (
                record["plant_temperature"] - record["air_temperature"]
            )
        
        # Store in MongoDB
        inserted_id = await create_edas_reading(db, record)
        
        logger.info(
            "EDAS sensor reading ingested successfully",
            extra={
                "device_id": payload.device_id,
                "record_id": inserted_id,
                "temp_diff": record["temperature_difference"],
            },
        )
        
        # Generate ML prediction for the newly ingested reading
        try:
            await generate_disease_prediction(
                plant_temperature=payload.plant_temperature,
                air_temperature=payload.air_temperature,
                humidity=payload.humidity,
                timestamp=record["timestamp"],
                device_id=payload.device_id,
                sensor_reading_id=inserted_id,
                db=db,
                save_to_db=True,
            )
            logger.info(
                "ML prediction generated for ingested EDAS reading",
                extra={"reading_id": inserted_id, "device_id": payload.device_id},
            )
        except Exception as pred_err:
            # Don't fail ingestion if prediction fails
            logger.warning(
                "Failed to generate prediction for ingested EDAS reading (non-fatal)",
                extra={"reading_id": inserted_id, "error": str(pred_err)},
            )
        
        return success_response(
            message="EDAS sensor data ingested successfully",
            data={
                "id": inserted_id,
                "temperature_difference": record["temperature_difference"],
            },
        )
        
    except Exception:
        logger.exception(
            "Failed to ingest EDAS sensor reading",
            extra={"device_id": payload.device_id},
        )
        raise
    # ================= EDAS component end =================


def calculate_temperature_difference(
    plant_temperature: float, air_temperature: float
) -> float:

    return plant_temperature - air_temperature


async def get_device_statistics(
    db: AsyncIOMotorDatabase, device_id: str
) -> Dict[str, any]:


    logger.info(f"Statistics requested for device: {device_id}")
    return {
        "device_id": device_id,
        "message": "Statistics calculation not yet implemented",
    }
    # ================= EDAS component end =================
