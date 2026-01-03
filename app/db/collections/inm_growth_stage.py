"""MongoDB helpers for persistent INM growth stage state.

We store the current growth stage as a singleton document so there is only
one active stage at any time.

Document shape:
{
  "_id": "current_growth_stage",
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
SINGLETON_ID = "current_growth_stage"
DEFAULT_GROWTH_STAGE = "vegetative"


async def set_current_growth_stage(db: AsyncIOMotorDatabase, growth_stage: str) -> dict:
    """Create or overwrite the singleton growth stage state document."""
    now = datetime.utcnow()
    doc = await db[COLLECTION_NAME].find_one_and_update(
        {"_id": SINGLETON_ID},
        {"$set": {"current_growth_stage": growth_stage, "updated_at": now}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )

    # Should always exist due to upsert=True, but guard anyway
    if doc is None:
        doc = {"_id": SINGLETON_ID, "current_growth_stage": growth_stage, "updated_at": now}

    doc["_id"] = str(doc["_id"])
    logger.info(
        "Growth stage updated",
        extra={"collection": COLLECTION_NAME, "growth_stage": growth_stage},
    )
    return doc


async def get_growth_stage_state(db: AsyncIOMotorDatabase) -> Optional[dict]:
    """Fetch the singleton growth stage state document, if it exists."""
    doc = await db[COLLECTION_NAME].find_one({"_id": SINGLETON_ID})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def get_current_growth_stage(db: AsyncIOMotorDatabase) -> str:
    """Return the current growth stage, defaulting to vegetative if unset."""
    doc = await get_growth_stage_state(db)
    if not doc:
        return DEFAULT_GROWTH_STAGE
    return str(doc.get("current_growth_stage") or DEFAULT_GROWTH_STAGE)


