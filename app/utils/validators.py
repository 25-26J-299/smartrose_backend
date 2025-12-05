"""Reusable validation helpers."""

from fastapi import HTTPException


def ensure_positive(value: float, field_name: str) -> float:
    """Ensure numeric values are positive; raise HTTPException if not."""
    if value < 0:
        raise HTTPException(
            status_code=422, detail=f"{field_name} must be greater than zero"
        )
    return value

