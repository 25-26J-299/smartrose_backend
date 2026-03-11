from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class EDASSensorData(BaseModel):
    """Schema for EDAS sensor data input from IoT devices.
    
    This model represents the raw sensor readings from the IoT system.
    Time-based fields (hour, is_day, time_period) are automatically calculated
    by the backend and should NOT be sent from Arduino/ESP32.
    """

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
    location_id: Optional[str] = Field(
        None,
        description="Greenhouse (location) this device belongs to (auto-populated by backend)",
    )
    user_id: Optional[str] = Field(
        None,
        description="Owner user ID (auto-populated by backend from device registry)",
    )
    temperature_difference: Optional[float] = Field(
        None,
        description="Calculated difference: plant_temperature - air_temperature (auto-calculated)",
    )
    timestamp: Optional[datetime] = Field(
        None,
        description="Reading timestamp (auto-set by backend if not provided)",
    )
    
    # ============================================================================
    # ML Time-Based Features (Auto-calculated by backend, DO NOT send from IoT)
    # ============================================================================
    hour: Optional[int] = Field(
        None,
        ge=0,
        le=23,
        description="Hour of day extracted from timestamp (0-23) - Auto-calculated for ML",
    )
    is_day: Optional[bool] = Field(
        None,
        description="Day/night indicator: True if 06:00-18:00, False otherwise - Auto-calculated for ML",
    )
    time_period: Optional[Literal["morning", "noon", "evening", "night"]] = Field(
        None,
        description="Time period classification for ML patterns - Auto-calculated for ML",
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
    """Schema for updating EDAS sensor data (all fields optional).
    
    This model is used for partial updates to existing sensor readings.
    In practice, sensor data is typically immutable, but this is provided
    for administrative corrections if needed.
    """

    device_id: Optional[str] = None
    location_id: Optional[str] = None
    user_id: Optional[str] = None
    plant_temperature: Optional[float] = None
    air_temperature: Optional[float] = None
    humidity: Optional[float] = None
    temperature_difference: Optional[float] = None
    timestamp: Optional[datetime] = None
    hour: Optional[int] = None
    is_day: Optional[bool] = None
    time_period: Optional[Literal["morning", "noon", "evening", "night"]] = None


class EDASSensorDataResponse(BaseModel):
    """Schema for EDAS sensor data API responses.
    
    This model includes all fields including ML time-based features.
    """

    id: Optional[str] = Field(None, alias="_id")
    device_id: str
    location_id: Optional[str] = None
    user_id: Optional[str] = None
    plant_temperature: float
    air_temperature: float
    humidity: float
    temperature_difference: float
    timestamp: datetime
    hour: int
    is_day: bool
    time_period: Literal["morning", "noon", "evening", "night"]

    class Config:
        populate_by_name = True
