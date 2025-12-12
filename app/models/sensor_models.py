"""Pydantic models that describe sensor payloads."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, constr


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


class LoRaSensorIngest(BaseModel):
    """Payload shape for LoRa gateway JSON ingestion."""
    # ================= eosm component start: LoRa gateway payload contract =================

    model_config = ConfigDict(populate_by_name=True)

    basestation_id: constr(strip_whitespace=True, min_length=1) = Field(
        ..., alias="basestationId", description="Gateway/base-station identifier"
    )
    greenhouse_id: constr(strip_whitespace=True, min_length=1) = Field(
        ..., alias="greenhouseId", description="Greenhouse identifier"
    )
    timestamp: int = Field(
        ...,
        ge=0,
        description="Epoch timestamp reported by the gateway",
    )
    temperature: float = Field(..., description="Temperature reading in Celsius")
    humidity: float = Field(
        ..., ge=0, le=100, description="Relative humidity percentage (0-100%)"
    )
    uv_raw: int = Field(
        ..., alias="uvRaw", ge=0, description="Raw UV ADC count from the gateway"
    )
    uv_voltage: float = Field(
        ..., alias="uvVoltage", ge=0, description="UV sensor voltage reading"
    )
    soil_raw: int = Field(
        ..., alias="soilRaw", ge=0, description="Raw soil moisture ADC count"
    )
    soil_voltage: float = Field(
        ..., alias="soilVoltage", ge=0, description="Soil moisture voltage reading"
    )
    mq_raw: int = Field(
        ..., alias="mqRaw", ge=0, description="Raw gas sensor ADC count"
    )
    mq_voltage: float = Field(
        ..., alias="mqVoltage", ge=0, description="Gas sensor voltage reading"
    )
    # ================= eosm component end =================

