import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

EDAS_COLLECTION_NAME = "edas_sensor_data"
logger = logging.getLogger(__name__)




async def create_edas_reading(db: AsyncIOMotorDatabase, payload: dict) -> str:

    try:
        # Backend controls the timestamp for consistency
        if "timestamp" not in payload or payload["timestamp"] is None:
            payload["timestamp"] = datetime.utcnow()
        
        # Auto-calculate temperature difference
        # This is the key metric for early disease detection
        if "plant_temperature" in payload and "air_temperature" in payload:
            payload["temperature_difference"] = (
                payload["plant_temperature"] - payload["air_temperature"]
            )
        
        result = await db[EDAS_COLLECTION_NAME].insert_one(payload)
        logger.info(
            "EDAS sensor reading created",
            extra={
                "collection": EDAS_COLLECTION_NAME,
                "id": str(result.inserted_id),
                "device_id": payload.get("device_id"),
            },
        )
        return str(result.inserted_id)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to insert EDAS sensor reading",
            extra={
                "collection": EDAS_COLLECTION_NAME,
                "device_id": payload.get("device_id"),
            },
        )
        raise


async def get_all_edas_readings(
    db: AsyncIOMotorDatabase,
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:

    try:
        cursor = (
            db[EDAS_COLLECTION_NAME]
            .find()
            .sort("timestamp", -1)  # Most recent first
            .skip(skip)
            .limit(limit)
        )
        readings = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            readings.append(doc)
        return readings
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to fetch EDAS sensor readings",
            extra={"collection": EDAS_COLLECTION_NAME},
        )
        raise


async def get_edas_reading_by_id(
    db: AsyncIOMotorDatabase, reading_id: str
) -> Optional[Dict[str, Any]]:

    try:
        if not ObjectId.is_valid(reading_id):
            return None
        doc = await db[EDAS_COLLECTION_NAME].find_one({"_id": ObjectId(reading_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to fetch EDAS sensor reading",
            extra={"collection": EDAS_COLLECTION_NAME, "id": reading_id},
        )
        raise


async def get_latest_edas_reading(
    db: AsyncIOMotorDatabase, device_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:

    try:
        query = {}
        if device_id:
            query["device_id"] = device_id
        
        doc = await db[EDAS_COLLECTION_NAME].find_one(
            query,
            sort=[("timestamp", -1)]
        )
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to fetch latest EDAS sensor reading",
            extra={"collection": EDAS_COLLECTION_NAME, "device_id": device_id},
        )
        raise


async def get_edas_readings_by_device(
    db: AsyncIOMotorDatabase,
    device_id: str,
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:

    try:
        cursor = (
            db[EDAS_COLLECTION_NAME]
            .find({"device_id": device_id})
            .sort("timestamp", -1)
            .skip(skip)
            .limit(limit)
        )
        readings = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            readings.append(doc)
        return readings
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to fetch EDAS sensor readings by device",
            extra={"collection": EDAS_COLLECTION_NAME, "device_id": device_id},
        )
        raise


async def update_edas_reading(
    db: AsyncIOMotorDatabase, reading_id: str, update_data: dict
) -> Optional[Dict[str, Any]]:

    try:
        if not ObjectId.is_valid(reading_id):
            return None
        
        # Remove None values from update_data
        update_data = {k: v for k, v in update_data.items() if v is not None}
        if not update_data:
            # No fields to update, return existing document
            return await get_edas_reading_by_id(db, reading_id)
        
        # Recalculate temperature_difference if temperature fields are updated
        if "plant_temperature" in update_data or "air_temperature" in update_data:
            existing = await get_edas_reading_by_id(db, reading_id)
            if existing:
                plant_temp = update_data.get(
                    "plant_temperature", existing.get("plant_temperature")
                )
                air_temp = update_data.get(
                    "air_temperature", existing.get("air_temperature")
                )
                if plant_temp is not None and air_temp is not None:
                    update_data["temperature_difference"] = plant_temp - air_temp

        result = await db[EDAS_COLLECTION_NAME].find_one_and_update(
            {"_id": ObjectId(reading_id)},
            {"$set": update_data},
            return_document=True,
        )
        if result:
            result["_id"] = str(result["_id"])
            logger.info(
                "EDAS sensor reading updated",
                extra={"collection": EDAS_COLLECTION_NAME, "id": reading_id},
            )
        return result
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to update EDAS sensor reading",
            extra={"collection": EDAS_COLLECTION_NAME, "id": reading_id},
        )
        raise


async def delete_edas_reading(db: AsyncIOMotorDatabase, reading_id: str) -> bool:

    try:
        if not ObjectId.is_valid(reading_id):
            return False
        result = await db[EDAS_COLLECTION_NAME].delete_one({"_id": ObjectId(reading_id)})
        if result.deleted_count > 0:
            logger.info(
                "EDAS sensor reading deleted",
                extra={"collection": EDAS_COLLECTION_NAME, "id": reading_id},
            )
            return True
        return False
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to delete EDAS sensor reading",
            extra={"collection": EDAS_COLLECTION_NAME, "id": reading_id},
        )
        raise

