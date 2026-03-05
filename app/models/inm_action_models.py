"""Pydantic models for INM human-in-the-loop action logging."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class INMActionCreate(BaseModel):
    """Client payload to log whether a recommendation was applied or ignored."""

    device_id: str = Field(..., description="Device ID the recommendation was generated for")
    recommendation_text: str = Field(..., description="Recommendation text shown to farmer")
    action_taken: Literal["applied", "ignored"] = Field(
        ..., description="Farmer feedback on whether the recommendation was applied or ignored"
    )

    # Weather context at the moment the farmer made the decision.
    # All fields are optional so existing clients are not broken.
    weather_condition: Optional[str] = Field(
        None, description="OpenWeatherMap condition string, e.g. 'Rain', 'Clear'"
    )
    weather_temperature_c: Optional[float] = Field(
        None, description="Air temperature in °C at time of action"
    )
    weather_humidity_pct: Optional[float] = Field(
        None, description="Relative humidity percentage at time of action"
    )
    weather_precipitation_mm: Optional[float] = Field(
        None, description="Precipitation in mm (1 h or 3 h) at time of action"
    )
    weather_advisory: Optional[Literal["good", "caution", "postpone"]] = Field(
        None,
        description="Advisory level computed on the device: good / caution / postpone",
    )


class INMActionInDB(INMActionCreate):
    """Action log document returned to clients (no _id exposed)."""

    growth_stage: str = Field(..., description="Growth stage context when action was logged")
    location_id: str = Field(default="", description="Greenhouse location ID")
    user_id: str = Field(default="", description="User who logged the action")
    timestamp: datetime = Field(..., description="UTC timestamp when action was logged")
