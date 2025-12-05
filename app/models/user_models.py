"""Pydantic models for user authentication flows."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    """Payload for registering a new user."""

    name: str = Field(..., min_length=1, description="Full name of the user")
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        """Store emails in lowercase for uniqueness consistency."""
        return value.lower()


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
    name: str
    email: EmailStr
    password_hash: str
    roles: List[str] = Field(default_factory=list)
    created_at: datetime

    class Config:
        populate_by_name = True


class UserPublic(BaseModel):
    """Public-facing user data."""

    id: str = Field(..., alias="_id")
    name: str
    email: EmailStr
    roles: List[str] = Field(default_factory=list)
    created_at: datetime

    class Config:
        populate_by_name = True


class RoleUpdate(BaseModel):
    """Payload for updating user roles."""

    roles: List[str] = Field(
        ...,
        min_length=1,
        description='Accepts any combination of ["farmer", "florist"]',
    )

