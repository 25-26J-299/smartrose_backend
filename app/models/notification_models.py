"""Pydantic models for notifications."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

NOTIFICATION_TYPES = ("EOSM", "EDAS", "FM", "INM")
SEVERITY_LEVELS = ("INFO", "WARNING", "HIGH")


class NotificationCreate(BaseModel):
    """Payload for creating a notification (service input)."""

    user_id: str = Field(..., description="User ID (owner)")
    type: str = Field(..., description="Module type: EOSM | EDAS | FM | INM")
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    severity: str = Field(default="INFO", description="INFO | WARNING | HIGH")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional metadata")


class NotificationResponse(BaseModel):
    """Notification as returned by the API."""

    id: str = Field(..., description="Notification ID")
    user_id: str = Field(..., description="User ID")
    type: str = Field(..., description="EOSM | EDAS | FM | INM")
    title: str = Field(..., description="Title")
    message: str = Field(..., description="Message")
    severity: str = Field(..., description="INFO | WARNING | HIGH")
    is_read: bool = Field(..., description="Whether the user has read it")
    created_at: str = Field(..., description="ISO datetime")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional metadata")
