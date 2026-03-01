"""Pydantic models for device management."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

DEVICE_TYPES = {"INM", "EOSM", "EDAS", "FM"}


class DeviceCreate(BaseModel):
    """Payload for creating a device."""

    location_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    type: str = Field(..., description="INM | EOSM | EDAS | FM")
    device_serial_number: str = Field(..., min_length=1)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        t = v.upper()
        if t not in DEVICE_TYPES:
            raise ValueError("type must be INM, EOSM, EDAS, or FM")
        return t


class DeviceUpdate(BaseModel):
    """Payload for updating a device. Partial update."""

    name: Optional[str] = Field(None, min_length=1)
    type: Optional[str] = Field(None, description="INM | EOSM | EDAS | FM")
    device_serial_number: Optional[str] = Field(None, min_length=1)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        t = v.upper()
        if t not in DEVICE_TYPES:
            raise ValueError("type must be INM, EOSM, EDAS, or FM")
        return t
