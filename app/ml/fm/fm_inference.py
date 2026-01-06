#FM model inference for freshness and vase life prediction


import logging
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

from app.core.config import settings

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Model paths (from environment variable or auto-detection)
# -----------------------------------------------------------------------------
_MODEL_DIR: Optional[Path] = None
_FRESHNESS_MODEL_PATH: Optional[Path] = None
_VASE_LIFE_MODEL_PATH: Optional[Path] = None
_MODEL_PATHS_INITIALIZED = False

# Try to find models in smartrose-fm directory relative to backend
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent
_FM_ML_DIR = _BACKEND_DIR.parent / "smartrose-fm" / "ml" / "models"


def _get_model_paths():
    """Get model paths, initializing them on first call."""
    global _MODEL_DIR, _FRESHNESS_MODEL_PATH, _VASE_LIFE_MODEL_PATH, _MODEL_PATHS_INITIALIZED
    
    if _MODEL_PATHS_INITIALIZED:
        return  # Already initialized
    
    _MODEL_PATHS_INITIALIZED = True
    
    if hasattr(settings, 'FM_MODEL_DIR') and settings.FM_MODEL_DIR:
        _MODEL_DIR = Path(settings.FM_MODEL_DIR)
        _FRESHNESS_MODEL_PATH = _MODEL_DIR / "freshness_model.pkl"
        _VASE_LIFE_MODEL_PATH = _MODEL_DIR / "vase_life_model.pkl"
    elif _FM_ML_DIR.exists():
        # Auto-detect from smartrose-fm directory
        _MODEL_DIR = _FM_ML_DIR
        _FRESHNESS_MODEL_PATH = _MODEL_DIR / "freshness_model.pkl"
        _VASE_LIFE_MODEL_PATH = _MODEL_DIR / "vase_life_model.pkl"


# Feature order (must match training)
FEATURES = [
    "temperature",
    "humidity",
    "gas_value",
    "water_level"
]

# -----------------------------------------------------------------------------
# Global model instances (loaded once)
# -----------------------------------------------------------------------------
_freshness_model = None
_vase_life_model = None
_models_loaded = False


def _load_models() -> bool:

    global _freshness_model, _vase_life_model, _models_loaded
    
    if _models_loaded:
        return True
    
    # Initialize paths if not done yet
    _get_model_paths()
    
    # Check if paths are configured
    if _FRESHNESS_MODEL_PATH is None or _VASE_LIFE_MODEL_PATH is None:
        logger.warning(
            "FM_MODEL_DIR not configured and models not found in smartrose-fm/ml/models/. "
            "Set FM_MODEL_DIR environment variable to the directory containing "
            "freshness_model.pkl and vase_life_model.pkl"
        )
        return False
    
    try:
        if not _FRESHNESS_MODEL_PATH.exists():
            logger.error(
                "FM freshness model file not found",
                extra={"path": str(_FRESHNESS_MODEL_PATH)},
            )
            return False
        
        if not _VASE_LIFE_MODEL_PATH.exists():
            logger.error(
                "FM vase life model file not found",
                extra={"path": str(_VASE_LIFE_MODEL_PATH)},
            )
            return False
        
        _freshness_model = joblib.load(_FRESHNESS_MODEL_PATH)
        _vase_life_model = joblib.load(_VASE_LIFE_MODEL_PATH)
        _models_loaded = True
        
        logger.info(
            "FM freshness and vase life models loaded successfully",
            extra={
                "freshness_model_path": str(_FRESHNESS_MODEL_PATH),
                "vase_life_model_path": str(_VASE_LIFE_MODEL_PATH),
            },
        )
        return True
        
    except Exception:
        logger.exception("Failed to load FM model artifacts")
        return False


def is_model_available() -> bool:
    #Check if the ML models are loaded and available for predictions.
    return _load_models()


def _compute_status(freshness_score: float) -> str:

    if freshness_score >= 0.7:
        return "Fresh"
    if freshness_score >= 0.4:
        return "Moderate"
    return "Poor"


def predict_freshness(
    temperature: float,
    humidity: float,
    gas_value: float,
    water_level: float,
) -> Optional[dict]:
   #Predict freshness score, vase life, and status from sensor readings.

    if not _load_models():
        logger.warning("FM models not available, returning None for freshness prediction")
        return None
    
    try:
        # Prepare feature DataFrame with proper column names (fixes sklearn warning)
        # Must match the feature names used during model training
        features_df = pd.DataFrame({
            "temperature": [temperature],
            "humidity": [humidity],
            "gas_value": [gas_value],
            "water_level": [water_level],
        })
        
        # Make predictions
        freshness_score_raw = float(_freshness_model.predict(features_df)[0])
        vase_life_hours_raw = float(_vase_life_model.predict(features_df)[0])
        
        # Round to reasonable precision
        freshness_score = round(freshness_score_raw, 4)
        vase_life_hours = round(vase_life_hours_raw, 2)
        
        # Compute status
        status = _compute_status(freshness_score)
        
        result = {
            "freshness_score": freshness_score,
            "vase_life_hours": vase_life_hours,
            "status": status,
        }
        
        logger.debug(
            "FM freshness prediction complete",
            extra={
                "freshness_score": freshness_score,
                "vase_life_hours": vase_life_hours,
                "status": status,
            },
        )
        
        return result
        
    except Exception:
        logger.exception("FM freshness prediction failed")
        return None


def predict(data: dict) -> dict:

    temperature = float(data.get("temperature", 20.0))
    humidity = float(data.get("humidity", 50.0))
    gas_value = float(data.get("gas_value", 0.0))
    water_level = float(data.get("water_level", 1))
    
    prediction = predict_freshness(
        temperature=temperature,
        humidity=humidity,
        gas_value=gas_value,
        water_level=water_level,
    )
    
    if prediction is None:
        return {
            "status": "error",
            "message": "Models not available or prediction failed",
            "freshness_score": None,
            "vase_life_hours": None,
        }
    
    return {
        **prediction,
    }
