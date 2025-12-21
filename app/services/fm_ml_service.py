"""Service for calling external FM ML microservice.

This service is responsible for sending sensor readings to the
Smart Rose FM ML API (running separately, e.g. in `smartrose-fm`)
exposed at http://127.0.0.1:9000/predict and returning the
prediction payload to callers.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from app.models.fm_models import FMSensorInput

logger = logging.getLogger(__name__)

ML_SERVICE_URL = "http://127.0.0.1:9000/predict"


class FMMLError(RuntimeError):
    """Raised when the FM ML service call fails."""


async def get_ml_prediction(reading: FMSensorInput) -> Dict[str, Any]:
    """Send sensor data to the external FM ML service and return prediction.

    Args:
        reading: Sensor input payload (temperature, humidity, gas_value, water_level, etc.).

    Returns:
        dict containing at least: ``freshness_score``, ``vase_life_hours``, ``status``.

    Raises:
        FMMLError: If the ML service is unreachable or returns an invalid response.
    """

    payload = {
        "temperature": reading.temperature,
        "humidity": reading.humidity,
        "gas_value": reading.gas_value,
        "water_level": reading.water_level,
    }

    logger.debug("Sending payload to FM ML service", extra={"url": ML_SERVICE_URL, "payload": payload})

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(ML_SERVICE_URL, json=payload)

        response.raise_for_status()
        data = response.json()

        # Basic shape validation
        if not isinstance(data, dict):
            raise FMMLError("Invalid response format from FM ML service (expected JSON object)")

        missing = {"freshness_score", "vase_life_hours", "status"} - data.keys()
        if missing:
            raise FMMLError(f"FM ML service response missing keys: {', '.join(sorted(missing))}")

        logger.info(
            "Received prediction from FM ML service",
            extra={
                "freshness_score": data.get("freshness_score"),
                "vase_life_hours": data.get("vase_life_hours"),
                "status": data.get("status"),
            },
        )

        return data
    except httpx.HTTPError as exc:
        logger.exception("HTTP error while calling FM ML service", extra={"url": ML_SERVICE_URL})
        raise FMMLError(f"Failed to call FM ML service: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error while calling FM ML service")
        raise FMMLError(f"Unexpected error from FM ML service: {exc}") from exc
