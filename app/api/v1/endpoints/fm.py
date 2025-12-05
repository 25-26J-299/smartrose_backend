"""Placeholder endpoints for FM model interactions."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/", summary="FM prediction endpoint placeholder")
async def fm_placeholder() -> dict:
    """Placeholder response until the FM model is integrated."""
    return {"detail": "FM endpoint TODO: wire model inference"}

