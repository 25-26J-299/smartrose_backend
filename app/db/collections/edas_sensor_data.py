import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Literal, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

EDAS_COLLECTION_NAME = "edas_sensor_data"
DEVICES_COLLECTION_NAME = "devices"
logger = logging.getLogger(__name__)

# =============================================================================
# Timezone Configuration for Greenhouse Location
# =============================================================================
# Sri Lanka Standard Time (SLST) is UTC+5:30
# This ensures ML features (hour, is_day, time_period) reflect actual 
# greenhouse local time, not UTC
GREENHOUSE_TIMEZONE = timezone(timedelta(hours=5, minutes=30))  # UTC+5:30 (Sri Lanka)


# =============================================================================
# Time-Based Feature Calculation for ML
# =============================================================================

def calculate_time_features(timestamp: datetime) -> Dict[str, Any]:
    """Calculate time-based features from timestamp for ML training.
    
    CRITICAL: Uses GREENHOUSE LOCAL TIME (Sri Lanka UTC+5:30), not UTC!
    This ensures ML learns disease patterns based on actual local day/night cycles,
    temperature variations, and sunlight exposure at the greenhouse location.
    
    These features enable the ML model to learn time-dependent patterns:
    - Fungal risk behavior at night (high humidity + low light)
    - Heat stress behavior during day (high temperature + direct sunlight)
    
    Args:
        timestamp: The sensor reading timestamp (in Sri Lanka timezone)
        
    Returns:
        Dictionary containing:
            - hour: Hour of day in LOCAL time (0-23)
            - is_day: Boolean indicating day (06:00-18:00) vs night in LOCAL time
            - time_period: Classification based on LOCAL time (morning/noon/evening/night)
            
    Time Period Classification Rules (LOCAL TIME):
        06:00-10:00 → morning  (sunrise, temperature rising)
        10:00-14:00 → noon     (peak heat, maximum stress)
        14:00-18:00 → evening  (cooling, afternoon conditions)
        18:00-06:00 → night    (darkness, humidity increase, fungal risk)
    """
    # =========================================================================
    # ENSURE TIMESTAMP IS IN SRI LANKA TIMEZONE
    # =========================================================================
    # If timestamp has no timezone info, assume it's already in Sri Lanka time
    if timestamp.tzinfo is None:
        local_timestamp = timestamp.replace(tzinfo=GREENHOUSE_TIMEZONE)
    else:
        # Convert to Sri Lanka timezone
        local_timestamp = timestamp.astimezone(GREENHOUSE_TIMEZONE)
    
    # Extract hour from LOCAL time
    hour = local_timestamp.hour
    
    # Determine if it's day time (06:00-18:00 LOCAL time)
    is_day = 6 <= hour < 18
    
    # Classify time period for ML pattern recognition (LOCAL time)
    if 6 <= hour < 10:
        time_period = "morning"
    elif 10 <= hour < 14:
        time_period = "noon"
    elif 14 <= hour < 18:
        time_period = "evening"
    else:  # 18:00-06:00
        time_period = "night"
    
    logger.info(
        "ML time features calculated from Sri Lankan local time",
        extra={
            "local_time": local_timestamp.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "hour": hour,
            "is_day": is_day,
            "time_period": time_period,
        },
    )
    
    return {
        "hour": hour,
        "is_day": is_day,
        "time_period": time_period,
    }




async def create_edas_reading(db: AsyncIOMotorDatabase, payload: dict) -> str:
    """Insert an EDAS sensor reading and return the inserted document id.
    
    The backend automatically:
    - Sets the timestamp if not provided (CURRENT Sri Lankan time)
    - Calculates temperature_difference (plant_temperature - air_temperature)
    - Calculates ML time-based features (hour, is_day, time_period)
    
    Args:
        db: MongoDB database instance
        payload: Sensor data dictionary containing device_id, temperatures, and humidity
        
    Returns:
        str: The inserted document's MongoDB ObjectId as string
        
    Raises:
        Exception: If insertion fails (logged and re-raised)
    """
    try:
        # =====================================================================
        # Step 0: Resolve location_id and user_id from device registry
        # =====================================================================
        # Look up the device to inherit its greenhouse (location) and owner.
        # IoT devices only send device_id; the backend enriches the reading.
        if not payload.get("location_id") or not payload.get("user_id"):
            device_id_value = payload.get("device_id")
            device_doc = None

            if device_id_value:
                # Try lookup by MongoDB ObjectId first, then by serial number
                if ObjectId.is_valid(device_id_value):
                    device_doc = await db[DEVICES_COLLECTION_NAME].find_one(
                        {"_id": ObjectId(device_id_value)}
                    )
                if device_doc is None:
                    device_doc = await db[DEVICES_COLLECTION_NAME].find_one(
                        {"device_serial_number": device_id_value}
                    )

            if device_doc:
                if not payload.get("location_id"):
                    payload["location_id"] = str(device_doc.get("location_id", ""))
                if not payload.get("user_id"):
                    payload["user_id"] = str(device_doc.get("user_id", ""))
                logger.info(
                    "Resolved location_id and user_id from device registry",
                    extra={
                        "device_id": device_id_value,
                        "location_id": payload.get("location_id"),
                        "user_id": payload.get("user_id"),
                    },
                )
            else:
                logger.warning(
                    "Device not found in registry; location_id and user_id will be empty",
                    extra={"device_id": device_id_value},
                )

        # =====================================================================
        # Step 1: Get CURRENT Sri Lankan LOCAL TIME
        # =====================================================================
        if "timestamp" not in payload or payload["timestamp"] is None:
            # Get current time in Sri Lanka timezone (UTC+5:30)
            local_timestamp = datetime.now(GREENHOUSE_TIMEZONE)
        else:
            local_timestamp = payload["timestamp"]
            if local_timestamp.tzinfo is None:
                local_timestamp = local_timestamp.replace(tzinfo=GREENHOUSE_TIMEZONE)
        
        # =====================================================================
        # Step 2: Calculate ML Features from LOCAL TIME (before converting to UTC)
        # =====================================================================
        # CRITICAL: ML features must be calculated from LOCAL greenhouse time
        # to accurately reflect actual day/night cycles and temperature patterns
        time_features = calculate_time_features(local_timestamp)
        payload.update(time_features)
        
        # =====================================================================
        # Step 3: Convert to UTC for MongoDB Storage (Standard Practice)
        # =====================================================================
        # Convert Sri Lankan time to UTC by subtracting 5:30
        # Example: 23:45 SLST → 18:15 UTC
        utc_timestamp = local_timestamp.astimezone(timezone.utc)
        payload["timestamp"] = utc_timestamp
        
        logger.info(
            "Timestamp conversion for storage",
            extra={
                "local_time_slst": local_timestamp.strftime("%Y-%m-%d %H:%M:%S SLST"),
                "utc_time_stored": utc_timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "ml_hour": time_features["hour"],
                "ml_time_period": time_features["time_period"],
            },
        )
        
        # =====================================================================
        # Step 4: Calculate Temperature Difference
        # =====================================================================
        # Auto-calculate temperature difference
        # This is the key metric for early disease detection
        if "plant_temperature" in payload and "air_temperature" in payload:
            payload["temperature_difference"] = (
                payload["plant_temperature"] - payload["air_temperature"]
            )
        
        result = await db[EDAS_COLLECTION_NAME].insert_one(payload)
        logger.info(
            "EDAS sensor reading created with ML time features",
            extra={
                "collection": EDAS_COLLECTION_NAME,
                "id": str(result.inserted_id),
                "device_id": payload.get("device_id"),
                "hour": time_features["hour"],
                "is_day": time_features["is_day"],
                "time_period": time_features["time_period"],
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
    """Retrieve all EDAS sensor readings with pagination.
    
    Timestamps are returned as UTC (as stored in MongoDB).
    Backend remains timezone-agnostic.
    """
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
    """Retrieve a single EDAS sensor reading by its MongoDB ObjectId.
    
    Timestamp returned as UTC (as stored in MongoDB).
    """
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
    db: AsyncIOMotorDatabase,
    device_id: Optional[str] = None,
    location_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve the most recent EDAS sensor reading matching optional filters.

    Filters are combined with AND. At least one filter should be supplied for
    authenticated, tenant-safe queries. An empty filter is treated as
    \"match nothing\" so callers do not accidentally read all tenants' data.

    Timestamp returned as UTC (as stored in MongoDB).
    """
    try:
        query: Dict[str, Any] = {}
        if device_id:
            query["device_id"] = device_id
        if location_id:
            query["location_id"] = location_id
        if user_id:
            query["user_id"] = user_id
        if not query:
            return None

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
    """Retrieve EDAS sensor readings for a specific device.
    
    Timestamps returned as UTC (as stored in MongoDB).
    """
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
    """Update an EDAS sensor reading by its MongoDB ObjectId.
    
    Note: In production, sensor data is typically immutable for data integrity.
    This endpoint is provided for administrative corrections only.
    
    If timestamp or temperature fields are updated, dependent fields are 
    automatically recalculated (temperature_difference, hour, is_day, time_period).
    
    Args:
        db: MongoDB database instance
        reading_id: MongoDB ObjectId as string
        update_data: Dictionary of fields to update
        
    Returns:
        Updated document if found and updated, None otherwise
    """
    try:
        if not ObjectId.is_valid(reading_id):
            return None
        
        # Remove None values from update_data
        update_data = {k: v for k, v in update_data.items() if v is not None}
        if not update_data:
            # No fields to update, return existing document
            return await get_edas_reading_by_id(db, reading_id)
        
        # Get existing document for calculations
        existing = await get_edas_reading_by_id(db, reading_id)
        if not existing:
            return None
        
        # Recalculate temperature_difference if temperature fields are updated
        if "plant_temperature" in update_data or "air_temperature" in update_data:
            plant_temp = update_data.get(
                "plant_temperature", existing.get("plant_temperature")
            )
            air_temp = update_data.get(
                "air_temperature", existing.get("air_temperature")
            )
            if plant_temp is not None and air_temp is not None:
                update_data["temperature_difference"] = plant_temp - air_temp
        
        # Recalculate ML time-based features if timestamp is updated
        if "timestamp" in update_data:
            timestamp = update_data["timestamp"]
            if isinstance(timestamp, datetime):
                time_features = calculate_time_features(timestamp)
                update_data.update(time_features)
                logger.info(
                    "Recalculated ML time features due to timestamp update",
                    extra={
                        "id": reading_id,
                        "new_hour": time_features["hour"],
                        "new_is_day": time_features["is_day"],
                        "new_time_period": time_features["time_period"],
                    },
                )

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


async def get_edas_readings_by_location(
    db: AsyncIOMotorDatabase,
    location_id: str,
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Retrieve EDAS sensor readings for a specific greenhouse (location).

    Useful for showing all sensor data from every EDAS device inside one greenhouse.
    Timestamps returned as UTC (as stored in MongoDB).
    """
    try:
        cursor = (
            db[EDAS_COLLECTION_NAME]
            .find({"location_id": location_id})
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
            "Failed to fetch EDAS sensor readings by location",
            extra={"collection": EDAS_COLLECTION_NAME, "location_id": location_id},
        )
        raise


async def get_edas_readings_by_user(
    db: AsyncIOMotorDatabase,
    user_id: str,
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Retrieve EDAS sensor readings for all devices owned by a user.

    Aggregates readings across all of the user's greenhouses and devices.
    Timestamps returned as UTC (as stored in MongoDB).
    """
    try:
        cursor = (
            db[EDAS_COLLECTION_NAME]
            .find({"user_id": user_id})
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
            "Failed to fetch EDAS sensor readings by user",
            extra={"collection": EDAS_COLLECTION_NAME, "user_id": user_id},
        )
        raise

