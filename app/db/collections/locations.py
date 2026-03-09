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


async def delete_locations_by_user(
    db: AsyncIOMotorDatabase, user_id: str
) -> int:
    """Delete all locations that belong to a user."""
    result = await db[COLLECTION_NAME].delete_many({"user_id": user_id})
    return result.deleted_count


async def count_locations_by_user_ids(
    db: AsyncIOMotorDatabase, user_ids: list[str]
) -> dict[str, int]:
    """Return location counts keyed by user_id for a list of users."""
    if not user_ids:
        return {}

    pipeline = [
        {"$match": {"user_id": {"$in": user_ids}}},
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
    ]
    counts: dict[str, int] = {}
    async for row in db[COLLECTION_NAME].aggregate(pipeline):
        uid = row.get("_id")
        if isinstance(uid, str):
            counts[uid] = int(row.get("count", 0))
    return counts


async def count_location_types_by_user_ids(
    db: AsyncIOMotorDatabase, user_ids: list[str]
) -> dict[str, dict[str, int]]:
    """Return per-user counts split by greenhouse and flower_shop."""
    if not user_ids:
        return {}

    pipeline = [
        {"$match": {"user_id": {"$in": user_ids}}},
        {"$group": {"_id": {"user_id": "$user_id", "type": "$type"}, "count": {"$sum": 1}}},
    ]
    counts: dict[str, dict[str, int]] = {}
    async for row in db[COLLECTION_NAME].aggregate(pipeline):
        group = row.get("_id") or {}
        uid = group.get("user_id")
        location_type = (group.get("type") or "").lower()
        if isinstance(uid, str):
            if uid not in counts:
                counts[uid] = {"greenhouse": 0, "flower_shop": 0}
            if location_type in {"greenhouse", "flower_shop"}:
                counts[uid][location_type] = int(row.get("count", 0))
    return counts


async def delete_location(db: AsyncIOMotorDatabase, location_id: str) -> bool:
    """Delete a single location by ID."""
    if not ObjectId.is_valid(location_id):
        return False
    result = await db[COLLECTION_NAME].delete_one({"_id": ObjectId(location_id)})
    return result.deleted_count > 0
