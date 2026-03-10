"""Data access helpers for the eosm_s_data collection."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.utils.timezone_utils import convert_datetime_fields

COLLECTION_NAME = "eosm_s_data"
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
            extra={
                "collection": COLLECTION_NAME,
                "device_id": payload.get("device_id"),
            },
        )
        raise


async def find_recent_sensor_readings(
    db: AsyncIOMotorDatabase,
    limit: int = 20,
    location_id: str | None = None,
    user_id: str | None = None,
    device_id: str | None = None,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Fetch sensor readings with optional filters."""
    sort_keys = [
        ("received_at", -1),
        ("timestamp", -1),
    ]
    projection = {
        "device_id": 1,
        "base_station_id": 1,
        "base_station_serial": 1,
        "location_id": 1,
        "user_id": 1,
        "timestamp": 1,
        "reading_time_utc": 1,
        "reading_time_slst": 1,
        "received_at": 1,
        "temperature": 1,
        "humidity": 1,
        "uv_raw": 1,
        "uv_voltage": 1,
        "soil_raw": 1,
        "soil_voltage": 1,
        "mq_raw": 1,
        "mq_voltage": 1,
    }

    query: Dict[str, Any] = {}
    if location_id:
        query["location_id"] = location_id
    if user_id:
        query["user_id"] = user_id
    if device_id:
        query["device_id"] = device_id
    
    # Add timestamp range filtering
    if start_timestamp is not None or end_timestamp is not None:
        timestamp_query: Dict[str, Any] = {}
        if start_timestamp is not None:
            timestamp_query["$gte"] = start_timestamp
        if end_timestamp is not None:
            timestamp_query["$lte"] = end_timestamp
        if timestamp_query:
            query["timestamp"] = timestamp_query

    cursor = (
        db[COLLECTION_NAME]
        .find(query, projection)
        .sort(sort_keys)
        .limit(max(1, limit))
    )
    docs = await cursor.to_list(length=limit)
    for i, doc in enumerate(docs):
        doc["_id"] = str(doc.get("_id"))
        if doc.get("base_station_id"):
            doc["base_station_id"] = str(doc["base_station_id"])
        docs[i] = convert_datetime_fields(doc, ["reading_time_utc", "received_at"])
    return docs

