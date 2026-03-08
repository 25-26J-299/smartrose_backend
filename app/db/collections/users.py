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
    # Backward compatibility: name -> full_name
    if "name" in document and "full_name" not in document:
        document["full_name"] = document["name"]
    # Sync role <-> roles so both are always present
    if "roles" in document and document["roles"]:
        roles = document["roles"]
        document.setdefault("role", roles[0])
    elif "role" in document and document["role"]:
        document.setdefault("roles", [document["role"]])
    document.setdefault("role", "farmer")
    document.setdefault("roles", [document["role"]])
    document.setdefault("status", "pending")
    document.setdefault("is_active", True)
    return document


async def get_user_by_id(db: AsyncIOMotorDatabase, user_id: str) -> Optional[dict]:
    """Return a single user by ID, if it exists."""
    if not ObjectId.is_valid(user_id):
        return None
    user = await db[COLLECTION_NAME].find_one(
        {"_id": ObjectId(user_id)},
        {"password_hash": 0},
    )
    return _normalize_user(user)


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


async def update_user(
    db: AsyncIOMotorDatabase,
    user_id: str,
    *,
    full_name: Optional[str] = None,
    phone: Optional[str] = None,
    role: Optional[str] = None,
    roles: Optional[list[str]] = None,
    is_active: Optional[bool] = None,
) -> Optional[dict]:
    """Update user fields and return the updated document."""
    if not ObjectId.is_valid(user_id):
        return None
    updates: dict = {"updated_at": datetime.utcnow()}
    if full_name is not None:
        updates["full_name"] = full_name
    if phone is not None:
        updates["phone"] = phone
    if roles is not None:
        updates["roles"] = roles
        updates["role"] = roles[0] if roles else "farmer"
    elif role is not None:
        updates["role"] = role
        updates["roles"] = [role]
    if is_active is not None:
        updates["is_active"] = is_active
    await db[COLLECTION_NAME].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": updates},
    )
    return await get_user_by_id(db, user_id)


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


async def search_approved_users(
    db: AsyncIOMotorDatabase, query: str
) -> list[dict]:
    """Search approved users by email, phone, or full_name. Returns users with password_hash excluded."""
    if not query or len(query.strip()) < 2:
        return []
    q = query.strip().lower()
    regex = {"$regex": q, "$options": "i"}
    cursor = db[COLLECTION_NAME].find(
        {
            "status": "approved",
            "is_active": True,
            "$or": [
                {"email": regex},
                {"phone": regex},
                {"full_name": regex},
                {"name": regex},
            ],
        },
        {"password_hash": 0},
    ).sort("created_at", -1)
    users = []
    async for doc in cursor:
        normalized = _normalize_user(doc)
        if normalized:
            users.append(normalized)
    return users


async def get_users_by_ids(
    db: AsyncIOMotorDatabase, user_ids: list[str]
) -> list[dict]:
    """Return approved users by IDs."""
    if not user_ids:
        return []
    ids = [ObjectId(uid) for uid in user_ids if ObjectId.is_valid(uid)]
    if not ids:
        return []
    cursor = db[COLLECTION_NAME].find(
        {"_id": {"$in": ids}, "status": "approved"},
        {"password_hash": 0},
    ).sort("created_at", -1)
    users = []
    async for doc in cursor:
        normalized = _normalize_user(doc)
        if normalized:
            users.append(normalized)
    return users


async def get_all_users(
    db: AsyncIOMotorDatabase, status_filter: Optional[str] = None
) -> list[dict]:
    """Return all users, sorted by created_at descending. Excludes password_hash.
    If status_filter is provided (approved|pending|rejected), filter by status."""
    query: dict = {}
    if status_filter in ("approved", "pending", "rejected"):
        query["status"] = status_filter
    cursor = db[COLLECTION_NAME].find(
        query,
        {"password_hash": 0},
    ).sort("created_at", -1)
    users = []
    async for doc in cursor:
        normalized = _normalize_user(doc)
        if normalized:
            users.append(normalized)
    return users


async def delete_user(db: AsyncIOMotorDatabase, user_id: str) -> bool:
    """Delete a user by ID."""
    if not ObjectId.is_valid(user_id):
        return False
    result = await db[COLLECTION_NAME].delete_one({"_id": ObjectId(user_id)})
    return result.deleted_count > 0
