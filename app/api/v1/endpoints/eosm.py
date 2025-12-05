"""Placeholder endpoints for EOSM model interactions."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/", summary="EOSM prediction endpoint placeholder")
async def eosm_placeholder() -> dict:
    """Placeholder response until the EOSM model is integrated."""
    return {"detail": "EOSM endpoint TODO: wire model inference"}

