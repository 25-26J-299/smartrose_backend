"""Placeholder endpoints for INM model interactions."""

from fastapi import APIRouter

from app.ml.inm.inm_inference import predict

router = APIRouter()


@router.post("/predict", summary="Run INM prediction (stub)")
async def inm_predict(payload: dict) -> dict:
    """Invoke the INM stub prediction.

    TODO: Replace with real model inputs/outputs once INM model is integrated.
    """
    return predict(payload)

