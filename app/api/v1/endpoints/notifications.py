"""Notification API: list, mark read, clear."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user
from app.db.collections import notifications as notifications_repo
from app.db.mongodb import get_db
from app.utils.response_builder import success_response

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/",
    summary="List notifications for the authenticated user",
    response_model=dict,
    tags=["notifications"],
)
async def list_notifications(
    type: Optional[str] = Query(None, description="Filter by type: EOSM | EDAS | FM | INM"),
    limit: int = Query(100, ge=1, le=500, description="Max number of notifications"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Return notifications for the authenticated user. Newest first."""
    user_id = str(current_user["_id"])
    items = await notifications_repo.find_by_user(db, user_id=user_id, type_=type, limit=limit)
    return success_response(message="ok", data={"notifications": items})


@router.patch(
    "/{notification_id}/read",
    summary="Mark a notification as read",
    response_model=dict,
    tags=["notifications"],
)
async def mark_notification_read(
    notification_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Mark the given notification as read. User must own the notification."""
    user_id = str(current_user["_id"])
    updated = await notifications_repo.mark_as_read(db, notification_id, user_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or already read",
        )
    return success_response(message="Notification marked as read", data={"id": notification_id})


@router.patch(
    "/read-all",
    summary="Mark all notifications as read",
    response_model=dict,
    tags=["notifications"],
)
async def mark_all_read(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Mark all notifications for the authenticated user as read."""
    user_id = str(current_user["_id"])
    count = await notifications_repo.mark_all_as_read(db, user_id)
    return success_response(
        message="All notifications marked as read",
        data={"updated_count": count},
    )


@router.delete(
    "/clear",
    summary="Delete all notifications for the user",
    response_model=dict,
    tags=["notifications"],
)
async def clear_notifications(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Delete all notifications for the authenticated user."""
    user_id = str(current_user["_id"])
    count = await notifications_repo.delete_all_by_user(db, user_id)
    return success_response(
        message="All notifications cleared",
        data={"deleted_count": count},
    )
