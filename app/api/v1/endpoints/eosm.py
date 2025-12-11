"""Placeholder endpoints for EOSM model interactions."""

from fastapi import APIRouter

from app.ml.eosm.eosm_inference import predict

router = APIRouter()


@router.post("/predict", summary="Run EOSM prediction (stub)")
async def eosm_predict(payload: dict) -> dict:
    """Invoke the EOSM stub prediction.

    TODO: Replace with real model inputs/outputs once eosm_model.pkl is wired.
    """
    return predict(payload)

