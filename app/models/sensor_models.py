"""Pydantic models that describe sensor payloads."""

from datetime import datetime

from pydantic import BaseModel, Field


class SensorData(BaseModel):
    """Payload shape for incoming sensor readings."""

    sensor_id: str = Field(..., description="Unique hardware identifier")
    temperature: float = Field(..., description="Temperature reading in Celsius")
    humidity: float = Field(..., description="Relative humidity percentage")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the reading was taken",
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

