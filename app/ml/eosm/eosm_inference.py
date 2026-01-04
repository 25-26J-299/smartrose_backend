"""EOSM ML model inference for stress prediction.

Loads the trained Random Forest model, scaler, and label encoder once on module import.
Provides prediction utilities for stress level prediction based on sensor readings.

Model path is configured via EOSM_MODEL_DIR environment variable pointing to smartrose-eosm/ml/models/

Expected features (in order):
    1. temperature
    2. humidity
    3. uv_voltage
    4. soil_voltage
    5. mq_voltage

Returns:
    - stress_label: "HIGH", "MEDIUM", or "LOW"
    - stress_probabilities: dict with probabilities for each label
"""

import logging
from pathlib import Path
from typing import Optional

import joblib
import numpy as np

from app.core.config import settings

# ================= eosm component start: ML inference =================

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Model paths (from environment variable)
# -----------------------------------------------------------------------------
_MODEL_DIR: Optional[Path] = None
_MODEL_PATH: Optional[Path] = None
_SCALER_PATH: Optional[Path] = None
_LABEL_ENCODER_PATH: Optional[Path] = None
_MODEL_PATHS_INITIALIZED = False

# Try to find models in smartrose-eosm directory relative to backend
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent
_EOSM_ML_DIR = _BACKEND_DIR.parent / "smartrose-eosm" / "ml" / "models"

# Initialize paths lazily to avoid import-time errors
def _get_model_paths():
    """Get model paths, initializing them on first call."""
    global _MODEL_DIR, _MODEL_PATH, _SCALER_PATH, _LABEL_ENCODER_PATH, _MODEL_PATHS_INITIALIZED
    
    if _MODEL_PATHS_INITIALIZED:
        return  # Already initialized
    
    _MODEL_PATHS_INITIALIZED = True
    
    if hasattr(settings, 'EOSM_MODEL_DIR') and settings.EOSM_MODEL_DIR:
        _MODEL_DIR = Path(settings.EOSM_MODEL_DIR)
        _MODEL_PATH = _MODEL_DIR / "stress_model_rf.pkl"
        _SCALER_PATH = _MODEL_DIR / "stress_scaler.pkl"
        _LABEL_ENCODER_PATH = _MODEL_DIR / "stress_label_encoder.pkl"
    elif _EOSM_ML_DIR.exists():
        # Auto-detect from smartrose-eosm directory
        _MODEL_DIR = _EOSM_ML_DIR
        _MODEL_PATH = _MODEL_DIR / "stress_model_rf.pkl"
        _SCALER_PATH = _MODEL_DIR / "stress_scaler.pkl"
        _LABEL_ENCODER_PATH = _MODEL_DIR / "stress_label_encoder.pkl"

# Feature order (must match training)
FEATURES = [
    "temperature",
    "humidity",
    "uv_voltage",
    "soil_voltage",
    "mq_voltage"
]

# -----------------------------------------------------------------------------
# Global model instances (loaded once)
# -----------------------------------------------------------------------------
_model = None
_scaler = None
_label_encoder = None
_model_loaded = False


def _load_models() -> bool:
    """Load Random Forest model, scaler, and label encoder from disk.
    
    Returns True if successful, False otherwise.
    Models are loaded only once and cached in module globals.
    """
    global _model, _scaler, _label_encoder, _model_loaded
    
    if _model_loaded:
        return True
    
    # Initialize paths if not done yet
    _get_model_paths()
    
    # Check if paths are configured
    if _MODEL_PATH is None or _SCALER_PATH is None or _LABEL_ENCODER_PATH is None:
        logger.warning(
            "EOSM_MODEL_DIR not configured and models not found in smartrose-eosm/ml/models/. "
            "Set EOSM_MODEL_DIR environment variable to the directory containing "
            "stress_model_rf.pkl, stress_scaler.pkl, and stress_label_encoder.pkl"
        )
        return False
    
    try:
        if not _MODEL_PATH.exists():
            logger.error(
                "EOSM model file not found",
                extra={"path": str(_MODEL_PATH)},
            )
            return False
        
        if not _SCALER_PATH.exists():
            logger.error(
                "EOSM scaler file not found",
                extra={"path": str(_SCALER_PATH)},
            )
            return False
        
        if not _LABEL_ENCODER_PATH.exists():
            logger.error(
                "EOSM label encoder file not found",
                extra={"path": str(_LABEL_ENCODER_PATH)},
            )
            return False
        
        _model = joblib.load(_MODEL_PATH)
        _scaler = joblib.load(_SCALER_PATH)
        _label_encoder = joblib.load(_LABEL_ENCODER_PATH)
        _model_loaded = True
        
        logger.info(
            "EOSM Random Forest model, scaler, and label encoder loaded successfully",
            extra={
                "model_path": str(_MODEL_PATH),
                "scaler_path": str(_SCALER_PATH),
                "label_encoder_path": str(_LABEL_ENCODER_PATH),
            },
        )
        return True
        
    except Exception:
        logger.exception("Failed to load EOSM model artifacts")
        return False


def is_model_available() -> bool:
    """Check if the ML model is loaded and available for predictions."""
    return _load_models()


def predict_stress(
    temperature: float,
    humidity: float,
    soil_voltage: float,
    uv_voltage: float,
    mq_voltage: float,
) -> Optional[dict]:
    """Predict stress level and probabilities from sensor readings.
    
    Args:
        temperature: Temperature in Celsius
        humidity: Humidity percentage (0-100)
        soil_voltage: Soil moisture sensor voltage
        uv_voltage: UV sensor voltage
        mq_voltage: Gas sensor (MQ) voltage
    
    Returns:
        Dictionary with prediction results:
        {
            "stress_label": "HIGH" | "MEDIUM" | "LOW",
            "stress_probabilities": {
                "HIGH": float,
                "MEDIUM": float,
                "LOW": float
            }
        }
        Or None if prediction fails.
    """
    if not _load_models():
        logger.warning("EOSM model not available, returning None for stress prediction")
        return None
    
    try:
        # Prepare feature array in the EXACT order expected by the model
        X = np.array([[
            temperature,
            humidity,
            uv_voltage,
            soil_voltage,
            mq_voltage,
        ]])
        
        # Scale features
        X_scaled = _scaler.transform(X)
        
        # Predict
        pred_encoded = _model.predict(X_scaled)[0]
        pred_label = _label_encoder.inverse_transform([pred_encoded])[0]
        
        # Get prediction probabilities
        probs = _model.predict_proba(X_scaled)[0]
        prob_map = {
            _label_encoder.classes_[i]: round(float(probs[i]), 3)
            for i in range(len(probs))
        }
        
        result = {
            "stress_label": pred_label,
            "stress_probabilities": prob_map
        }
        
        logger.debug(
            "EOSM stress prediction complete",
            extra={
                "stress_label": pred_label,
                "probabilities": prob_map,
            },
        )
        
        return result
        
    except Exception:
        logger.exception("EOSM stress prediction failed")
        return None


def predict(data: dict) -> dict:
    """Legacy predict interface for API compatibility.
    
    Accepts a dict with sensor readings and returns prediction result.
    """
    temperature = float(data.get("temperature", 20.0))
    humidity = float(data.get("humidity", 50.0))
    uv_voltage = float(data.get("uv_voltage", data.get("uvVoltage", 0.5)))
    soil_voltage = float(data.get("soil_voltage", data.get("soilVoltage", 2.0)))
    mq_voltage = float(data.get("mq_voltage", data.get("mqVoltage", 0.5)))
    
    prediction = predict_stress(
        temperature=temperature,
        humidity=humidity,
        uv_voltage=uv_voltage,
        soil_voltage=soil_voltage,
        mq_voltage=mq_voltage,
    )
    
    if prediction is None:
        return {
            "status": "error",
            "message": "Model not available or prediction failed",
            "stress_label": None,
        }
    
    return {
        "status": "ok",
        **prediction,
    }

# ================= eosm component end =================

