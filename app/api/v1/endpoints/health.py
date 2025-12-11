"""Database health check endpoint.

This lets operators quickly verify Mongo connectivity without hitting ingest
paths. Kept lightweight to run even when other services are degraded.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.db.mongodb import get_database

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/db-health/", summary="Check MongoDB connectivity")
async def db_health() -> dict:
    """Ping MongoDB; return status depending on connectivity."""
    db = get_database()
    try:
        await db.command({"ping": 1})
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("MongoDB health check failed")
        raise HTTPException(
            status_code=503,
            detail={"status": "error", "reason": str(exc)},
        )

