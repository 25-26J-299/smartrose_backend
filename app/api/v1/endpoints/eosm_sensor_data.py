"""Endpoints for ingesting eosm LoRa sensor readings."""

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user
from app.db.collections import devices as device_repo
from app.db.collections.eosm_readings import find_recent_sensor_readings
from app.db.collections.eosm_predictions import get_latest_prediction, get_previous_prediction_for_reading
from app.db.mongodb import get_db
from app.models.eosm_sensor_models import LoRaSensorIngest
from app.services.eosm_iot_service import ingest_lora_reading
from app.services.energy_optimization_service import optimize_energy
from app.services.eosm_ml_service import generate_stress_prediction_with_energy
from app.services.notification_service import create_notification
from app.db.collections import notifications as notifications_repo
from app.utils.response_builder import success_response

router = APIRouter()
logger = logging.getLogger(__name__)


def _sensor_data_from_reading(reading: Dict[str, Any]) -> Dict[str, float]:
    """Build sensor_data dict for EODE from a reading document."""
    return {
        "temperature": float(reading.get("temperature", 25.0)),
        "humidity": float(reading.get("humidity", 60.0)),
        "soil_voltage": float(reading.get("soil_voltage", 2.5)),
        "uv_voltage": float(reading.get("uv_voltage", 0.8)),
        "mq_voltage": float(reading.get("mq_voltage", 0.5)),
    }


def _add_confidence_to_prediction(prediction: Dict[str, Any]) -> None:
    """Add confidence (max probability) to prediction dict for Flutter."""
    probs = prediction.get("stress_probabilities") or {}
    if isinstance(probs, dict) and probs:
        prediction["confidence"] = round(max(float(p) for p in probs.values()), 2)


async def _verify_eosm_device_ownership(db, device_id: str, current_user: dict) -> dict:
    dev = await device_repo.get_device_by_serial(db, device_id)
    if not dev:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found.")
    if str(dev.get("type", "")).upper() != "EOSM":
        raise HTTPException(status_code=400, detail=f"Device '{device_id}' is not an EOSM device.")
    if dev.get("user_id") != current_user["_id"]:
        raise HTTPException(status_code=403, detail="You do not have access to this device.")
    return dev


@router.get(
    "/",
    summary="List sensor readings with optional date range filtering",
    response_model=dict,
    tags=["sensor-data"],
)
async def list_sensor_readings(
    limit: int = Query(20, ge=1, le=2000),
    device_id: str | None = Query(None, alias="deviceId"),
    start_date: str | None = Query(None, alias="startDate", description="Start date in YYYY-MM-DD format"),
    end_date: str | None = Query(None, alias="endDate", description="End date in YYYY-MM-DD format"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
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
    
    if device_id:
        await _verify_eosm_device_ownership(db, device_id, current_user)

    readings = await find_recent_sensor_readings(
        db,
        limit=limit,
        user_id=current_user["_id"],
        device_id=device_id,
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
            extra={"device_id": payload.device_id},
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
    device_id: str | None = Query(None, alias="deviceId"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Get the latest sensor reading along with its ML prediction.
    
    Returns the most recent sensor reading and its associated stress prediction.
    """
    # ================= eosm component start: Latest reading with prediction =================
    try:
        if device_id:
            await _verify_eosm_device_ownership(db, device_id, current_user)

        from app.models.eosm_prediction_models import EOSMStressPredictionRequest

        energy_optimization = None
        # If device_id is None (ALL devices), aggregate predictions
        if device_id is None:
            all_readings = await find_recent_sensor_readings(
                db,
                limit=500,
                user_id=current_user["_id"],
            )

            if not all_readings:
                raise HTTPException(status_code=404, detail="No sensor readings found")

            # Group by device_id, keep the latest reading per device
            device_latest: Dict[str, Dict[str, Any]] = {}
            for reading in all_readings:
                dev_id = reading.get("device_id")
                if dev_id:
                    reading_ts = reading.get("timestamp", 0)
                    current_ts = device_latest.get(dev_id, {}).get("timestamp", 0)
                    if dev_id not in device_latest or reading_ts > current_ts:
                        device_latest[dev_id] = reading

            if not device_latest:
                raise HTTPException(status_code=404, detail="No sensor readings with device_id found")

            # Per-device: ensure prediction saved and create HIGH stress notification if needed (same as single-device path)
            for dev_id, reading in device_latest.items():
                try:
                    current_reading_id = str(reading.get("_id", ""))
                    prev_pred = await get_previous_prediction_for_reading(
                        db, device_id=dev_id, current_sensor_reading_id=current_reading_id
                    )
                    prev_stress = (
                        str(prev_pred["stress_label"]).upper()
                        if prev_pred and prev_pred.get("stress_label")
                        else None
                    )
                    pred_req = EOSMStressPredictionRequest(
                        temperature=float(reading.get("temperature", 20.0)),
                        humidity=float(reading.get("humidity", 50.0)),
                        soil_voltage=float(reading.get("soil_voltage", 2.0)),
                        uv_voltage=float(reading.get("uv_voltage", 0.5)),
                        mq_voltage=float(reading.get("mq_voltage", 0.5)),
                        device_id=dev_id,
                    )
                    pred_resp, _ = await generate_stress_prediction_with_energy(
                        request=pred_req,
                        db=db,
                        device_id=dev_id,
                        sensor_reading_id=current_reading_id,
                        save_to_db=True,
                    )
                    if pred_resp:
                        cur_stress = (
                            str(pred_resp.stress_label).upper()
                            if pred_resp and pred_resp.stress_label
                            else None
                        )
                        if cur_stress == "HIGH" and (prev_stress is None or prev_stress != "HIGH"):
                            uid = reading.get("user_id")
                            loc_id = reading.get("location_id")
                            if uid:
                                already = await notifications_repo.exists_eosm_high_for_reading(
                                    db, str(uid), current_reading_id
                                )
                                if not already:
                                    await create_notification(
                                        db=db,
                                        user_id=str(uid),
                                        type="EOSM",
                                        title="High Plant Stress Detected",
                                        message="Greenhouse experiencing high stress conditions.",
                                        severity="HIGH",
                                        metadata={
                                            "device_id": dev_id,
                                            "greenhouse_id": str(loc_id) if loc_id else "",
                                            "sensor_reading_id": current_reading_id,
                                        },
                                    )
                                    logger.info(
                                        "EOSM HIGH stress notification created (aggregate path)",
                                        extra={"device_id": dev_id},
                                    )
                except Exception as per_dev_err:
                    logger.warning(
                        "Per-device prediction/notification failed (non-fatal)",
                        extra={"device_id": dev_id, "error": str(per_dev_err)},
                    )

            greenhouse_latest = device_latest  # reuse variable below

            logger.info(
                "Aggregating predictions from multiple devices",
                extra={
                    "device_count": len(device_latest),
                    "device_ids": list(device_latest.keys()),
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
                    "device_count": count,
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
                )
                prediction_response, energy_optimization = await generate_stress_prediction_with_energy(
                    request=prediction_request,
                    db=db,
                    device_id=None,
                    save_to_db=False,
                )
                if prediction_response:
                    prediction = prediction_response.model_dump(by_alias=True)
                    if "timestamp" in prediction and isinstance(prediction["timestamp"], datetime):
                        prediction["timestamp"] = int(prediction["timestamp"].timestamp())
                    prediction["is_aggregated"] = True
                    prediction["device_count"] = count
                    _add_confidence_to_prediction(prediction)
                    logger.info(
                        "Aggregated prediction generated for all devices",
                        extra={
                            "device_count": count,
                            "stress_label": prediction.get("stress_label"),
                        },
                    )
            except Exception as pred_err:
                logger.warning(
                    "Failed to generate aggregated prediction",
                    extra={"error": str(pred_err)},
                )
        else:
            # Single device: get latest reading and generate prediction
            readings = await find_recent_sensor_readings(
                db,
                limit=1,
                user_id=current_user["_id"],
                device_id=device_id,
            )
            
            if not readings:
                # Device exists but has no readings yet — return 200 with nulls so app can show "No data"
                latest_reading = None
                prediction = None
                energy_optimization = optimize_energy(
                    _sensor_data_from_reading({}),
                    "MEDIUM",
                )
                result = {
                    "reading": latest_reading,
                    "prediction": prediction,
                    "energy_optimization": energy_optimization,
                }
                return success_response(
                    message="No sensor readings found for this device",
                    data=result,
                )
            
            latest_reading = readings[0]
            dev_id = latest_reading.get("device_id")
            current_reading_id = str(latest_reading.get("_id", ""))

            # Previous = prediction for a different reading (not this one), so we don't use same-reading from prior API call
            previous_prediction = await get_previous_prediction_for_reading(
                db, device_id=dev_id, current_sensor_reading_id=current_reading_id
            )
            previous_stress = (
                str(previous_prediction["stress_label"]).upper()
                if previous_prediction and previous_prediction.get("stress_label")
                else None
            )

            # Always generate a fresh prediction for the latest reading
            prediction = None
            try:
                prediction_request = EOSMStressPredictionRequest(
                    temperature=float(latest_reading.get("temperature", 20.0)),
                    humidity=float(latest_reading.get("humidity", 50.0)),
                    soil_voltage=float(latest_reading.get("soil_voltage", 2.0)),
                    uv_voltage=float(latest_reading.get("uv_voltage", 0.5)),
                    mq_voltage=float(latest_reading.get("mq_voltage", 0.5)),
                    device_id=latest_reading.get("device_id"),
                )
                prediction_response, energy_optimization = await generate_stress_prediction_with_energy(
                    request=prediction_request,
                    db=db,
                    device_id=dev_id,
                    sensor_reading_id=current_reading_id,
                    save_to_db=True,
                )
                if prediction_response:
                    prediction = prediction_response.model_dump(by_alias=True)
                    if "timestamp" in prediction and isinstance(prediction["timestamp"], datetime):
                        prediction["timestamp"] = int(prediction["timestamp"].timestamp())
                    _add_confidence_to_prediction(prediction)
                    logger.info(
                        "Fresh prediction generated for latest reading",
                        extra={
                            "device_id": dev_id,
                            "stress_label": prediction.get("stress_label"),
                        },
                    )
                    # Notify when stress transitions TO HIGH (same logic as ingest) — covers manually inserted readings
                    current_stress = (
                        str(prediction_response.stress_label).upper()
                        if prediction_response and prediction_response.stress_label
                        else None
                    )
                    # Notify when HIGH and (no previous prediction, or previous was LOW/MEDIUM)
                    if current_stress == "HIGH" and (previous_stress is None or previous_stress != "HIGH"):
                        try:
                            user_id_val = latest_reading.get("user_id")
                            location_id = latest_reading.get("location_id")
                            if user_id_val:
                                already = await notifications_repo.exists_eosm_high_for_reading(
                                    db, str(user_id_val), current_reading_id
                                )
                                if not already:
                                    await create_notification(
                                        db=db,
                                        user_id=str(user_id_val),
                                        type="EOSM",
                                        title="High Plant Stress Detected",
                                        message="Greenhouse experiencing high stress conditions.",
                                        severity="HIGH",
                                        metadata={
                                            "device_id": dev_id,
                                            "greenhouse_id": str(location_id) if location_id else "",
                                            "sensor_reading_id": current_reading_id,
                                        },
                                    )
                                    logger.info(
                                        "EOSM HIGH stress notification created for latest reading",
                                        extra={"device_id": dev_id},
                                    )
                        except Exception as notif_err:
                            logger.warning(
                                "Failed to create HIGH stress notification (non-fatal)",
                                extra={"device_id": dev_id, "error": str(notif_err)},
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
                        device_id=latest_reading.get("device_id"),
                    )
                except Exception:
                    pass  # Continue with prediction=None

        if energy_optimization is None:
            stress_label = (prediction or {}).get("stress_label") or "MEDIUM"
            sensor_data = _sensor_data_from_reading(latest_reading)
            energy_optimization = optimize_energy(sensor_data, stress_label)

        result = {
            "reading": latest_reading,
            "prediction": prediction,
            "energy_optimization": energy_optimization,
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

