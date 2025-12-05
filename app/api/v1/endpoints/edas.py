"""Placeholder endpoints for EDAS model interactions."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/", summary="EDAS prediction endpoint placeholder")
async def edas_placeholder() -> dict:
    """Placeholder response until the EDAS model is integrated."""
    return {"detail": "EDAS endpoint TODO: wire model inference"}

