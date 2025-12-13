"""Data access helpers for the freshness_sensor_data collection."""

import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION_NAME = "fm_sensor_data"
logger = logging.getLogger(__name__)


async def insert_freshness_sensor_data(
    db: AsyncIOMotorDatabase, payload: dict
) -> str:
    """Insert a freshness sensor reading and return the inserted document id."""
    try:
        result = await db[COLLECTION_NAME].insert_one(payload)
        return str(result.inserted_id)
    except Exception:  # noqa: BLE001
        # Log before bubbling up so request handlers can return a clean 500.
        logger.exception(
            "Failed to insert freshness sensor data",
            extra={
                "collection": COLLECTION_NAME,
                "device_id": payload.get("device_id"),
            },
        )
        raise


