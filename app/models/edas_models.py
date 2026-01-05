from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class EDASSensorData(BaseModel):


    device_id: str = Field(
        ..., 
        description="Unique identifier for the ESP32/IoT device",
        min_length=1
    )
    plant_temperature: float = Field(
        ...,
        ge=-50,
        le=150,
        description="Rose plant temperature in Celsius (MLX90614 sensor)",
    )
    air_temperature: float = Field(
        ...,
        ge=-50,
        le=150,
        description="Air temperature in Celsius (SHT31 sensor)",
    )
    humidity: float = Field(
        ...,
        ge=0,
        le=100,
        description="Relative humidity percentage (0-100%) (SHT31 sensor)",
    )
    temperature_difference: Optional[float] = Field(
        None,
        description="Calculated difference: plant_temperature - air_temperature (auto-calculated)",
    )
    timestamp: Optional[datetime] = Field(
        None,
        description="Reading timestamp (auto-set by backend if not provided)",
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v):

        if v is None:
            return None
        
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
                    # If all parsing fails, return None (backend will set it)
                    return None
        
        # Default to None if we can't parse
        return None


class EDASSensorDataInDB(EDASSensorData):


    id: str = Field(..., alias="_id", description="MongoDB document ID")

    class Config:
        populate_by_name = True


class EDASSensorDataUpdate(BaseModel):


    device_id: Optional[str] = None
    plant_temperature: Optional[float] = None
    air_temperature: Optional[float] = None
    humidity: Optional[float] = None
    temperature_difference: Optional[float] = None
    timestamp: Optional[datetime] = None


class EDASSensorDataResponse(BaseModel):


    id: Optional[str] = Field(None, alias="_id")
    device_id: str
    plant_temperature: float
    air_temperature: float
    humidity: float
    temperature_difference: float
    timestamp: datetime

    class Config:
        populate_by_name = True
