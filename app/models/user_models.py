"""Pydantic models for user authentication flows."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

ALLOWED_ROLES = {"admin", "farmer", "florist"}
ALLOWED_STATUSES = {"pending", "approved", "rejected"}


class UserCreate(BaseModel):
    """Payload for registering a new user."""

    full_name: str = Field(..., min_length=1, description="Full name of the user")
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=32)
    password: str = Field(..., min_length=6, max_length=72)
    role: str = Field(..., description="farmer | florist")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        """Store emails in lowercase for uniqueness consistency."""
        return value.lower()

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        r = v.lower()
        if r not in {"farmer", "florist"}:
            raise ValueError("role must be farmer or florist")
        return r


class UserLogin(BaseModel):
    """Payload for logging a user in."""

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.lower()


class UserInDB(BaseModel):
    """Internal representation of a user as stored in MongoDB."""

    id: str = Field(..., alias="_id")
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    password_hash: str
    role: str = "farmer"
    status: str = "pending"
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    is_active: bool = True

    class Config:
        populate_by_name = True


class UserPublic(BaseModel):
    """Public-facing user data."""

    id: str = Field(..., alias="_id")
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    role: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    is_active: bool

    class Config:
        populate_by_name = True


class RoleUpdate(BaseModel):
    """Payload for updating user role (admin)."""

    role: str = Field(..., description="admin | farmer | florist")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        r = v.lower()
        if r not in ALLOWED_ROLES:
            raise ValueError("role must be admin, farmer, or florist")
        return r


class StatusUpdate(BaseModel):
    """Payload for updating user status (admin)."""

    status: str = Field(..., description="pending | approved | rejected")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        s = v.lower()
        if s not in ALLOWED_STATUSES:
            raise ValueError("status must be pending, approved, or rejected")
        return s


# Legacy: for backward compatibility with update-roles endpoint
class RoleUpdateLegacy(BaseModel):
    """Payload for updating user roles (legacy)."""

    roles: List[str] = Field(
        ...,
        min_length=1,
        description='Accepts any combination of ["farmer", "florist"]',
    )
