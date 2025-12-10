"""Pydantic models for INM sensor data and predictions."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class INMSensorData(BaseModel):
    """Schema for INM sensor data input."""

    sensor_id: str = Field(..., description="Unique identifier for the sensor")
    temperature: float = Field(..., description="Temperature reading in Celsius")
    humidity: float = Field(..., description="Humidity percentage (0-100)")
    soil_moisture: float = Field(..., description="Soil moisture percentage (0-100)")
    timestamp: Optional[datetime] = Field(
        default=None, description="Reading timestamp (auto-set if not provided)"
    )


class INMSensorDataInDB(INMSensorData):
    """Schema for INM sensor data stored in MongoDB."""

    id: str = Field(..., alias="_id", description="MongoDB document ID")

    class Config:
        populate_by_name = True


class INMSensorDataUpdate(BaseModel):
    """Schema for updating INM sensor data (all fields optional)."""

    sensor_id: Optional[str] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    soil_moisture: Optional[float] = None
    timestamp: Optional[datetime] = None

