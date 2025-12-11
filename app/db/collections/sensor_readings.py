"""Data access helpers for the sensor_readings collection."""

import logging
from typing import Any, Dict, List

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


async def find_recent_sensor_readings(
    db: AsyncIOMotorDatabase, limit: int = 20
) -> List[Dict[str, Any]]:
    """Fetch the most recent sensor readings."""
    # Sort primarily by received_at/timestamp if present, then created_at as a fallback.
    sort_keys = [
        ("received_at", -1),
        ("timestamp", -1),
        ("created_at", -1),
    ]
    projection = {
        "sensor_id": 1,
        "timestamp": 1,
        "received_at": 1,
        "temperature": 1,
        "humidity": 1,
        "uv_raw": 1,
        "uv_voltage": 1,
        "soil_raw": 1,
        "soil_voltage": 1,
        "mq_raw": 1,
        "mq_voltage": 1,
        "created_at": 1,
    }

    cursor = (
        db[COLLECTION_NAME]
        .find({}, projection)
        .sort(sort_keys)
        .limit(max(1, limit))
    )
    docs = await cursor.to_list(length=limit)
    for doc in docs:
        doc["_id"] = str(doc.get("_id"))
    return docs

