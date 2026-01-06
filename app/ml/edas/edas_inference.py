"""EDAS ML model inference for disease risk prediction.

Loads the trained Random Forest model once on module import.
Provides prediction utilities for disease risk prediction based on sensor readings.

Model path is configured via EDAS_MODEL_DIR environment variable pointing to smartrose-edas/ml/models/

Expected features (in order):
    1. plant_temperature
    2. air_temperature
    3. humidity
    4. temperature_difference
    5. hour
    6. is_day
    7. time_period

Returns:
    - disease_risk: "HIGH", "MEDIUM", or "LOW"
    - disease_probability: Probability of HIGH risk (0.0-1.0)
    - risk_probabilities: dict with probabilities for each risk level
"""

import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone, timedelta

import joblib
import numpy as np

from app.core.config import settings

# ================= edas component start: ML inference =================

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Model paths (from environment variable)
# -----------------------------------------------------------------------------
_MODEL_DIR: Optional[Path] = None
_MODEL_PATH: Optional[Path] = None
_MODEL_PATHS_INITIALIZED = False

# Try to find models in smartrose-edas directory relative to backend
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent
_EDAS_ML_DIR = _BACKEND_DIR.parent / "smartrose-edas" / "ml" / "models"

# Time period encoding (must match training)
TIME_PERIOD_ENCODING = {
    "morning": 0,
    "noon": 1,
    "evening": 2,
    "night": 3
}

# Sri Lanka timezone for time feature calculation
GREENHOUSE_TIMEZONE = timezone(timedelta(hours=5, minutes=30))  # UTC+5:30


def _get_model_paths():
    """Get model paths, initializing them on first call."""
    global _MODEL_DIR, _MODEL_PATH, _MODEL_PATHS_INITIALIZED
    
    if _MODEL_PATHS_INITIALIZED:
        return  # Already initialized
    
    _MODEL_PATHS_INITIALIZED = True
    
    if hasattr(settings, 'EDAS_MODEL_DIR') and settings.EDAS_MODEL_DIR:
        _MODEL_DIR = Path(settings.EDAS_MODEL_DIR)
        _MODEL_PATH = _MODEL_DIR / "smartrose_edas_rf_model.pkl"
    elif _EDAS_ML_DIR.exists():
        # Auto-detect from smartrose-edas directory
        _MODEL_DIR = _EDAS_ML_DIR
        _MODEL_PATH = _MODEL_DIR / "smartrose_edas_rf_model.pkl"

# Feature order (must match training)
FEATURES = [
    "plant_temperature",
    "air_temperature",
    "humidity",
    "temperature_difference",
    "hour",
    "is_day",
    "time_period"
]

# -----------------------------------------------------------------------------
# Global model instance (loaded once)
# -----------------------------------------------------------------------------
_model = None
_model_loaded = False


def _calculate_time_features(timestamp: datetime) -> dict:
    """Calculate time-based features from timestamp for ML.
    
    Uses Sri Lanka timezone (UTC+5:30) to match backend behavior.
    """
    # If timestamp has no timezone info, assume UTC
    if timestamp.tzinfo is None:
        utc_timestamp = timestamp.replace(tzinfo=timezone.utc)
    else:
        utc_timestamp = timestamp
    
    # Convert to Sri Lanka timezone
    local_timestamp = utc_timestamp.astimezone(GREENHOUSE_TIMEZONE)
    
    # Extract hour from LOCAL time
    hour = local_timestamp.hour
    
    # Determine if it's day time (06:00-18:00 LOCAL time)
    is_day = 6 <= hour < 18
    
    # Classify time period for ML pattern recognition (LOCAL time)
    if 6 <= hour < 10:
        time_period = "morning"
    elif 10 <= hour < 14:
        time_period = "noon"
    elif 14 <= hour < 18:
        time_period = "evening"
    else:  # 18:00-06:00
        time_period = "night"
    
    return {
        "hour": hour,
        "is_day": is_day,
        "time_period": time_period,
    }


def _load_model() -> bool:
    """Load Random Forest model from disk.
    
    Returns True if successful, False otherwise.
    Model is loaded only once and cached in module global.
    """
    global _model, _model_loaded
    
    if _model_loaded:
        return True
    
    # Initialize paths if not done yet
    _get_model_paths()
    
    # Check if paths are configured
    if _MODEL_PATH is None:
        logger.warning(
            "EDAS_MODEL_DIR not configured and models not found in smartrose-edas/ml/models/. "
            "Set EDAS_MODEL_DIR environment variable to the directory containing "
            "smartrose_edas_rf_model.pkl"
        )
        return False
    
    try:
        if not _MODEL_PATH.exists():
            logger.error(
                "EDAS model file not found",
                extra={"path": str(_MODEL_PATH)},
            )
            return False
        
        _model = joblib.load(_MODEL_PATH)
        _model_loaded = True
        
        logger.info(
            "EDAS Random Forest model loaded successfully",
            extra={
                "model_path": str(_MODEL_PATH),
            },
        )
        return True
        
    except Exception:
        logger.exception("Failed to load EDAS model")
        return False


def is_model_available() -> bool:
    """Check if the ML model is loaded and available for predictions."""
    return _load_model()


def predict_disease_risk(
    plant_temperature: float,
    air_temperature: float,
    humidity: float,
    timestamp: Optional[datetime] = None,
    temperature_difference: Optional[float] = None,
    hour: Optional[int] = None,
    is_day: Optional[bool] = None,
    time_period: Optional[str] = None,
) -> Optional[dict]:
    """Predict disease risk level and probabilities from sensor readings.
    
    Args:
        plant_temperature: Plant temperature in Celsius
        air_temperature: Air temperature in Celsius
        humidity: Humidity percentage (0-100)
        timestamp: Timestamp for time feature calculation (optional)
        temperature_difference: Pre-calculated difference (optional, auto-calculated if None)
        hour: Hour of day (0-23) - auto-calculated from timestamp if not provided
        is_day: Day/night indicator - auto-calculated from timestamp if not provided
        time_period: Time period classification - auto-calculated from timestamp if not provided
    
    Returns:
        Dictionary with prediction results:
        {
            "disease_risk": "HIGH" | "MEDIUM" | "LOW",
            "disease_probability": float,  # Probability of HIGH risk (0.0-1.0)
            "risk_probabilities": {
                "HIGH": float,
                "MEDIUM": float,
                "LOW": float
            }
        }
        Or None if prediction fails.
    """
    if not _load_model():
        logger.warning("EDAS model not available, returning None for disease risk prediction")
        return None
    
    try:
        # Calculate temperature_difference if not provided
        if temperature_difference is None:
            temperature_difference = plant_temperature - air_temperature
        
        # Calculate time features if timestamp is provided and features are missing
        if timestamp is not None:
            if hour is None or is_day is None or time_period is None:
                time_features = _calculate_time_features(timestamp)
                hour = hour or time_features["hour"]
                is_day = is_day if is_day is not None else time_features["is_day"]
                time_period = time_period or time_features["time_period"]
        
        # Default values if time features are still missing
        if hour is None:
            hour = 12  # Default to noon
        if is_day is None:
            is_day = True  # Default to day
        if time_period is None:
            time_period = "noon"  # Default to noon
        
        # Encode time_period to numeric
        time_period_encoded = TIME_PERIOD_ENCODING.get(time_period, 3)  # Default to "night"
        
        # Encode is_day to numeric (0 or 1)
        is_day_encoded = 1 if is_day else 0
        
        # Prepare feature array in the EXACT order expected by the model
        X = np.array([[
            plant_temperature,
            air_temperature,
            humidity,
            temperature_difference,
            hour,
            is_day_encoded,
            time_period_encoded
        ]])
        
        # Predict
        pred_encoded = _model.predict(X)[0]
        
        # Get prediction probabilities
        probs = _model.predict_proba(X)[0]
        
        # Map encoded prediction to label
        # Assuming model outputs: 0=LOW, 1=MEDIUM, 2=HIGH
        risk_labels = ["LOW", "MEDIUM", "HIGH"]
        pred_label = risk_labels[pred_encoded] if pred_encoded < len(risk_labels) else "UNKNOWN"
        
        # Create probability map
        prob_map = {
            risk_labels[i]: round(float(probs[i]), 3)
            for i in range(min(len(probs), len(risk_labels)))
        }
        
        # Get disease probability (probability of HIGH risk)
        disease_prob = float(probs[2]) if len(probs) > 2 else 0.0
        
        result = {
            "disease_risk": pred_label,
            "disease_probability": round(disease_prob, 3),
            "risk_probabilities": prob_map
        }
        
        logger.debug(
            "EDAS disease risk prediction complete",
            extra={
                "disease_risk": pred_label,
                "disease_probability": disease_prob,
                "probabilities": prob_map,
            },
        )
        
        return result
        
    except Exception:
        logger.exception("EDAS disease risk prediction failed")
        return None


def predict(data: dict) -> dict:
    """Legacy predict interface for API compatibility.
    
    Accepts a dict with sensor readings and returns prediction result.
    Handles timestamp conversion and time feature calculation.
    """
    try:
        # Extract sensor values
        plant_temperature = float(data.get("plant_temperature", 25.0))
        air_temperature = float(data.get("air_temperature", 25.0))
        humidity = float(data.get("humidity", 50.0))
        temperature_difference = data.get("temperature_difference")
        
        # Handle timestamp
        timestamp = None
        if "timestamp" in data and data["timestamp"] is not None:
            ts = data["timestamp"]
            if isinstance(ts, datetime):
                timestamp = ts
            elif isinstance(ts, (int, float)):
                timestamp = datetime.fromtimestamp(ts, tz=timezone.utc)
            elif isinstance(ts, str):
                try:
                    timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                except ValueError:
                    try:
                        timestamp = datetime.fromtimestamp(float(ts), tz=timezone.utc)
                    except (ValueError, TypeError):
                        pass
        
        # Extract time features if provided
        hour = data.get("hour")
        is_day = data.get("is_day")
        time_period = data.get("time_period")
        
        prediction = predict_disease_risk(
            plant_temperature=plant_temperature,
            air_temperature=air_temperature,
            humidity=humidity,
            timestamp=timestamp,
            temperature_difference=temperature_difference,
            hour=hour,
            is_day=is_day,
            time_period=time_period,
        )
        
        if prediction is None:
            return {
                "status": "error",
                "message": "Model not available or prediction failed",
                "disease_risk": None,
            }
        
        return {
            "status": "ok",
            **prediction,
        }
        
    except Exception:
        logger.exception("EDAS prediction failed in legacy predict interface")
        return {
            "status": "error",
            "message": "Prediction failed due to invalid input data",
            "disease_risk": None,
        }

# ================= edas component end =================
