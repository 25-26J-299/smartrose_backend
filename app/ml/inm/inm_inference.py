"""INM Random Forest model inference for EC prediction.

Loads the trained Random Forest model and scaler once on module import.
Provides prediction utilities for 24-hour ahead EC forecasting.

Model path is configured via INM_MODEL_DIR environment variable.

Expected features (in order):
    1. soil_temperature
    2. soil_moisture
    3. ec
    4. ph
    5. nitrogen
    6. phosphorus
    7. potassium
    8. air_temperature
    9. air_humidity
    10. growth_stage (encoded: 0=vegetative, 1=bud_formation, 2=flowering, 3=post_harvest)
"""

import logging
from pathlib import Path
from typing import Optional

import joblib
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Growth stage encoding (must match training data)
# -----------------------------------------------------------------------------
GROWTH_STAGE_ENCODING = {
    "vegetative": 0,
    "flowering": 1,
    "maintenance": 2,
}

# -----------------------------------------------------------------------------
# Model paths (from environment variable)
# -----------------------------------------------------------------------------
_MODEL_DIR: Optional[Path] = None
_RF_MODEL_PATH: Optional[Path] = None
_SCALER_PATH: Optional[Path] = None

if settings.INM_MODEL_DIR:
    _MODEL_DIR = Path(settings.INM_MODEL_DIR)
    _RF_MODEL_PATH = _MODEL_DIR / "inm_ec_rf_model.pkl"
    _SCALER_PATH = _MODEL_DIR / "inm_ec_scaler.pkl"

# -----------------------------------------------------------------------------
# Global model instances (loaded once)
# -----------------------------------------------------------------------------
_rf_model = None
_scaler = None
_model_loaded = False


def _load_models() -> bool:
    """Load Random Forest model and scaler from disk.
    
    Returns True if successful, False otherwise.
    Models are loaded only once and cached in module globals.
    """
    global _rf_model, _scaler, _model_loaded
    
    if _model_loaded:
        return True
    
    # Check if paths are configured
    if _RF_MODEL_PATH is None or _SCALER_PATH is None:
        logger.error(
            "INM_MODEL_DIR not configured. Set INM_MODEL_DIR environment variable "
            "to the directory containing inm_ec_rf_model.pkl and inm_ec_scaler.pkl"
        )
        return False
    
    try:
        if not _RF_MODEL_PATH.exists():
            logger.error(
                "RF model file not found",
                extra={"path": str(_RF_MODEL_PATH)},
            )
            return False
        
        if not _SCALER_PATH.exists():
            logger.error(
                "Scaler file not found",
                extra={"path": str(_SCALER_PATH)},
            )
            return False
        
        _rf_model = joblib.load(_RF_MODEL_PATH)
        _scaler = joblib.load(_SCALER_PATH)
        _model_loaded = True
        
        logger.info(
            "INM Random Forest model and scaler loaded successfully",
            extra={
                "model_path": str(_RF_MODEL_PATH),
                "scaler_path": str(_SCALER_PATH),
            },
        )
        return True
        
    except Exception:
        logger.exception("Failed to load INM model artifacts")
        return False


def is_model_available() -> bool:
    """Check if the ML model is loaded and available for predictions."""
    return _load_models()


def predict_ec_24h(
    soil_temp: float,
    soil_moisture: float,
    ec: float,
    ph: float,
    nitrogen: float,
    phosphorus: float,
    potassium: float,
    air_temp: float,
    air_humidity: float,
    growth_stage: str = "vegetative",
) -> Optional[float]:
    """Predict EC value 24 hours ahead using Random Forest model.
    
    Args:
        soil_temp: Soil temperature in Celsius
        soil_moisture: Soil moisture percentage
        ec: Current electrical conductivity (µS/cm)
        ph: Current soil pH level
        nitrogen: Nitrogen content (mg/kg)
        phosphorus: Phosphorus content (mg/kg)
        potassium: Potassium content (mg/kg)
        air_temp: Air temperature in Celsius
        air_humidity: Air humidity percentage
        growth_stage: Growth stage (vegetative, bud_formation, flowering, post_harvest)
    
    Returns:
        Predicted EC value for 24 hours ahead, or None if prediction fails.
    """
    if not _load_models():
        logger.warning("Model not available, returning None for EC prediction")
        return None
    
    try:
        # Encode growth stage
        growth_stage_encoded = GROWTH_STAGE_ENCODING.get(growth_stage.lower(), 0)
        
        # Prepare feature array in the EXACT order expected by the scaler:
        # ['soil_temperature', 'soil_moisture', 'ec', 'ph', 'nitrogen', 
        #  'phosphorus', 'potassium', 'air_temperature', 'air_humidity', 'growth_stage']
        features = np.array([[
            soil_temp,          # soil_temperature
            soil_moisture,      # soil_moisture
            ec,                 # ec
            ph,                 # ph
            nitrogen,           # nitrogen
            phosphorus,         # phosphorus
            potassium,          # potassium
            air_temp,           # air_temperature
            air_humidity,       # air_humidity
            growth_stage_encoded,  # growth_stage
        ]])
        
        # Scale features
        features_scaled = _scaler.transform(features)
        
        # Predict
        predicted_ec = _rf_model.predict(features_scaled)[0]
        
        # Ensure non-negative EC value
        predicted_ec = max(0.0, float(predicted_ec))
        
        logger.debug(
            "EC prediction complete",
            extra={"current_ec": ec, "predicted_ec_24h": predicted_ec},
        )
        
        return predicted_ec
        
    except Exception:
        logger.exception("EC prediction failed")
        return None


def predict(data: dict) -> dict:
    """Legacy predict interface for API compatibility.
    
    Accepts a dict with sensor readings and returns prediction result.
    """
    soil_temp = float(data.get("soil_temp", 25))
    soil_moisture = float(data.get("soil_moisture", 0))
    ec = float(data.get("ec", 0))
    ph = float(data.get("ph", 7.0))
    nitrogen = float(data.get("N", 0))
    phosphorus = float(data.get("P", 0))
    potassium = float(data.get("K", 0))
    air_temp = float(data.get("air_temp", 25))
    air_humidity = float(data.get("air_hum", 50))
    growth_stage = data.get("growth_stage", "vegetative")
    
    predicted_ec = predict_ec_24h(
        soil_temp=soil_temp,
        soil_moisture=soil_moisture,
        ec=ec,
        ph=ph,
        nitrogen=nitrogen,
        phosphorus=phosphorus,
        potassium=potassium,
        air_temp=air_temp,
        air_humidity=air_humidity,
        growth_stage=growth_stage,
    )
    
    if predicted_ec is None:
        return {
            "status": "error",
            "message": "Model not available or prediction failed",
            "predicted_ec_24h": None,
        }
    
    return {
        "status": "ok",
        "predicted_ec_24h": round(predicted_ec, 2),
    }
