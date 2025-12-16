"""Data access helpers for the eosm_s_data collection."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

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
                "basestation_id": payload.get("basestation_id"),
            },
        )
        raise


async def find_recent_sensor_readings(
    db: AsyncIOMotorDatabase,
    limit: int = 20,
    basestation_id: str | None = None,
    greenhouse_id: str | None = None,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Fetch sensor readings with optional filters.
    
    Args:
        db: MongoDB database instance
        limit: Maximum number of records to return
        basestation_id: Filter by basestation ID
        greenhouse_id: Filter by greenhouse ID
        start_timestamp: Filter records with timestamp >= start_timestamp (epoch seconds)
        end_timestamp: Filter records with timestamp <= end_timestamp (epoch seconds)
    """
    # Sort primarily by received_at/timestamp if present, then created_at as a fallback.
    sort_keys = [
        ("received_at", -1),
        ("timestamp", -1),
        ("created_at", -1),
    ]
    projection = {
        "sensor_id": 1,
        "basestation_id": 1,
        "greenhouse_id": 1,
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

    query: Dict[str, Any] = {}
    if basestation_id:
        query["basestation_id"] = basestation_id
    if greenhouse_id:
        query["greenhouse_id"] = greenhouse_id
    
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
    for doc in docs:
        doc["_id"] = str(doc.get("_id"))
    return docs

