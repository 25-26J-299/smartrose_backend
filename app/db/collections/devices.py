"""Device collection."""

from datetime import datetime
from typing import Literal, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION_NAME = "devices"
DeviceType = Literal["INM", "EOSM", "EDAS", "FM"]


def _normalize_device(document: Optional[dict]) -> Optional[dict]:
    """Convert Mongo ObjectId to string."""
    if document is None:
        return None
    document["_id"] = str(document["_id"])
    return document


async def create_device(
    db: AsyncIOMotorDatabase,
    location_id: str,
    user_id: str,
    name: str,
    device_type: str,
    device_serial_number: str,
) -> dict:
    """Insert a new device and return the stored document."""
    now = datetime.utcnow()
    doc = {
        "location_id": location_id,
        "user_id": user_id,
        "name": name,
        "type": device_type,
        "device_serial_number": device_serial_number,
        "last_seen": None,
        "created_at": now,
        "updated_at": now,
    }
    result = await db[COLLECTION_NAME].insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return _normalize_device(doc) or doc


async def get_devices_by_location(
    db: AsyncIOMotorDatabase, location_id: str
) -> list[dict]:
    """Return all devices for a location."""
    cursor = db[COLLECTION_NAME].find({"location_id": location_id}).sort(
        "created_at", -1
    )
    return [_normalize_device(doc) async for doc in cursor if _normalize_device(doc)]


async def get_devices_by_user(
    db: AsyncIOMotorDatabase, user_id: str
) -> list[dict]:
    """Return all devices for a user."""
    cursor = db[COLLECTION_NAME].find({"user_id": user_id}).sort("created_at", -1)
    return [_normalize_device(doc) async for doc in cursor if _normalize_device(doc)]


async def get_all_devices(
    db: AsyncIOMotorDatabase,
    location_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> list[dict]:
    """Return all devices, optionally filtered by location or user."""
    query: dict = {}
    if location_id:
        query["location_id"] = location_id
    if user_id:
        query["user_id"] = user_id
    cursor = db[COLLECTION_NAME].find(query).sort("created_at", -1)
    return [_normalize_device(doc) async for doc in cursor if _normalize_device(doc)]


async def get_device_by_id(
    db: AsyncIOMotorDatabase, device_id: str
) -> Optional[dict]:
    """Return a single device by ID."""
    if not ObjectId.is_valid(device_id):
        return None
    doc = await db[COLLECTION_NAME].find_one({"_id": ObjectId(device_id)})
    return _normalize_device(doc)


async def get_device_by_serial(
    db: AsyncIOMotorDatabase, device_serial_number: str
) -> Optional[dict]:
    """Return a single device by serial number."""
    doc = await db[COLLECTION_NAME].find_one(
        {"device_serial_number": device_serial_number}
    )
    return _normalize_device(doc)


async def delete_device(db: AsyncIOMotorDatabase, device_id: str) -> bool:
    """Delete a single device by ID."""
    if not ObjectId.is_valid(device_id):
        return False
    result = await db[COLLECTION_NAME].delete_one({"_id": ObjectId(device_id)})
    return result.deleted_count > 0


async def update_device(
    db: AsyncIOMotorDatabase,
    device_id: str,
    *,
    name: Optional[str] = None,
    device_type: Optional[str] = None,
    device_serial_number: Optional[str] = None,
    last_seen: Optional[datetime] = None,
) -> Optional[dict]:
    """Update a device and return the updated document."""
    if not ObjectId.is_valid(device_id):
        return None
    updates: dict = {"updated_at": datetime.utcnow()}
    if name is not None:
        updates["name"] = name
    if device_type is not None:
        updates["type"] = device_type
    if device_serial_number is not None:
        updates["device_serial_number"] = device_serial_number
    if last_seen is not None:
        updates["last_seen"] = last_seen
    await db[COLLECTION_NAME].update_one(
        {"_id": ObjectId(device_id)},
        {"$set": updates},
    )
    return await get_device_by_id(db, device_id)


async def update_last_seen(
    db: AsyncIOMotorDatabase, device_id: str
) -> None:
    """Update last_seen timestamp for the device."""
    if not ObjectId.is_valid(device_id):
        return
    await db[COLLECTION_NAME].update_one(
        {"_id": ObjectId(device_id)},
        {"$set": {"last_seen": datetime.utcnow(), "updated_at": datetime.utcnow()}},
    )


async def delete_devices_by_user(
    db: AsyncIOMotorDatabase, user_id: str
) -> int:
    """Delete all devices assigned to a user."""
    result = await db[COLLECTION_NAME].delete_many({"user_id": user_id})
    return result.deleted_count


async def delete_devices_by_locations(
    db: AsyncIOMotorDatabase, location_ids: list[str]
) -> int:
    """Delete all devices assigned to the provided locations."""
    if not location_ids:
        return 0
    result = await db[COLLECTION_NAME].delete_many(
        {"location_id": {"$in": location_ids}}
    )
    return result.deleted_count
