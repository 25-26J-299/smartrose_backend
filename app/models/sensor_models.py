"""Pydantic models that describe sensor payloads."""

from datetime import datetime

from pydantic import BaseModel, Field, constr


class SensorData(BaseModel):
    """Payload shape for incoming sensor readings."""

    # Keep sensor id non-empty to avoid silent ingestion of anonymous devices.
    sensor_id: constr(strip_whitespace=True, min_length=1) = Field(
        ..., description="Unique hardware identifier"
    )
    # Basic physical sanity checks; can be tightened as domain knowledge improves.
    temperature: float = Field(
        ...,
        ge=-100,
        le=150,
        description="Temperature reading in Celsius",
    )
    humidity: float = Field(
        ...,
        ge=0,
        le=100,
        description="Relative humidity percentage (0-100%)",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the reading was taken",
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

