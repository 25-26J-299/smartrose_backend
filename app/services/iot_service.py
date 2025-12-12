"""Service helpers for IoT device ingestion."""

import logging
from typing import Dict

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections.sensor_readings import insert_sensor_reading
from app.models.sensor_models import LoRaSensorIngest
from app.utils import time_utils
from app.utils.response_builder import success_response

logger = logging.getLogger(__name__)


async def ingest_lora_reading(
    payload: LoRaSensorIngest, db: AsyncIOMotorDatabase
) -> Dict[str, str]:
    """Persist a LoRa gateway reading and return a standard response."""
    # ================= eosm component start: LoRa ingestion service =================
    record = payload.model_dump()
    record["received_at"] = time_utils.utc_now()

    try:
        inserted_id = await insert_sensor_reading(db, record)
    except Exception:
        logger.exception(
            "Failed to ingest LoRa reading",
            extra={"basestation_id": payload.basestation_id},
        )
        raise

    return success_response(message="ok", data={"id": inserted_id})
    # ================= eosm component end =================

