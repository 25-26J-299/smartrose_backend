"""Data access helpers for the notifications collection."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION_NAME = "notifications"
logger = logging.getLogger(__name__)


def _serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert _id to string and datetime fields for JSON."""
    if not doc:
        return doc
    out = dict(doc)
    if out.get("_id") is not None:
        out["id"] = str(out["_id"])
        del out["_id"]
    if out.get("created_at") and isinstance(out["created_at"], datetime):
        out["created_at"] = out["created_at"].isoformat() + "Z"
    return out


async def insert_notification(
    db: AsyncIOMotorDatabase,
    user_id: str,
    type_: str,
    title: str,
    message: str,
    severity: str = "INFO",
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Insert a notification and return its id."""
    doc = {
        "user_id": user_id,
        "type": type_,
        "title": title,
        "message": message,
        "severity": severity.upper() if severity else "INFO",
        "is_read": False,
        "metadata": metadata or {},
        "created_at": datetime.utcnow(),
    }
    result = await db[COLLECTION_NAME].insert_one(doc)
    logger.info(
        "Notification created",
        extra={"collection": COLLECTION_NAME, "id": str(result.inserted_id), "type": type_},
    )
    return str(result.inserted_id)


async def find_by_user(
    db: AsyncIOMotorDatabase,
    user_id: str,
    type_: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Return notifications for a user, optionally filtered by type. Newest first."""
    query: Dict[str, Any] = {"user_id": user_id}
    if type_:
        query["type"] = type_
    cursor = (
        db[COLLECTION_NAME]
        .find(query)
        .sort("created_at", -1)
        .limit(max(1, limit))
    )
    docs = await cursor.to_list(length=limit)
    return [_serialize_doc(doc) for doc in docs]


async def get_by_id(
    db: AsyncIOMotorDatabase,
    notification_id: str,
) -> Optional[Dict[str, Any]]:
    """Get a notification by id. Returns None if not found or not valid ObjectId."""
    if not ObjectId.is_valid(notification_id):
        return None
    doc = await db[COLLECTION_NAME].find_one({"_id": ObjectId(notification_id)})
    return _serialize_doc(doc) if doc else None


async def mark_as_read(
    db: AsyncIOMotorDatabase,
    notification_id: str,
    user_id: str,
) -> bool:
    """Mark a notification as read. Returns True if updated."""
    if not ObjectId.is_valid(notification_id):
        return False
    result = await db[COLLECTION_NAME].update_one(
        {"_id": ObjectId(notification_id), "user_id": user_id},
        {"$set": {"is_read": True}},
    )
    return result.modified_count > 0


async def mark_all_as_read(
    db: AsyncIOMotorDatabase,
    user_id: str,
) -> int:
    """Mark all notifications for the user as read. Returns count updated."""
    result = await db[COLLECTION_NAME].update_many(
        {"user_id": user_id, "is_read": False},
        {"$set": {"is_read": True}},
    )
    return result.modified_count


async def delete_all_by_user(
    db: AsyncIOMotorDatabase,
    user_id: str,
) -> int:
    """Delete all notifications for the user. Returns count deleted."""
    result = await db[COLLECTION_NAME].delete_many({"user_id": user_id})
    return result.deleted_count


async def exists_eosm_high_for_reading(
    db: AsyncIOMotorDatabase,
    user_id: str,
    sensor_reading_id: str,
) -> bool:
    """Return True if an EOSM HIGH notification already exists for this reading (avoids duplicates)."""
    if not sensor_reading_id:
        return False
    try:
        doc = await db[COLLECTION_NAME].find_one(
            {
                "user_id": user_id,
                "type": "EOSM",
                "severity": "HIGH",
                "metadata.sensor_reading_id": sensor_reading_id,
            }
        )
        return doc is not None
    except Exception:  # noqa: BLE001
        logger.exception("exists_eosm_high_for_reading failed")
        return True  # skip creating to be safe


async def exists_inm_event_for_reading(
    db: AsyncIOMotorDatabase,
    user_id: str,
    sensor_reading_id: str,
    event_key: str,
) -> bool:
    """Return True if an INM notification already exists for this reading/event pair."""
    if not sensor_reading_id or not event_key:
        return False
    try:
        doc = await db[COLLECTION_NAME].find_one(
            {
                "user_id": user_id,
                "type": "INM",
                "metadata.sensor_reading_id": sensor_reading_id,
                "metadata.event_key": event_key,
            }
        )
        return doc is not None
    except Exception:  # noqa: BLE001
        logger.exception("exists_inm_event_for_reading failed")
        return True  # skip creating to be safe


async def exists_fm_event_for_reading(
    db: AsyncIOMotorDatabase,
    user_id: str,
    sensor_reading_id: str,
    event_key: str,
) -> bool:
    """Return True if an FM notification already exists for this reading/event pair."""
    if not sensor_reading_id or not event_key:
        return False
    try:
        doc = await db[COLLECTION_NAME].find_one(
            {
                "user_id": user_id,
                "type": "FM",
                "metadata.sensor_reading_id": sensor_reading_id,
                "metadata.event_key": event_key,
            }
        )
        return doc is not None
    except Exception:  # noqa: BLE001
        logger.exception("exists_fm_event_for_reading failed")
        return True  # skip creating to be safe
