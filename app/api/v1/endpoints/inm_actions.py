"""Endpoints for INM human-in-the-loop action logging.

Actions are scoped per device so each greenhouse's farmer sees only their
own recommendation history.
"""

import logging

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.db.collections import devices as device_repo
from app.db.collections.inm_actions import (
    create_inm_action,
    get_inm_action_history_by_device,
)
from app.db.mongodb import get_db
from app.models.inm_action_models import INMActionCreate
from app.services.inm_growth_stage_service import get_current_growth_stage

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/action", summary="Log whether an INM recommendation was applied or ignored")
async def log_inm_action(
    payload: INMActionCreate,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Log farmer feedback for a recommendation (applied/ignored).

    Requires JWT. device_id must belong to the logged-in user.
    This is logging only and does not affect predictions or recommendations.
    """
    # Verify device belongs to this user
    device = await device_repo.get_device_by_serial(db, payload.device_id)
    if not device or device.get("user_id") != current_user["_id"]:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device not found or does not belong to your account.",
        )

    growth_stage = await get_current_growth_stage(db, payload.device_id)
    logger.info(
        "Logging INM action",
        extra={
            "device_id": payload.device_id,
            "growth_stage": growth_stage.value,
            "action_taken": payload.action_taken,
        },
    )

    doc = await create_inm_action(
        db=db,
        recommendation_text=payload.recommendation_text,
        growth_stage=growth_stage.value,
        action_taken=payload.action_taken,
        ec_action=payload.ec_action,
        ph_action=payload.ph_action,
        npk_recommendation=payload.npk_recommendation,
        device_id=payload.device_id,
        location_id=device.get("location_id", ""),
        user_id=current_user["_id"],
        weather_condition=payload.weather_condition,
        weather_temperature_c=payload.weather_temperature_c,
        weather_humidity_pct=payload.weather_humidity_pct,
        weather_precipitation_mm=payload.weather_precipitation_mm,
        weather_advisory=payload.weather_advisory,
    )
    return {"status": "ok", "message": "Action logged successfully", "data": doc}


@router.get("/action-history", summary="Get INM action history for a device")
async def inm_action_history(
    device_id: str = Query(..., description="Device ID to fetch action history for"),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Return most recent INM actions for a specific device.

    Requires JWT. The device must belong to the logged-in user.
    """
    device = await device_repo.get_device_by_serial(db, device_id)
    if not device or device.get("user_id") != current_user["_id"]:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device not found or does not belong to your account.",
        )

    history = await get_inm_action_history_by_device(db, device_id, limit=limit)
    logger.info(
        "Returning INM action history",
        extra={"device_id": device_id, "limit": limit, "count": len(history)},
    )
    return {"status": "ok", "device_id": device_id, "count": len(history), "data": history}
