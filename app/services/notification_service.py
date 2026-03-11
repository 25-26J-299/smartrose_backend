"""Notification service: in-app notifications only (MongoDB)."""

import logging
from typing import Any, Dict, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections import notifications as notifications_repo

logger = logging.getLogger(__name__)


async def create_notification(
    db: AsyncIOMotorDatabase,
    user_id: str,
    type: str,
    title: str,
    message: str,
    severity: str = "INFO",
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Insert a notification into MongoDB. In-app only; no push or email.

    Args:
        db: MongoDB database instance
        user_id: Owner user id (string)
        type: Module type — EOSM | EDAS | FM | INM
        title: Short title
        message: Body text
        severity: INFO | WARNING | HIGH
        metadata: Optional dict (e.g. device_id, greenhouse_id)

    Returns:
        Inserted notification id
    """
    notification_id = await notifications_repo.insert_notification(
        db=db,
        user_id=user_id,
        type_=type,
        title=title,
        message=message,
        severity=severity,
        metadata=metadata,
    )
    return notification_id
