"""Pydantic models for the Freshness Monitoring component."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


class FMSensorInput(BaseModel):
    air_temperature: float
    humidity: float
    gas_value: float
    water_level: int
    water_temperature: float = Field(default=20.0, description="Water temperature in Celsius. Defaults to 20.0 if not provided.")
    device_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="before")
    @classmethod
    def handle_legacy_temperature_field(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # If old 'temperature' field exists but not 'air_temperature'
            if "temperature" in data and "air_temperature" not in data:
                data["air_temperature"] = data["temperature"]
                # If water_temperature also not provided, use same value
                if "water_temperature" not in data:
                    data["water_temperature"] = data["temperature"]
        return data

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


class FMUploadResponse(BaseModel):
    """Response body for POST /fm/upload (ESP32 + clients)."""

    message: str = "saved"
    id: str
    prediction_id: str
    freshness_score: float
    replace_water: bool
