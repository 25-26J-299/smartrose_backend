#Service for FM ML prediction using local inference.


from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.ml.fm.fm_inference import predict_freshness
from app.models.fm_models import FMSensorInput

logger = logging.getLogger(__name__)


class FMMLError(RuntimeError):
    """Raised when the FM ML prediction fails."""


async def get_ml_prediction(reading: FMSensorInput) -> Dict[str, Any]:

    
    logger.debug(
        "Generating FM prediction with local models",
        extra={
            "temperature": reading.temperature,
            "humidity": reading.humidity,
            "gas_value": reading.gas_value,
            "water_level": reading.water_level,
        }
    )

    try:
        # Get prediction from local ML model
        prediction_result = predict_freshness(
            temperature=reading.temperature,
            humidity=reading.humidity,
            gas_value=reading.gas_value,
            water_level=reading.water_level,
        )
        
        if prediction_result is None:
            logger.warning("FM local model prediction returned None")
            raise FMMLError("FM models not available or prediction failed")
        
        # Validate prediction structure
        missing = {"freshness_score", "vase_life_hours", "status"} - prediction_result.keys()
        if missing:
            raise FMMLError(f"FM prediction missing keys: {', '.join(sorted(missing))}")

        logger.info(
            "FM prediction complete",
            extra={
                "freshness_score": prediction_result.get("freshness_score"),
                "vase_life_hours": prediction_result.get("vase_life_hours"),
                "status": prediction_result.get("status"),
            },
        )

        return prediction_result
        
    except FMMLError:
        raise
    except Exception as exc: 
        logger.exception("Unexpected error during FM prediction")
        raise FMMLError(f"Unexpected error during FM prediction: {exc}") from exc
