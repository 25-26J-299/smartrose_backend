"""Pydantic models for the Freshness Monitoring component."""

from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class FMSensorInput(BaseModel):
    temperature: float
    humidity: float
    gas_value: float
    water_level: int
    device_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v):
        """Handle timestamp from ESP32 which may send Unix timestamp or ISO string."""
        if v is None:
            return datetime.utcnow()
        
        # If it's already a datetime object, return as-is
        if isinstance(v, datetime):
            return v
        
        # If it's a Unix timestamp (integer or float)
        if isinstance(v, (int, float)):
            return datetime.utcfromtimestamp(v)
        
        # If it's a string, try to parse it
        if isinstance(v, str):
            # Try ISO format first
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                # Try Unix timestamp as string
                try:
                    return datetime.utcfromtimestamp(float(v))
                except (ValueError, TypeError):
                    # If all parsing fails, use current time
                    return datetime.utcnow()
        
        # Default to current time if we can't parse
        return datetime.utcnow()


class FMSensorDB(FMSensorInput):
    id: Optional[str]


class FMPredictionResponse(BaseModel):
    freshness_score: float
    vase_life_hours: float
    alerts: List[str] = []
