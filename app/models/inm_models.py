"""Pydantic models for INM sensor data and predictions."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict

from app.services.inm_service import GrowthStage


class INMSensorData(BaseModel):
    """Schema for full ESP32 INM sensor data input (NPK + pH + EC + soil + air)."""

    device_id: str = Field(..., description="Unique identifier for the ESP32 device")
    soil_moisture: float = Field(..., description="Soil moisture percentage")
    soil_temp: float = Field(..., description="Soil temperature in Celsius")
    ec: float = Field(..., ge=0, description="Electrical conductivity (µS/cm)")
    ph: float = Field(..., ge=0, le=14, description="Soil pH level (0-14)")
    N: float = Field(..., ge=0, description="Nitrogen content (mg/kg)")
    P: float = Field(..., ge=0, description="Phosphorus content (mg/kg)")
    K: float = Field(..., ge=0, description="Potassium content (mg/kg)")
    air_temp: float = Field(..., description="Air temperature in Celsius")
    air_hum: float = Field(..., description="Air humidity percentage")
    timestamp: Optional[datetime] = Field(
        default=None, description="Reading timestamp (auto-set by backend)"
    )


class INMSensorDataInDB(INMSensorData):
    """Schema for INM sensor data stored in MongoDB."""

    id: str = Field(..., alias="_id", description="MongoDB document ID")

    class Config:
        populate_by_name = True


class INMSensorDataUpdate(BaseModel):
    """Schema for updating INM sensor data (all fields optional)."""

    device_id: Optional[str] = None
    soil_moisture: Optional[float] = None
    soil_temp: Optional[float] = None
    ec: Optional[float] = Field(default=None, ge=0)
    ph: Optional[float] = Field(default=None, ge=0, le=14)
    N: Optional[float] = Field(default=None, ge=0)
    P: Optional[float] = Field(default=None, ge=0)
    K: Optional[float] = Field(default=None, ge=0)
    air_temp: Optional[float] = None
    air_hum: Optional[float] = None
    timestamp: Optional[datetime] = None


class GrowthStageUpdateRequest(BaseModel):
    """Request schema for setting the persistent growth stage state."""

    model_config = ConfigDict(populate_by_name=True)

    # Accept both `growth_stage` and common camelCase `growthStage` from clients.
    growth_stage: GrowthStage = Field(
        ...,
        alias="growthStage",
        description="Current growth stage context set by farmer",
    )

