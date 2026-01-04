"""Endpoints for INM human-in-the-loop action logging."""

import logging
from fastapi import APIRouter, Depends

from app.db.collections.inm_actions import create_inm_action, get_inm_action_history
from app.db.mongodb import get_db
from app.models.inm_action_models import INMActionCreate
from app.services.inm_growth_stage_service import get_current_growth_stage

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/action", summary="Log whether an INM recommendation was applied or ignored")
async def log_inm_action(payload: INMActionCreate, db=Depends(get_db)) -> dict:
    """Log farmer feedback for a recommendation (applied/ignored).

    This is logging only and must not affect predictions or recommendations.
    """
    growth_stage = await get_current_growth_stage(db)
    logger.info(
        "Logging INM action",
        extra={"growth_stage": growth_stage.value, "action_taken": payload.action_taken},
    )
    doc = await create_inm_action(
        db=db,
        recommendation_text=payload.recommendation_text,
        growth_stage=growth_stage.value,
        action_taken=payload.action_taken,
    )
    return {"status": "ok", "message": "Action logged successfully", "data": doc}


@router.get("/action-history", summary="Get recent INM action history")
async def inm_action_history(limit: int = 50, db=Depends(get_db)) -> dict:
    """Return most recent INM actions (for history visualization)."""
    history = await get_inm_action_history(db, limit=limit)
    logger.info("Returning INM action history", extra={"limit": limit, "count": len(history)})
    return {"status": "ok", "count": len(history), "data": history}


