"""Data access helpers for the edas_predictions collection."""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

# ================= edas component start: Predictions collection =================

COLLECTION_NAME = "edas_predictions"
logger = logging.getLogger(__name__)


async def insert_disease_prediction(
    db: AsyncIOMotorDatabase, payload: Dict
) -> str:
    """Insert a disease risk prediction and return the inserted document id.
    
    Args:
        db: MongoDB database instance
        payload: Prediction data dictionary
    
    Returns:
        Inserted document ID as string
    """
    try:
        result = await db[COLLECTION_NAME].insert_one(payload)
        logger.info(
            "EDAS disease prediction created",
            extra={"collection": COLLECTION_NAME, "id": str(result.inserted_id)},
        )
        return str(result.inserted_id)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to insert EDAS disease prediction",
            extra={"collection": COLLECTION_NAME},
        )
        raise


async def find_recent_predictions(
    db: AsyncIOMotorDatabase,
    limit: int = 20,
    device_id: Optional[str] = None,
    start_timestamp: Optional[datetime] = None,
    end_timestamp: Optional[datetime] = None,
) -> List[Dict]:
    """Find recent disease predictions with optional filtering.
    
    Args:
        db: MongoDB database instance
        limit: Maximum number of records to return
        device_id: Filter by device ID
        start_timestamp: Filter by start timestamp
        end_timestamp: Filter by end timestamp
    
    Returns:
        List of prediction documents
    """
    try:
        query: Dict = {}
        
        if device_id:
            query["device_id"] = device_id
        
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
        logger.exception("Failed to find EDAS disease predictions")
        raise


async def get_prediction_by_id(
    db: AsyncIOMotorDatabase, prediction_id: str
) -> Optional[Dict]:
    """Get a disease prediction by its ID.
    
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
            "Failed to get EDAS disease prediction by ID",
            extra={"prediction_id": prediction_id},
        )
        return None


async def get_latest_prediction(
    db: AsyncIOMotorDatabase,
    device_id: Optional[str] = None,
) -> Optional[Dict]:
    """Get the latest disease prediction.
    
    Args:
        db: MongoDB database instance
        device_id: Filter by device ID
    
    Returns:
        Latest prediction document or None if not found
    """
    try:
        query: Dict = {}
        
        if device_id:
            query["device_id"] = device_id
        
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
        logger.exception("Failed to get latest EDAS disease prediction")
        return None

# ================= edas component end =================
