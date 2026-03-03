"""MongoDB helpers for persistent INM growth stage state.

Growth stage is stored **per device** so that multiple greenhouses (each with
their own INM device) can independently track their own rose growth stage.

Document shape (one doc per device):
{
  "_id": "gs_<device_id>",          e.g. "gs_INM-001"
  "device_id": "INM-001",
  "current_growth_stage": "vegetative" | "flowering" | "maintenance",
  "updated_at": <datetime>
}
"""

import logging
from datetime import datetime
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

logger = logging.getLogger(__name__)

COLLECTION_NAME = "inm_config"
DEFAULT_GROWTH_STAGE = "vegetative"


def _doc_id(device_id: str) -> str:
    """Build a stable, unique MongoDB _id for the growth stage of a device."""
    return f"gs_{device_id}"


async def set_current_growth_stage(
    db: AsyncIOMotorDatabase,
    growth_stage: str,
    device_id: str,
) -> dict:
    """Create or overwrite the growth stage document for a specific device."""
    now = datetime.utcnow()
    doc = await db[COLLECTION_NAME].find_one_and_update(
        {"_id": _doc_id(device_id)},
        {
            "$set": {
                "device_id": device_id,
                "current_growth_stage": growth_stage,
                "updated_at": now,
            }
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )

    if doc is None:
        doc = {
            "_id": _doc_id(device_id),
            "device_id": device_id,
            "current_growth_stage": growth_stage,
            "updated_at": now,
        }

    doc["_id"] = str(doc["_id"])
    logger.info(
        "Growth stage updated",
        extra={"collection": COLLECTION_NAME, "device_id": device_id, "growth_stage": growth_stage},
    )
    return doc


async def get_growth_stage_state(
    db: AsyncIOMotorDatabase,
    device_id: str,
) -> Optional[dict]:
    """Fetch the growth stage document for a specific device, or None if not set."""
    doc = await db[COLLECTION_NAME].find_one({"_id": _doc_id(device_id)})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def get_current_growth_stage(
    db: AsyncIOMotorDatabase,
    device_id: str,
) -> str:
    """Return the current growth stage for a device, defaulting to vegetative if unset."""
    doc = await get_growth_stage_state(db, device_id)
    if not doc:
        return DEFAULT_GROWTH_STAGE
    return str(doc.get("current_growth_stage") or DEFAULT_GROWTH_STAGE)
