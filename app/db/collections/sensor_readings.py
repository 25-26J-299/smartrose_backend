"""Data access helpers for the sensor_readings collection."""

import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION_NAME = "sensor_readings"
logger = logging.getLogger(__name__)


async def insert_sensor_reading(db: AsyncIOMotorDatabase, payload: dict) -> str:
    """Insert a reading and return the inserted document id."""
    try:
        result = await db[COLLECTION_NAME].insert_one(payload)
        return str(result.inserted_id)
    except Exception:  # noqa: BLE001
        # Log before bubbling up so request handlers can return a clean 500.
        logger.exception(
            "Failed to insert sensor reading",
            extra={"collection": COLLECTION_NAME, "sensor_id": payload.get("sensor_id")},
        )
        raise

