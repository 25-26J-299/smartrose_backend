"""Placeholder endpoints for EDAS model interactions."""

from fastapi import APIRouter

from app.ml.edas.edas_inference import predict

router = APIRouter()


@router.post("/predict", summary="Run EDAS prediction (stub)")
async def edas_predict(payload: dict) -> dict:
    """Invoke the EDAS stub prediction.

    TODO: Replace with real model inputs/outputs once EDAS model is integrated.
    """
    return predict(payload)

