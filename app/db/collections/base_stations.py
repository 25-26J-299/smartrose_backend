"""Base station collection.

EOSM: one base station per user (recommended), serving multiple devices across locations.
"""

from datetime import datetime
from typing import Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION_NAME = "base_stations"


def _normalize(document: Optional[dict]) -> Optional[dict]:
    if document is None:
        return None
    document["_id"] = str(document["_id"])
    return document


async def create_base_station(
    db: AsyncIOMotorDatabase,
    *,
    user_id: str,
    name: str,
    serial: str,
) -> dict:
    now = datetime.utcnow()
    doc = {
        "user_id": user_id,
        "name": name,
        "serial": serial,
        "last_seen": None,
        "created_at": now,
        "updated_at": now,
    }
    result = await db[COLLECTION_NAME].insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return _normalize(doc) or doc


async def get_base_station_by_id(
    db: AsyncIOMotorDatabase, base_station_id: str
) -> Optional[dict]:
    if not ObjectId.is_valid(base_station_id):
        return None
    doc = await db[COLLECTION_NAME].find_one({"_id": ObjectId(base_station_id)})
    return _normalize(doc)


async def get_base_station_by_serial(
    db: AsyncIOMotorDatabase, serial: str
) -> Optional[dict]:
    doc = await db[COLLECTION_NAME].find_one({"serial": serial})
    return _normalize(doc)


async def get_base_stations_by_user(
    db: AsyncIOMotorDatabase, user_id: str
) -> list[dict]:
    cursor = db[COLLECTION_NAME].find({"user_id": user_id}).sort("created_at", -1)
    return [_normalize(doc) async for doc in cursor if _normalize(doc)]


async def get_all_base_stations(
    db: AsyncIOMotorDatabase,
    *,
    user_id: Optional[str] = None,
) -> list[dict]:
    query: dict = {}
    if user_id:
        query["user_id"] = user_id
    cursor = db[COLLECTION_NAME].find(query).sort("created_at", -1)
    return [_normalize(doc) async for doc in cursor if _normalize(doc)]


async def update_base_station(
    db: AsyncIOMotorDatabase,
    base_station_id: str,
    *,
    name: Optional[str] = None,
    serial: Optional[str] = None,
    last_seen: Optional[datetime] = None,
) -> Optional[dict]:
    if not ObjectId.is_valid(base_station_id):
        return None
    updates: dict = {"updated_at": datetime.utcnow()}
    if name is not None:
        updates["name"] = name
    if serial is not None:
        updates["serial"] = serial
    if last_seen is not None:
        updates["last_seen"] = last_seen
    await db[COLLECTION_NAME].update_one(
        {"_id": ObjectId(base_station_id)}, {"$set": updates}
    )
    return await get_base_station_by_id(db, base_station_id)


async def delete_base_station(db: AsyncIOMotorDatabase, base_station_id: str) -> bool:
    if not ObjectId.is_valid(base_station_id):
        return False
    result = await db[COLLECTION_NAME].delete_one({"_id": ObjectId(base_station_id)})
    return result.deleted_count > 0
