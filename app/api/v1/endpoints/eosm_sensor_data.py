"""Endpoints for ingesting eosm LoRa sensor readings."""

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections.eosm_readings import find_recent_sensor_readings
from app.db.collections.eosm_predictions import get_latest_prediction
from app.db.mongodb import get_db
from app.models.eosm_sensor_models import LoRaSensorIngest
from app.services.eosm_iot_service import ingest_lora_reading
from app.utils.response_builder import success_response

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/",
    summary="List sensor readings with optional date range filtering",
    response_model=dict,
    tags=["sensor-data"],
)
async def list_sensor_readings(
    limit: int = Query(20, ge=1, le=2000),
    basestation_id: str | None = Query(None, alias="basestationId"),
    greenhouse_id: str | None = Query(None, alias="greenhouseId"),
    start_date: str | None = Query(None, alias="startDate", description="Start date in YYYY-MM-DD format"),
    end_date: str | None = Query(None, alias="endDate", description="End date in YYYY-MM-DD format"),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Return sensor readings with optional filters.
    
    Supports date range filtering using startDate and endDate (YYYY-MM-DD format).
    Dates are converted to epoch timestamps for querying the timestamp field.
    """
    start_timestamp = None
    end_timestamp = None
    
    if start_date:
        try:
            # Parse date as UTC to avoid timezone issues
            # Interpret the date string as a date in UTC (start of day UTC)
            dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            start_timestamp = int(dt.timestamp())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid startDate format. Expected YYYY-MM-DD, got: {start_date}"
            )
    
    if end_date:
        try:
            # Parse date as UTC and set to end of day (23:59:59 UTC)
            dt = datetime.strptime(end_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
            end_timestamp = int(dt.timestamp())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid endDate format. Expected YYYY-MM-DD, got: {end_date}"
            )
    
    readings = await find_recent_sensor_readings(
        db,
        limit=limit,
        basestation_id=basestation_id,
        greenhouse_id=greenhouse_id,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
    )
    return success_response(message="ok", data={"items": readings})


@router.post(
    "/ingest",
    summary="Ingest sensor reading from LoRa gateway",
    status_code=status.HTTP_201_CREATED,
    tags=["sensor-data", "iot"],
)
async def ingest_lora_sensor_reading(
    payload: LoRaSensorIngest, db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    """Validate and persist a LoRa gateway sensor reading."""
    # ================= eosm component start: LoRa ingestion endpoint =================
    try:
        return await ingest_lora_reading(payload, db)
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        logger.exception(
            "Unexpected failure while inserting LoRa sensor reading",
            extra={"basestation_id": payload.basestation_id},
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to ingest sensor data due to an internal error",
        )
    # ================= eosm component end =================


@router.get(
    "/latest-with-prediction",
    summary="Get latest sensor reading with ML prediction",
    response_model=dict,
    tags=["sensor-data"],
)
async def get_latest_with_prediction(
    basestation_id: str | None = Query(None, alias="basestationId"),
    greenhouse_id: str | None = Query(None, alias="greenhouseId"),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Get the latest sensor reading along with its ML prediction.
    
    Returns the most recent sensor reading and its associated stress prediction.
    """
    # ================= eosm component start: Latest reading with prediction =================
    try:
        from app.models.eosm_prediction_models import EOSMStressPredictionRequest
        from app.services.eosm_ml_service import generate_stress_prediction
        
        # If greenhouse_id is None (ALL greenhouses), aggregate predictions
        if greenhouse_id is None:
            # Fetch enough readings to ensure we get latest from each greenhouse
            # Use a larger limit to cover all greenhouses (assuming reasonable number of greenhouses)
            all_readings = await find_recent_sensor_readings(
                db,
                limit=500,  # Get enough readings to cover all greenhouses
                basestation_id=basestation_id,
                greenhouse_id=None,  # No filter - get all greenhouses
            )
            
            if not all_readings:
                raise HTTPException(
                    status_code=404,
                    detail="No sensor readings found",
                )
            
            # Group by greenhouse_id and get the latest reading for each
            # This ensures we get the most recent reading from each greenhouse
            greenhouse_latest: Dict[str, Dict[str, Any]] = {}
            for reading in all_readings:
                gh_id = reading.get("greenhouse_id")
                if gh_id:
                    # Get timestamp (handle both int and datetime formats)
                    reading_ts = reading.get("timestamp", 0)
                    if isinstance(reading_ts, str):
                        try:
                            reading_ts = int(datetime.fromisoformat(reading_ts.replace('Z', '+00:00')).timestamp())
                        except (ValueError, AttributeError):
                            reading_ts = 0
                    
                    if gh_id not in greenhouse_latest:
                        greenhouse_latest[gh_id] = reading
                    else:
                        # Compare timestamps to keep the latest
                        current_ts = greenhouse_latest[gh_id].get("timestamp", 0)
                        if isinstance(current_ts, str):
                            try:
                                current_ts = int(datetime.fromisoformat(current_ts.replace('Z', '+00:00')).timestamp())
                            except (ValueError, AttributeError):
                                current_ts = 0
                        
                        if reading_ts > current_ts:
                            greenhouse_latest[gh_id] = reading
            
            if not greenhouse_latest:
                raise HTTPException(
                    status_code=404,
                    detail="No sensor readings with greenhouse_id found",
                )
            
            logger.info(
                "Aggregating predictions from multiple greenhouses",
                extra={
                    "greenhouse_count": len(greenhouse_latest),
                    "greenhouse_ids": list(greenhouse_latest.keys()),
                },
            )
            
            # Calculate aggregated sensor values (average across all greenhouses)
            aggregated = {
                "temperature": 0.0,
                "humidity": 0.0,
                "soil_voltage": 0.0,
                "uv_voltage": 0.0,
                "mq_voltage": 0.0,
            }
            count = len(greenhouse_latest)
            
            for reading in greenhouse_latest.values():
                aggregated["temperature"] += float(reading.get("temperature", 20.0))
                aggregated["humidity"] += float(reading.get("humidity", 50.0))
                aggregated["soil_voltage"] += float(reading.get("soil_voltage", 2.0))
                aggregated["uv_voltage"] += float(reading.get("uv_voltage", 0.5))
                aggregated["mq_voltage"] += float(reading.get("mq_voltage", 0.5))
            
            # Average the values
            for key in aggregated:
                aggregated[key] /= count
            
            logger.info(
                "Calculated aggregated sensor values",
                extra={
                    "greenhouse_count": count,
                    "avg_temperature": aggregated["temperature"],
                    "avg_humidity": aggregated["humidity"],
                    "avg_soil_voltage": aggregated["soil_voltage"],
                    "avg_uv_voltage": aggregated["uv_voltage"],
                    "avg_mq_voltage": aggregated["mq_voltage"],
                },
            )
            
            # Use the most recent reading as the "reading" response (for display)
            # Find the reading with the highest timestamp
            latest_reading = None
            latest_ts = 0
            for reading in greenhouse_latest.values():
                ts = reading.get("timestamp", 0)
                if isinstance(ts, str):
                    try:
                        ts = int(datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp())
                    except (ValueError, AttributeError):
                        ts = 0
                if ts > latest_ts:
                    latest_ts = ts
                    latest_reading = reading
            
            if not latest_reading:
                latest_reading = list(greenhouse_latest.values())[0]
            
            # Generate prediction using aggregated values
            prediction = None
            try:
                prediction_request = EOSMStressPredictionRequest(
                    temperature=aggregated["temperature"],
                    humidity=aggregated["humidity"],
                    soil_voltage=aggregated["soil_voltage"],
                    uv_voltage=aggregated["uv_voltage"],
                    mq_voltage=aggregated["mq_voltage"],
                    basestation_id=None,  # Aggregated across all basestations
                    greenhouse_id=None,  # Aggregated across all greenhouses
                )
                
                prediction_response = await generate_stress_prediction(
                    request=prediction_request,
                    db=db,
                    basestation_id=None,
                    greenhouse_id=None,
                    save_to_db=False,  # Don't save aggregated predictions
                )
                
                if prediction_response:
                    prediction = prediction_response.model_dump(by_alias=True)
                    if "timestamp" in prediction and isinstance(prediction["timestamp"], datetime):
                        prediction["timestamp"] = int(prediction["timestamp"].timestamp())
                    # Mark as aggregated
                    prediction["is_aggregated"] = True
                    prediction["greenhouse_count"] = count
                    logger.info(
                        "Aggregated prediction generated for all greenhouses",
                        extra={
                            "greenhouse_count": count,
                            "stress_label": prediction.get("stress_label"),
                        },
                    )
            except Exception as pred_err:
                logger.warning(
                    "Failed to generate aggregated prediction",
                    extra={"error": str(pred_err)},
                )
        else:
            # Single greenhouse: get latest reading and generate prediction
            readings = await find_recent_sensor_readings(
                db,
                limit=1,
                basestation_id=basestation_id,
                greenhouse_id=greenhouse_id,
            )
            
            if not readings:
                raise HTTPException(
                    status_code=404,
                    detail="No sensor readings found",
                )
            
            latest_reading = readings[0]
            
            # Always generate a fresh prediction for the latest reading
            prediction = None
            try:
                prediction_request = EOSMStressPredictionRequest(
                    temperature=float(latest_reading.get("temperature", 20.0)),
                    humidity=float(latest_reading.get("humidity", 50.0)),
                    soil_voltage=float(latest_reading.get("soil_voltage", 2.0)),
                    uv_voltage=float(latest_reading.get("uv_voltage", 0.5)),
                    mq_voltage=float(latest_reading.get("mq_voltage", 0.5)),
                    basestation_id=latest_reading.get("basestation_id"),
                    greenhouse_id=latest_reading.get("greenhouse_id"),
                )
                
                prediction_response = await generate_stress_prediction(
                    request=prediction_request,
                    db=db,
                    basestation_id=latest_reading.get("basestation_id"),
                    greenhouse_id=latest_reading.get("greenhouse_id"),
                    save_to_db=True,
                )
                
                if prediction_response:
                    prediction = prediction_response.model_dump(by_alias=True)
                    if "timestamp" in prediction and isinstance(prediction["timestamp"], datetime):
                        prediction["timestamp"] = int(prediction["timestamp"].timestamp())
                    logger.info(
                        "Fresh prediction generated for latest reading",
                        extra={
                            "basestation_id": latest_reading.get("basestation_id"),
                            "greenhouse_id": latest_reading.get("greenhouse_id"),
                            "stress_label": prediction.get("stress_label"),
                        },
                    )
            except Exception as pred_err:
                logger.warning(
                    "Failed to generate prediction for latest reading",
                    extra={"error": str(pred_err)},
                )
                # Try to get existing prediction as fallback
                try:
                    prediction = await get_latest_prediction(
                        db,
                        basestation_id=latest_reading.get("basestation_id"),
                        greenhouse_id=latest_reading.get("greenhouse_id"),
                    )
                except Exception:
                    pass  # Continue with prediction=None
        
        result = {
            "reading": latest_reading,
            "prediction": prediction,
        }
        
        return success_response(
            message="Latest reading with prediction retrieved successfully",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to retrieve latest reading with prediction")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve latest reading with prediction due to an error",
        ) from exc
    # ================= eosm component end =================

