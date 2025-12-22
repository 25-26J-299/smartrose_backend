"""Data access helpers for the inm_sensor_data collection."""

import logging
from datetime import datetime
from typing import Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

INM_COLLECTION_NAME = "inm_sensor_data"
logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# INM Sensor Data CRUD Operations
# -----------------------------------------------------------------------------


async def create_inm_reading(db: AsyncIOMotorDatabase, payload: dict) -> str:
    """Insert an INM sensor reading and return the inserted document id.
    
    Backend always controls the timestamp to ensure consistency.
    """
    try:
        # Force backend-controlled timestamp
        payload["timestamp"] = datetime.utcnow()
        
        result = await db[INM_COLLECTION_NAME].insert_one(payload)
        logger.info(
            "INM sensor reading created",
            extra={"collection": INM_COLLECTION_NAME, "id": str(result.inserted_id)},
        )
        return str(result.inserted_id)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to insert INM sensor reading",
            extra={"collection": INM_COLLECTION_NAME, "device_id": payload.get("device_id")},
        )
        raise


async def get_all_inm_readings(
    db: AsyncIOMotorDatabase,
    skip: int = 0,
    limit: int = 500,
) -> list[dict]:
    """Retrieve all INM sensor readings with pagination, sorted by newest first."""
    try:
        # Sort by timestamp descending (newest first) - IMPORTANT!
        cursor = db[INM_COLLECTION_NAME].find().sort("timestamp", -1).skip(skip).limit(limit)
        readings = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            # Convert datetime to ISO format string for JSON serialization
            if "timestamp" in doc and doc["timestamp"]:
                doc["timestamp"] = doc["timestamp"].isoformat()
            readings.append(doc)
        return readings
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to fetch INM sensor readings",
            extra={"collection": INM_COLLECTION_NAME},
        )
        raise


async def get_inm_reading_by_id(
    db: AsyncIOMotorDatabase, reading_id: str
) -> Optional[dict]:
    """Retrieve a single INM sensor reading by its MongoDB ObjectId."""
    try:
        if not ObjectId.is_valid(reading_id):
            return None
        doc = await db[INM_COLLECTION_NAME].find_one({"_id": ObjectId(reading_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to fetch INM sensor reading",
            extra={"collection": INM_COLLECTION_NAME, "id": reading_id},
        )
        raise


async def update_inm_reading(
    db: AsyncIOMotorDatabase, reading_id: str, update_data: dict
) -> Optional[dict]:
    """Update an INM sensor reading by its MongoDB ObjectId."""
    try:
        if not ObjectId.is_valid(reading_id):
            return None
        # Remove None values from update_data
        update_data = {k: v for k, v in update_data.items() if v is not None}
        if not update_data:
            # No fields to update, return existing document
            return await get_inm_reading_by_id(db, reading_id)

        result = await db[INM_COLLECTION_NAME].find_one_and_update(
            {"_id": ObjectId(reading_id)},
            {"$set": update_data},
            return_document=True,
        )
        if result:
            result["_id"] = str(result["_id"])
            logger.info(
                "INM sensor reading updated",
                extra={"collection": INM_COLLECTION_NAME, "id": reading_id},
            )
        return result
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to update INM sensor reading",
            extra={"collection": INM_COLLECTION_NAME, "id": reading_id},
        )
        raise


async def delete_inm_reading(db: AsyncIOMotorDatabase, reading_id: str) -> bool:
    """Delete an INM sensor reading by its MongoDB ObjectId. Returns True if deleted."""
    try:
        if not ObjectId.is_valid(reading_id):
            return False
        result = await db[INM_COLLECTION_NAME].delete_one({"_id": ObjectId(reading_id)})
        if result.deleted_count > 0:
            logger.info(
                "INM sensor reading deleted",
                extra={"collection": INM_COLLECTION_NAME, "id": reading_id},
            )
            return True
        return False
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to delete INM sensor reading",
            extra={"collection": INM_COLLECTION_NAME, "id": reading_id},
        )
        raise

