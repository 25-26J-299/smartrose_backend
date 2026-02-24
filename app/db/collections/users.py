"""User collection helpers."""

from datetime import datetime
from typing import Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION_NAME = "users"


def _normalize_user(document: Optional[dict]) -> Optional[dict]:
    """Convert Mongo ObjectId to string and normalize legacy fields."""
    if document is None:
        return None
    document["_id"] = str(document["_id"])
    # Backward compatibility: name -> full_name, roles -> role
    if "name" in document and "full_name" not in document:
        document["full_name"] = document["name"]
    if "roles" in document and "role" not in document:
        roles = document.get("roles") or []
        document["role"] = roles[0] if roles else "farmer"
    document.setdefault("role", "farmer")
    document.setdefault("status", "pending")
    document.setdefault("is_active", True)
    return document


async def get_user_by_email(db: AsyncIOMotorDatabase, email: str) -> Optional[dict]:
    """Return a single user by email, if it exists."""
    user = await db[COLLECTION_NAME].find_one({"email": email.lower()})
    return _normalize_user(user)


async def create_user(db: AsyncIOMotorDatabase, user_data: dict) -> dict:
    """Insert a new user and return the stored document."""
    now = datetime.utcnow()
    user_data["created_at"] = user_data.get("created_at") or now
    user_data["updated_at"] = user_data.get("updated_at") or now
    user_data.setdefault("status", "pending")
    user_data.setdefault("is_active", True)
    result = await db[COLLECTION_NAME].insert_one(user_data)
    user_data["_id"] = str(result.inserted_id)
    return _normalize_user(user_data) or user_data


async def verify_user_credentials(
    db: AsyncIOMotorDatabase, email: str
) -> Optional[dict]:
    """Fetch a user for credential verification."""
    user = await db[COLLECTION_NAME].find_one({"email": email.lower()})
    return _normalize_user(user)


async def update_roles(
    db: AsyncIOMotorDatabase, user_id: str, roles: list[str]
) -> Optional[dict]:
    """Update user roles (legacy) and return the updated document."""
    if not ObjectId.is_valid(user_id):
        return None
    role = roles[0] if roles else "farmer"
    await db[COLLECTION_NAME].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"roles": roles, "role": role, "updated_at": datetime.utcnow()}},
    )
    updated = await db[COLLECTION_NAME].find_one({"_id": ObjectId(user_id)})
    return _normalize_user(updated)


async def update_role(
    db: AsyncIOMotorDatabase, user_id: str, role: str
) -> Optional[dict]:
    """Update user role and return the updated document."""
    if not ObjectId.is_valid(user_id):
        return None
    await db[COLLECTION_NAME].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": role, "updated_at": datetime.utcnow()}},
    )
    updated = await db[COLLECTION_NAME].find_one({"_id": ObjectId(user_id)})
    return _normalize_user(updated)


async def update_status(
    db: AsyncIOMotorDatabase, user_id: str, status: str
) -> Optional[dict]:
    """Update user status and return the updated document."""
    if not ObjectId.is_valid(user_id):
        return None
    await db[COLLECTION_NAME].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"status": status, "updated_at": datetime.utcnow()}},
    )
    updated = await db[COLLECTION_NAME].find_one({"_id": ObjectId(user_id)})
    return _normalize_user(updated)


async def update_last_login(
    db: AsyncIOMotorDatabase, user_id: str
) -> None:
    """Update last_login timestamp for the user."""
    if not ObjectId.is_valid(user_id):
        return
    await db[COLLECTION_NAME].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"last_login": datetime.utcnow(), "updated_at": datetime.utcnow()}},
    )


async def get_all_users(db: AsyncIOMotorDatabase) -> list[dict]:
    """Return all users, sorted by created_at descending. Excludes password_hash in projection."""
    cursor = db[COLLECTION_NAME].find(
        {},
        {"password_hash": 0},
    ).sort("created_at", -1)
    users = []
    async for doc in cursor:
        normalized = _normalize_user(doc)
        if normalized:
            users.append(normalized)
    return users
