"""Pydantic models for the Freshness Monitoring component."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class FMSensorInput(BaseModel):
    temperature: float
    humidity: float
    gas_value: float
    water_level: int
    device_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FMSensorDB(FMSensorInput):
    id: Optional[str]


class FMPredictionResponse(BaseModel):
    freshness_score: float
    vase_life_hours: float
    alerts: List[str] = []
