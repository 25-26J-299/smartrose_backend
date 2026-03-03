"""Service helpers for persistent growth stage state.

Growth stage is now stored **per device** so multiple greenhouses can
independently track their own rose growth stage.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections.inm_growth_stage import (
    DEFAULT_GROWTH_STAGE,
    get_current_growth_stage as _get_current_growth_stage,
    get_growth_stage_state as _get_growth_stage_state,
    set_current_growth_stage as _set_current_growth_stage,
)
from app.services.inm_service import GrowthStage


async def get_current_growth_stage(
    db: AsyncIOMotorDatabase,
    device_id: str,
) -> GrowthStage:
    """Fetch the persisted growth stage for a device, defaulting to VEGETATIVE."""
    stage_str = (await _get_current_growth_stage(db, device_id)).strip().lower()
    try:
        return GrowthStage(stage_str)
    except Exception:  # noqa: BLE001
        return GrowthStage(DEFAULT_GROWTH_STAGE)


async def get_growth_stage_state(
    db: AsyncIOMotorDatabase,
    device_id: str,
) -> dict | None:
    """Return the raw growth stage document for a device, or None if unset."""
    return await _get_growth_stage_state(db, device_id)


async def set_current_growth_stage(
    db: AsyncIOMotorDatabase,
    stage: GrowthStage,
    device_id: str,
) -> dict:
    """Persist the provided growth stage as the active state for a device."""
    return await _set_current_growth_stage(db, stage.value, device_id)
