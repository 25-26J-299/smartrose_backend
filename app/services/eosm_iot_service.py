"""Service helpers for eosm IoT device ingestion."""

import logging
from typing import Dict

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections import base_stations as base_station_repo
from app.db.collections import devices as device_repo
from app.db.collections.eosm_readings import insert_sensor_reading
from app.db.collections.eosm_predictions import get_latest_prediction
from app.db.collections import notifications as notifications_repo
from app.models.eosm_sensor_models import LoRaSensorIngest
from app.models.eosm_prediction_models import EOSMStressPredictionRequest
from app.services.eosm_ml_service import generate_stress_prediction
from app.services.notification_service import create_notification
from app.utils import time_utils
from app.utils.response_builder import success_response

logger = logging.getLogger(__name__)


async def ingest_lora_reading(
    payload: LoRaSensorIngest, db: AsyncIOMotorDatabase
) -> Dict[str, str]:
    """Persist a LoRa gateway reading, generate ML prediction. EOSM: deviceId → device + base_station lookup, enrich."""
    # ================= eosm component start: LoRa ingestion service =================
    device = await device_repo.get_device_by_serial(db, payload.device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Device '{payload.device_id}' is not registered. "
                "Ask your admin to register and assign this device first."
            ),
        )
    if str(device.get("type", "")).upper() != "EOSM":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Device '{payload.device_id}' is not an EOSM device.",
        )

    base_station_id = device.get("base_station_id")
    if not base_station_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Device '{payload.device_id}' has no base_station_id. "
                "Connect this device to a base station in the admin panel."
            ),
        )

    base_station = await base_station_repo.get_base_station_by_id(db, str(base_station_id))
    if not base_station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Base station for this device was not found.",
        )

    location_id = device.get("location_id", "")
    user_id = device.get("user_id", "")
    if base_station.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device user_id does not match base station user_id.",
        )

    record = payload.model_dump()

    now_utc = time_utils.utc_now()
    reading_utc = time_utils.epoch_to_utc(payload.timestamp)
    drift_seconds = abs((now_utc - reading_utc).total_seconds())
    if drift_seconds > 86400 * 30:
        logger.warning(
            "Suspicious timestamp in payload — possible RTC drift or SD card replay",
            extra={
                "device_id": payload.device_id,
                "timestamp_epoch": payload.timestamp,
                "reading_time_utc": reading_utc.isoformat(),
                "drift_seconds": drift_seconds,
            },
        )

    # reading_time_utc: actual sensor reading time (from gateway UTC epoch)
    # reading_time_slst: same moment as ISO string with +05:30 offset, for display
    # received_at: when backend received this upload (detects offline delay)
    record["reading_time_utc"] = reading_utc
    record["reading_time_slst"] = time_utils.epoch_to_slst(payload.timestamp).isoformat()
    record["received_at"] = now_utc

    # Device / location context resolved from registry — no duplicates
    record["device_id"] = payload.device_id
    record["location_id"] = location_id
    record["user_id"] = user_id
    record["base_station_id"] = base_station["_id"]   # ObjectId ref
    record["base_station_serial"] = base_station.get("serial") or ""  # human-readable

    try:
        inserted_id = await insert_sensor_reading(db, record)

        try:
            # Fetch previous prediction for this device (before we insert the new one)
            previous_prediction = await get_latest_prediction(db, device_id=payload.device_id)
            previous_stress = (
                str(previous_prediction["stress_label"]).upper()
                if previous_prediction and previous_prediction.get("stress_label")
                else None
            )

            prediction_request = EOSMStressPredictionRequest(
                temperature=payload.temperature,
                humidity=payload.humidity,
                soil_voltage=payload.soil_voltage,
                uv_voltage=payload.uv_voltage,
                mq_voltage=payload.mq_voltage,
                device_id=payload.device_id,
            )

            prediction_response = await generate_stress_prediction(
                request=prediction_request,
                db=db,
                device_id=payload.device_id,
                sensor_reading_id=inserted_id,
                save_to_db=True,
            )
            logger.info(
                "ML prediction generated for ingested reading",
                extra={"reading_id": inserted_id, "device_id": payload.device_id},
            )

            # Notify only when stress is HIGH and (no previous level or transition from LOW/MEDIUM)
            current_stress = (
                str(prediction_response.stress_label).upper()
                if prediction_response and prediction_response.stress_label
                else None
            )
            if (
                current_stress == "HIGH"
                and (previous_stress is None or previous_stress != "HIGH")
            ):
                try:
                    already = await notifications_repo.exists_eosm_high_for_reading(
                        db, str(user_id), inserted_id
                    )
                    if not already:
                        await create_notification(
                            db=db,
                            user_id=str(user_id),
                            type="EOSM",
                            title="High Plant Stress Detected",
                            message="Greenhouse experiencing high stress conditions.",
                            severity="HIGH",
                            metadata={
                                "device_id": payload.device_id,
                                "greenhouse_id": str(location_id) if location_id else "",
                                "sensor_reading_id": inserted_id,
                            },
                        )
                except Exception as notif_err:
                    logger.warning(
                        "Failed to create HIGH stress notification (non-fatal)",
                        extra={"device_id": payload.device_id, "error": str(notif_err)},
                    )
        except Exception as pred_err:
            logger.warning(
                "Failed to generate prediction for ingested reading (non-fatal)",
                extra={"reading_id": inserted_id, "error": str(pred_err)},
            )

    except Exception:
        logger.exception(
            "Failed to ingest LoRa reading",
            extra={"device_id": payload.device_id, "base_station_id": str(base_station_id)},
        )
        raise

    return success_response(message="ok", data={"id": inserted_id})
    # ================= eosm component end =================

