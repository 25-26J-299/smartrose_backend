"""Greenhouse and flower shop collection helpers."""

from datetime import datetime
from typing import Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION_NAME = "greenhouses"


def _normalize_greenhouse(document: Optional[dict]) -> Optional[dict]:
    """Convert Mongo ObjectId to string."""
    if document is None:
        return None
    document["_id"] = str(document["_id"])
    return document


async def create_greenhouse(
    db: AsyncIOMotorDatabase,
    user_id: str,
    name: str,
    address: str,
) -> dict:
    """Insert a new greenhouse/flower shop and return the stored document."""
    now = datetime.utcnow()
    doc = {
        "user_id": user_id,
        "name": name,
        "address": address,
        "created_at": now,
        "updated_at": now,
        "is_active": True,
    }
    result = await db[COLLECTION_NAME].insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return _normalize_greenhouse(doc) or doc


async def get_greenhouses_by_user(
    db: AsyncIOMotorDatabase, user_id: str
) -> list[dict]:
    """Return all greenhouses/flower shops for a user."""
    cursor = db[COLLECTION_NAME].find({"user_id": user_id}).sort("created_at", -1)
    return [_normalize_greenhouse(doc) async for doc in cursor if _normalize_greenhouse(doc)]


async def get_all_greenhouses(db: AsyncIOMotorDatabase) -> list[dict]:
    """Return all greenhouses/flower shops, sorted by created_at descending."""
    cursor = db[COLLECTION_NAME].find({}).sort("created_at", -1)
    return [_normalize_greenhouse(doc) async for doc in cursor if _normalize_greenhouse(doc)]


async def get_greenhouse_by_id(
    db: AsyncIOMotorDatabase, greenhouse_id: str
) -> Optional[dict]:
    """Return a single greenhouse by ID."""
    if not ObjectId.is_valid(greenhouse_id):
        return None
    doc = await db[COLLECTION_NAME].find_one({"_id": ObjectId(greenhouse_id)})
    return _normalize_greenhouse(doc)


async def update_greenhouse(
    db: AsyncIOMotorDatabase,
    greenhouse_id: str,
    *,
    name: Optional[str] = None,
    address: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[dict]:
    """Update a greenhouse and return the updated document."""
    if not ObjectId.is_valid(greenhouse_id):
        return None
    updates: dict = {"updated_at": datetime.utcnow()}
    if name is not None:
        updates["name"] = name
    if address is not None:
        updates["address"] = address
    if is_active is not None:
        updates["is_active"] = is_active
    await db[COLLECTION_NAME].update_one(
        {"_id": ObjectId(greenhouse_id)},
        {"$set": updates},
    )
    return await get_greenhouse_by_id(db, greenhouse_id)
