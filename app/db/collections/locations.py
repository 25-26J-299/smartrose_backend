"""Location collection (greenhouses and flower shops)."""

from datetime import datetime
from typing import Literal, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION_NAME = "locations"
LocationType = Literal["greenhouse", "flower_shop"]


def _normalize_location(document: Optional[dict]) -> Optional[dict]:
    """Convert Mongo ObjectId to string."""
    if document is None:
        return None
    document["_id"] = str(document["_id"])
    return document


async def create_location(
    db: AsyncIOMotorDatabase,
    user_id: str,
    name: str,
    location_type: LocationType,
    address: str,
) -> dict:
    """Insert a new location (greenhouse or flower shop) and return the stored document."""
    now = datetime.utcnow()
    doc = {
        "user_id": user_id,
        "name": name,
        "type": location_type,
        "address": address,
        "created_at": now,
        "updated_at": now,
        "is_active": True,
    }
    result = await db[COLLECTION_NAME].insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return _normalize_location(doc) or doc


async def search_locations_by_name(
    db: AsyncIOMotorDatabase, query: str
) -> list[dict]:
    """Search locations by name. Returns locations matching the query."""
    if not query or len(query.strip()) < 2:
        return []
    regex = {"$regex": query.strip(), "$options": "i"}
    cursor = db[COLLECTION_NAME].find({"name": regex}).sort("created_at", -1)
    return [_normalize_location(doc) async for doc in cursor if _normalize_location(doc)]


async def get_locations_by_user(
    db: AsyncIOMotorDatabase, user_id: str
) -> list[dict]:
    """Return all locations for a user."""
    cursor = db[COLLECTION_NAME].find({"user_id": user_id}).sort("created_at", -1)
    return [_normalize_location(doc) async for doc in cursor if _normalize_location(doc)]


async def get_all_locations(db: AsyncIOMotorDatabase) -> list[dict]:
    """Return all locations, sorted by created_at descending."""
    cursor = db[COLLECTION_NAME].find({}).sort("created_at", -1)
    return [_normalize_location(doc) async for doc in cursor if _normalize_location(doc)]


async def get_location_by_id(
    db: AsyncIOMotorDatabase, location_id: str
) -> Optional[dict]:
    """Return a single location by ID."""
    if not ObjectId.is_valid(location_id):
        return None
    doc = await db[COLLECTION_NAME].find_one({"_id": ObjectId(location_id)})
    return _normalize_location(doc)


async def update_location(
    db: AsyncIOMotorDatabase,
    location_id: str,
    *,
    name: Optional[str] = None,
    location_type: Optional[LocationType] = None,
    address: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[dict]:
    """Update a location and return the updated document."""
    if not ObjectId.is_valid(location_id):
        return None
    updates: dict = {"updated_at": datetime.utcnow()}
    if name is not None:
        updates["name"] = name
    if location_type is not None:
        updates["type"] = location_type
    if address is not None:
        updates["address"] = address
    if is_active is not None:
        updates["is_active"] = is_active
    await db[COLLECTION_NAME].update_one(
        {"_id": ObjectId(location_id)},
        {"$set": updates},
    )
    return await get_location_by_id(db, location_id)
