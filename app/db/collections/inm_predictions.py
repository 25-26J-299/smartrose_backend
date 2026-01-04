"""Data access helpers for the inm_predictions collection.

Stores persisted INM status outputs (ML prediction + recommendations) for history/audit.
This is logging only and does not affect ML or recommendations.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

COLLECTION_NAME = "inm_predictions"


def _serialize_timestamp(doc: dict) -> dict:
    ts = doc.get("timestamp")
    if isinstance(ts, datetime):
        doc["timestamp"] = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    return doc


async def create_inm_prediction(db: AsyncIOMotorDatabase, payload: Dict[str, Any]) -> str:
    """Insert an INM prediction/status record and return inserted id."""
    payload = dict(payload)
    payload["timestamp"] = datetime.utcnow()
    result = await db[COLLECTION_NAME].insert_one(payload)
    logger.info(
        "INM prediction saved",
        extra={"collection": COLLECTION_NAME, "id": str(result.inserted_id)},
    )
    return str(result.inserted_id)


async def get_recent_inm_predictions(db: AsyncIOMotorDatabase, limit: int = 50) -> List[Dict[str, Any]]:
    """Return latest INM predictions sorted by timestamp desc."""
    cursor = db[COLLECTION_NAME].find().sort([("timestamp", -1), ("_id", -1)]).limit(max(1, limit))
    docs = await cursor.to_list(length=limit)
    for doc in docs:
        doc["_id"] = str(doc.get("_id"))
        _serialize_timestamp(doc)
    return docs

