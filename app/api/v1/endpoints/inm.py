"""Placeholder endpoints for INM model interactions."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/", summary="INM prediction endpoint placeholder")
async def inm_placeholder() -> dict:
    """Placeholder response until the INM model is integrated."""
    return {"detail": "INM endpoint TODO: wire model inference"}

