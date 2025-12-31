"""Data access helpers for the eosm_predictions collection."""

import logging
from typing import Dict, List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

# ================= eosm component start: Predictions collection =================

COLLECTION_NAME = "eosm_predictions"
logger = logging.getLogger(__name__)


async def insert_stress_prediction(
    db: AsyncIOMotorDatabase, payload: Dict
) -> str:
    """Insert a stress prediction and return the inserted document id.
    
    Args:
        db: MongoDB database instance
        payload: Prediction data dictionary
    
    Returns:
        Inserted document ID as string
    """
    try:
        result = await db[COLLECTION_NAME].insert_one(payload)
        logger.info(
            "EOSM stress prediction created",
            extra={"collection": COLLECTION_NAME, "id": str(result.inserted_id)},
        )
        return str(result.inserted_id)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to insert EOSM stress prediction",
            extra={"collection": COLLECTION_NAME},
        )
        raise


async def find_recent_predictions(
    db: AsyncIOMotorDatabase,
    limit: int = 20,
    basestation_id: Optional[str] = None,
    greenhouse_id: Optional[str] = None,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
) -> List[Dict]:
    """Find recent stress predictions with optional filtering.
    
    Args:
        db: MongoDB database instance
        limit: Maximum number of records to return
        basestation_id: Filter by base station ID
        greenhouse_id: Filter by greenhouse ID
        start_timestamp: Filter by start timestamp (epoch seconds)
        end_timestamp: Filter by end timestamp (epoch seconds)
    
    Returns:
        List of prediction documents
    """
    try:
        query: Dict = {}
        
        if basestation_id:
            query["basestation_id"] = basestation_id
        if greenhouse_id:
            query["greenhouse_id"] = greenhouse_id
        
        if start_timestamp is not None or end_timestamp is not None:
            timestamp_query: Dict = {}
            if start_timestamp is not None:
                timestamp_query["$gte"] = start_timestamp
            if end_timestamp is not None:
                timestamp_query["$lte"] = end_timestamp
            if timestamp_query:
                query["timestamp"] = timestamp_query
        
        cursor = (
            db[COLLECTION_NAME]
            .find(query)
            .sort([("timestamp", -1), ("_id", -1)])
            .limit(max(1, limit))
        )
        docs = await cursor.to_list(length=limit)
        
        for doc in docs:
            doc["_id"] = str(doc.get("_id"))
        
        return docs
    except Exception:  # noqa: BLE001
        logger.exception("Failed to find EOSM stress predictions")
        raise


async def get_prediction_by_id(
    db: AsyncIOMotorDatabase, prediction_id: str
) -> Optional[Dict]:
    """Get a stress prediction by its ID.
    
    Args:
        db: MongoDB database instance
        prediction_id: Prediction document ID
    
    Returns:
        Prediction document or None if not found
    """
    try:
        doc = await db[COLLECTION_NAME].find_one({"_id": ObjectId(prediction_id)})
        if doc:
            doc["_id"] = str(doc.get("_id"))
        return doc
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to get EOSM stress prediction by ID",
            extra={"prediction_id": prediction_id},
        )
        return None


async def get_latest_prediction(
    db: AsyncIOMotorDatabase,
    basestation_id: Optional[str] = None,
    greenhouse_id: Optional[str] = None,
) -> Optional[Dict]:
    """Get the latest stress prediction.
    
    Args:
        db: MongoDB database instance
        basestation_id: Filter by base station ID
        greenhouse_id: Filter by greenhouse ID
    
    Returns:
        Latest prediction document or None if not found
    """
    try:
        query: Dict = {}
        
        if basestation_id:
            query["basestation_id"] = basestation_id
        if greenhouse_id:
            query["greenhouse_id"] = greenhouse_id
        
        doc = await (
            db[COLLECTION_NAME]
            .find(query)
            .sort([("timestamp", -1), ("_id", -1)])
            .limit(1)
            .to_list(length=1)
        )
        
        if doc and len(doc) > 0:
            doc[0]["_id"] = str(doc[0].get("_id"))
            return doc[0]
        
        return None
    except Exception:  # noqa: BLE001
        logger.exception("Failed to get latest EOSM stress prediction")
        return None

# ================= eosm component end =================


