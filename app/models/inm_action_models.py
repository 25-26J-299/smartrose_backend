"""Pydantic models for INM human-in-the-loop action logging."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class INMActionCreate(BaseModel):
    """Client payload to log whether a recommendation was applied or ignored."""

    device_id: str = Field(..., description="Device ID the recommendation was generated for")
    recommendation_text: str = Field(..., description="Recommendation text shown to farmer")
    action_taken: Literal["applied", "ignored"] = Field(
        ..., description="Farmer feedback on whether the recommendation was applied or ignored"
    )


class INMActionInDB(INMActionCreate):
    """Action log document returned to clients (no _id exposed)."""

    growth_stage: str = Field(..., description="Growth stage context when action was logged")
    location_id: str = Field(default="", description="Greenhouse location ID")
    user_id: str = Field(default="", description="User who logged the action")
    timestamp: datetime = Field(..., description="UTC timestamp when action was logged")
