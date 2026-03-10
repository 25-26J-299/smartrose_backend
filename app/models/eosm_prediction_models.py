"""Pydantic models for EOSM stress predictions."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

# ================= eosm component start: Prediction models =================


class EOSMStressPredictionRequest(BaseModel):
    """Request model for stress prediction."""

    temperature: float = Field(..., description="Temperature in Celsius")
    humidity: float = Field(..., ge=0, le=100, description="Humidity percentage (0-100)")
    soil_voltage: float = Field(..., ge=0, description="Soil moisture sensor voltage")
    uv_voltage: float = Field(..., ge=0, description="UV sensor voltage")
    mq_voltage: float = Field(..., ge=0, description="Gas sensor (MQ) voltage")
    device_id: Optional[str] = Field(None, description="Device serial (e.g. SR-EOSM-20250310)")


class EOSMStressPredictionResponse(BaseModel):
    """Response model for stress prediction."""

    stress_label: str = Field(..., description="Stress label: HIGH, MEDIUM, or LOW")
    stress_probabilities: dict = Field(..., description="Probabilities for each stress level")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Prediction timestamp")


class EOSMStressPredictionInDB(EOSMStressPredictionResponse):
    """Schema for stress prediction stored in MongoDB."""

    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")
    device_id: Optional[str] = Field(None, description="Device serial (e.g. SR-EOSM-20250310)")
    sensor_reading_id: Optional[str] = Field(None, description="Associated sensor reading ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation timestamp")

# ================= eosm component end =================


