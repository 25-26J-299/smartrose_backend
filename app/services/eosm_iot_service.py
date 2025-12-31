"""Service helpers for eosm IoT device ingestion."""

import logging
from typing import Dict

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections.eosm_readings import insert_sensor_reading
from app.models.eosm_sensor_models import LoRaSensorIngest
from app.models.eosm_prediction_models import EOSMStressPredictionRequest
from app.services.eosm_ml_service import generate_stress_prediction
from app.utils import time_utils
from app.utils.response_builder import success_response

logger = logging.getLogger(__name__)


async def ingest_lora_reading(
    payload: LoRaSensorIngest, db: AsyncIOMotorDatabase
) -> Dict[str, str]:
    """Persist a LoRa gateway reading, generate ML prediction, and return a standard response."""
    # ================= eosm component start: LoRa ingestion service =================
    record = payload.model_dump()
    record["received_at"] = time_utils.utc_now()

    try:
        inserted_id = await insert_sensor_reading(db, record)
        
        # Generate ML prediction for the newly ingested reading
        try:
            prediction_request = EOSMStressPredictionRequest(
                temperature=payload.temperature,
                humidity=payload.humidity,
                soil_voltage=payload.soil_voltage,
                uv_voltage=payload.uv_voltage,
                mq_voltage=payload.mq_voltage,
                basestation_id=payload.basestation_id,
                greenhouse_id=payload.greenhouse_id,
            )
            
            await generate_stress_prediction(
                request=prediction_request,
                db=db,
                basestation_id=payload.basestation_id,
                greenhouse_id=payload.greenhouse_id,
                sensor_reading_id=inserted_id,
                save_to_db=True,
            )
            logger.info(
                "ML prediction generated for ingested reading",
                extra={"reading_id": inserted_id, "basestation_id": payload.basestation_id},
            )
        except Exception as pred_err:
            # Don't fail ingestion if prediction fails
            logger.warning(
                "Failed to generate prediction for ingested reading (non-fatal)",
                extra={"reading_id": inserted_id, "error": str(pred_err)},
            )
        
    except Exception:
        logger.exception(
            "Failed to ingest LoRa reading",
            extra={"basestation_id": payload.basestation_id},
        )
        raise

    return success_response(message="ok", data={"id": inserted_id})
    # ================= eosm component end =================

