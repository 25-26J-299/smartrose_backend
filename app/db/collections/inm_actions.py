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
    ec_action: str | None = None,
    ph_action: str | None = None,
    npk_recommendation: str | None = None,
    device_id: str = "",
    location_id: str = "",
    user_id: str = "",
    # Weather context – all optional so older call-sites are unaffected
    weather_condition: str | None = None,
    weather_temperature_c: float | None = None,
    weather_humidity_pct: float | None = None,
    weather_precipitation_mm: float | None = None,
    weather_advisory: str | None = None,
) -> dict:
    """Insert a new inm_actions document and return it (excluding _id).

    device_id, location_id, and user_id scope history per device / greenhouse /
    user in a multi-tenant setup. Weather fields record the environmental
    context at the moment the farmer made the apply/skip decision so the history
    view and future analytics can show why an application was postponed.
    """
    payload = {
        "timestamp": datetime.utcnow(),
        "recommendation_text": recommendation_text,
        "growth_stage": growth_stage,
        "action_taken": action_taken,
        "ec_action": ec_action,
        "ph_action": ph_action,
        "npk_recommendation": npk_recommendation,
        "device_id": device_id,
        "location_id": location_id,
        "user_id": user_id,
        # Store weather context when available
        "weather_condition": weather_condition,
        "weather_temperature_c": weather_temperature_c,
        "weather_humidity_pct": weather_humidity_pct,
        "weather_precipitation_mm": weather_precipitation_mm,
        "weather_advisory": weather_advisory,
    }
    result = await db[COLLECTION_NAME].insert_one(payload)
    logger.info(
        "INM action logged",
        extra={
            "collection": COLLECTION_NAME,
            "id": str(result.inserted_id),
            "device_id": device_id,
            "growth_stage": growth_stage,
            "action_taken": action_taken,
            "weather_advisory": weather_advisory,
        },
    )
    payload.pop("_id", None)
    return _serialize_timestamp(payload)


async def get_inm_action_history(db: AsyncIOMotorDatabase, limit: int = 50) -> list[dict]:
    """Return latest actions sorted by timestamp (descending), excluding _id."""
    cursor = db[COLLECTION_NAME].find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
    actions: list[dict] = []
    async for doc in cursor:
        actions.append(_serialize_timestamp(doc))
    logger.info(
        "INM action history fetched",
        extra={"collection": COLLECTION_NAME, "limit": limit, "count": len(actions)},
    )
    return actions


async def get_inm_action_history_by_device(
    db: AsyncIOMotorDatabase,
    device_id: str,
    limit: int = 50,
) -> list[dict]:
    """Return latest actions for a specific device, sorted by timestamp descending."""
    cursor = (
        db[COLLECTION_NAME]
        .find({"device_id": device_id}, {"_id": 0})
        .sort("timestamp", -1)
        .limit(limit)
    )
    actions: list[dict] = []
    async for doc in cursor:
        actions.append(_serialize_timestamp(doc))
    logger.info(
        "INM action history fetched by device",
        extra={"collection": COLLECTION_NAME, "device_id": device_id, "count": len(actions)},
    )
    return actions


