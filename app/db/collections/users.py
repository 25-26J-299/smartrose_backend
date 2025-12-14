"""User collection helpers."""

from datetime import datetime
from typing import Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION_NAME = "users"


def _normalize_user(document: Optional[dict]) -> Optional[dict]:
    """Convert Mongo ObjectId to string and normalize roles."""
    if document is None:
        return None
    document["_id"] = str(document["_id"])
    document.setdefault("roles", [])
    return document


async def get_user_by_email(db: AsyncIOMotorDatabase, email: str) -> Optional[dict]:
    """Return a single user by email, if it exists."""
    user = await db[COLLECTION_NAME].find_one({"email": email})
    return _normalize_user(user)


async def create_user(db: AsyncIOMotorDatabase, user_data: dict) -> dict:
    """Insert a new user and return the stored document."""
    user_data["created_at"] = user_data.get("created_at") or datetime.utcnow()
    result = await db[COLLECTION_NAME].insert_one(user_data)
    user_data["_id"] = str(result.inserted_id)
    user_data.setdefault("roles", [])
    return user_data


async def verify_user_credentials(
    db: AsyncIOMotorDatabase, email: str
) -> Optional[dict]:
    """Fetch a user for credential verification."""
    user = await db[COLLECTION_NAME].find_one({"email": email})
    return _normalize_user(user)


async def update_roles(
    db: AsyncIOMotorDatabase, user_id: str, roles: list[str]
) -> Optional[dict]:
    """Update user roles and return the updated document."""
    if not ObjectId.is_valid(user_id):
        return None
    await db[COLLECTION_NAME].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"roles": roles}},
    )
    updated = await db[COLLECTION_NAME].find_one({"_id": ObjectId(user_id)})
    return _normalize_user(updated)

