"""Data access helpers for the inm_actions collection.

This collection stores human-in-the-loop feedback about whether a farmer
applied or ignored a given INM recommendation. This is logging only and does
not affect recommendations or ML.
"""

import logging
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

COLLECTION_NAME = "inm_actions"


def _serialize_timestamp(doc: dict) -> dict:
    """Ensure timestamp is JSON-serializable in a consistent UTC ISO format."""
    ts = doc.get("timestamp")
    if isinstance(ts, datetime):
        doc["timestamp"] = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    return doc


async def create_inm_action(
    db: AsyncIOMotorDatabase,
    recommendation_text: str,
    growth_stage: str,
    action_taken: str,
) -> dict:
    """Insert a new inm_actions document and return it (excluding _id)."""
    payload = {
        "timestamp": datetime.utcnow(),
        "recommendation_text": recommendation_text,
        "growth_stage": growth_stage,
        "action_taken": action_taken,
    }
    result = await db[COLLECTION_NAME].insert_one(payload)
    logger.info(
        "INM action logged",
        extra={"collection": COLLECTION_NAME, "id": str(result.inserted_id)},
    )
    payload.pop("_id", None)
    return _serialize_timestamp(payload)


async def get_inm_action_history(db: AsyncIOMotorDatabase, limit: int = 50) -> list[dict]:
    """Return latest actions sorted by timestamp (descending), excluding _id."""
    cursor = db[COLLECTION_NAME].find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
    actions: list[dict] = []
    async for doc in cursor:
        actions.append(_serialize_timestamp(doc))
    return actions


