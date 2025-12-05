"""Placeholder endpoints for FM model interactions."""

from fastapi import APIRouter

from app.ml.fm.fm_inference import predict

router = APIRouter()


@router.post("/predict", summary="Run FM prediction (stub)")
async def fm_predict(payload: dict) -> dict:
    """Invoke the FM stub prediction.

    TODO: Replace with real model inputs/outputs once FM model is integrated.
    """
    return predict(payload)

