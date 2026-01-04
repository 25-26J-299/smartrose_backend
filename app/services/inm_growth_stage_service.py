"""Service helpers for persistent growth stage state.

This layer provides a reusable getter for INM logic and endpoints.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections.inm_growth_stage import (
    DEFAULT_GROWTH_STAGE,
    get_current_growth_stage as _get_current_growth_stage,
    set_current_growth_stage as _set_current_growth_stage,
)
from app.services.inm_service import GrowthStage


async def get_current_growth_stage(db: AsyncIOMotorDatabase) -> GrowthStage:
    """Fetch the persisted growth stage, defaulting to VEGETATIVE if missing/invalid."""
    stage_str = (await _get_current_growth_stage(db)).strip().lower()
    try:
        return GrowthStage(stage_str)
    except Exception:  # noqa: BLE001
        return GrowthStage(DEFAULT_GROWTH_STAGE)


async def set_current_growth_stage(db: AsyncIOMotorDatabase, stage: GrowthStage) -> dict:
    """Persist the provided growth stage as the singleton active state."""
    return await _set_current_growth_stage(db, stage.value)


