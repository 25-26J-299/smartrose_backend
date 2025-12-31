"""API endpoints for EOSM stress predictions."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.collections.eosm_predictions import (
    find_recent_predictions,
    get_latest_prediction,
    get_prediction_by_id,
)
from app.db.mongodb import get_db
from app.models.eosm_prediction_models import (
    EOSMStressPredictionRequest,
    EOSMStressPredictionResponse,
)
from app.services.eosm_ml_service import generate_stress_prediction
from app.utils.response_builder import success_response

# ================= eosm component start: Prediction endpoints =================

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/predict",
    summary="Generate stress prediction from sensor data",
    response_model=dict,
    tags=["eosm-predictions"],
)
async def predict_stress_endpoint(
    request: EOSMStressPredictionRequest,
    save_to_db: bool = Query(True, description="Save prediction to database"),
    db=Depends(get_db),
) -> dict:
    """Generate stress prediction from sensor readings using ML model.
    
    Args:
        request: Sensor reading data for prediction
        save_to_db: Whether to save the prediction to database
        db: MongoDB database instance
    
    Returns:
        Prediction result with stress_label and stress_probabilities
    """
    try:
        prediction = await generate_stress_prediction(
            request=request,
            db=db,
            basestation_id=request.basestation_id,
            greenhouse_id=request.greenhouse_id,
            save_to_db=save_to_db,
        )
        
        if prediction is None:
            raise HTTPException(
                status_code=502,
                detail="ML model prediction failed. Model may not be available.",
            )
        
        return success_response(
            message="Stress prediction generated successfully",
            data=prediction.model_dump(),
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to generate stress prediction")
        raise HTTPException(
            status_code=500,
            detail="Unable to generate stress prediction due to an error",
        ) from exc


@router.get(
    "/latest",
    summary="Get latest stress prediction",
    response_model=dict,
    tags=["eosm-predictions"],
)
async def get_latest_prediction_endpoint(
    basestation_id: Optional[str] = Query(None, alias="basestationId", description="Filter by base station ID"),
    greenhouse_id: Optional[str] = Query(None, alias="greenhouseId", description="Filter by greenhouse ID"),
    db=Depends(get_db),
) -> dict:
    """Get the latest stress prediction.
    
    Args:
        basestation_id: Filter by base station ID
        greenhouse_id: Filter by greenhouse ID
        db: MongoDB database instance
    
    Returns:
        Latest prediction document
    """
    try:
        prediction = await get_latest_prediction(
            db,
            basestation_id=basestation_id,
            greenhouse_id=greenhouse_id,
        )
        
        if prediction is None:
            raise HTTPException(
                status_code=404,
                detail="No predictions found",
            )
        
        return success_response(
            message="Latest prediction retrieved successfully",
            data=prediction,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to retrieve latest prediction")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve latest prediction due to an error",
        ) from exc


@router.get(
    "/",
    summary="List stress predictions",
    response_model=dict,
    tags=["eosm-predictions"],
)
async def list_predictions(
    limit: int = Query(20, ge=1, le=2000, description="Maximum number of records to return"),
    basestation_id: Optional[str] = Query(None, alias="basestationId", description="Filter by base station ID"),
    greenhouse_id: Optional[str] = Query(None, alias="greenhouseId", description="Filter by greenhouse ID"),
    start_date: Optional[str] = Query(None, alias="startDate", description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, alias="endDate", description="End date in YYYY-MM-DD format"),
    db=Depends(get_db),
) -> dict:
    """List stress predictions with optional filtering.
    
    Args:
        limit: Maximum number of records to return
        basestation_id: Filter by base station ID
        greenhouse_id: Filter by greenhouse ID
        start_date: Filter by start date (YYYY-MM-DD)
        end_date: Filter by end date (YYYY-MM-DD)
        db: MongoDB database instance
    
    Returns:
        List of prediction documents
    """
    try:
        from datetime import datetime, timezone
        
        start_timestamp = None
        end_timestamp = None
        
        if start_date:
            try:
                dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                start_timestamp = int(dt.timestamp())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid startDate format. Expected YYYY-MM-DD, got: {start_date}",
                )
        
        if end_date:
            try:
                dt = datetime.strptime(end_date, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, tzinfo=timezone.utc
                )
                end_timestamp = int(dt.timestamp())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid endDate format. Expected YYYY-MM-DD, got: {end_date}",
                )
        
        predictions = await find_recent_predictions(
            db,
            limit=limit,
            basestation_id=basestation_id,
            greenhouse_id=greenhouse_id,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
        )
        
        return success_response(
            message="Predictions retrieved successfully",
            data={"items": predictions},
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to list predictions")
        raise HTTPException(
            status_code=500,
            detail="Unable to list predictions due to an error",
        ) from exc


@router.get(
    "/{prediction_id}",
    summary="Get stress prediction by ID",
    response_model=dict,
    tags=["eosm-predictions"],
)
async def get_prediction_by_id_endpoint(
    prediction_id: str,
    db=Depends(get_db),
) -> dict:
    """Get a stress prediction by its ID.
    
    Args:
        prediction_id: Prediction document ID
        db: MongoDB database instance
    
    Returns:
        Prediction document
    """
    try:
        prediction = await get_prediction_by_id(db, prediction_id)
        
        if prediction is None:
            raise HTTPException(
                status_code=404,
                detail=f"Prediction with id '{prediction_id}' not found",
            )
        
        return success_response(
            message="Prediction retrieved successfully",
            data=prediction,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to retrieve prediction by ID")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve prediction due to an error",
        ) from exc

# ================= eosm component end =================


