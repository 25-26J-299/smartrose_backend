"""
Energy Optimization Decision Engine (EODE) for EOSM.

Rule-based service that recommends actuator settings for greenhouse control
based on sensor readings and ML-predicted stress level. Stress level has
FINAL PRIORITY over environmental rules.

Decision order:
  1. Default actuator state
  2. Environmental analysis (temperature, humidity, soil, UV)
  3. Stress override (FINAL — cannot be overridden)
  4. Safety rule (humidity > 90 and stress != LOW → increase ventilation)
  5. Reasoning generation
  6. Return

Actuators: fan_level, ac_level, water_pump, uv_light_intensity, energy_mode.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

FAN_LEVELS = ("OFF", "LOW", "MEDIUM", "HIGH")


def _fan_level_index(level: str) -> int:
    """Return numeric index for fan level comparison."""
    try:
        return FAN_LEVELS.index(level.upper())
    except ValueError:
        return 0


def _bump_fan_level(level: str) -> str:
    """Increase fan level by one step."""
    idx = _fan_level_index(level)
    if idx < len(FAN_LEVELS) - 1:
        return FAN_LEVELS[idx + 1]
    return level


def optimize_energy(
    sensor_data: Dict[str, Any],
    stress_label: str,
) -> Dict[str, Any]:
    """
    Compute actuator recommendations. Stress rules execute LAST and have final priority.

    Args:
        sensor_data: temperature, humidity, soil_voltage, uv_voltage, mq_voltage.
        stress_label: "LOW", "MEDIUM", or "HIGH".

    Returns:
        fan_level, ac_level, water_pump, uv_light_intensity, energy_mode,
        estimated_energy_saving, reasoning.
    """
    temp = float(sensor_data.get("temperature", 25.0))
    hum = float(sensor_data.get("humidity", 60.0))
    soil_v = float(sensor_data.get("soil_voltage", 2.5))
    uv_v = float(sensor_data.get("uv_voltage", 0.8))
    stress = str(stress_label).strip().upper()
    if stress not in ("LOW", "MEDIUM", "HIGH"):
        stress = "MEDIUM"

    env_reasons: list[str] = []

    # -------------------------------------------------------------
    # Step 1 — Default actuator state
    # -------------------------------------------------------------
    fan_level = "LOW"
    ac_level = "OFF"
    water_pump = "OFF"
    uv_light_intensity = "OFF"
    energy_mode = "OPTIMIZED"
    estimated_energy_saving = "25%"

    # -------------------------------------------------------------
    # Step 2 — Environmental analysis (recommendations only)
    # -------------------------------------------------------------

    # Temperature control (qualitative, fewer numbers)
    if temp < 28:
        fan_level = "LOW"
        env_reasons.append("Temperature is below the optimal range; fan set to LOW.")
    elif temp < 32:
        fan_level = "MEDIUM"
        env_reasons.append("Temperature is warm; fan set to MEDIUM for comfort.")
    else:
        fan_level = "HIGH"
        env_reasons.append("Temperature is high; fan set to HIGH for cooling.")

    # Humidity control
    if hum > 85:
        fan_level = _bump_fan_level(fan_level)
        env_reasons.append("Humidity is very high; ventilation is increased.")
    if hum > 90:
        ac_level = "MEDIUM"
        env_reasons.append("Extreme humidity; AC set to MEDIUM for dehumidification.")

    # Soil moisture
    if soil_v < 2.3:
        water_pump = "HIGH"
        env_reasons.append("Soil looks quite dry; water pump set to HIGH.")
    elif soil_v <= 2.7:
        water_pump = "LOW"
        env_reasons.append("Soil moisture is moderate; water pump set to LOW.")
    else:
        water_pump = "OFF"
        env_reasons.append("Soil is moist enough; water pump turned OFF.")

    # UV grow lights
    if uv_v < 0.5:
        uv_light_intensity = "HIGH"
        env_reasons.append("Natural light is low; grow lights set to HIGH.")
    elif uv_v <= 1.2:
        uv_light_intensity = "MEDIUM"
        env_reasons.append("Natural light is moderate; grow lights set to MEDIUM.")
    else:
        uv_light_intensity = "OFF"
        env_reasons.append("Natural light is strong; grow lights turned OFF.")

    # -------------------------------------------------------------
    # Step 3 — Stress override (FINAL; overwrites environmental)
    # -------------------------------------------------------------
    if stress == "HIGH":
        fan_level = "HIGH"
        ac_level = "MEDIUM"
        energy_mode = "PROTECT"
        estimated_energy_saving = "5%"
    elif stress == "MEDIUM":
        energy_mode = "OPTIMIZED"
        estimated_energy_saving = "25%"
    else:
        # LOW
        fan_level = "LOW"
        ac_level = "OFF"
        uv_light_intensity = "LOW"
        energy_mode = "MAX_SAVING"
        estimated_energy_saving = "40%"

    # -------------------------------------------------------------
    # Step 4 — Safety rule: humidity > 90 and stress != LOW → increase ventilation
    # -------------------------------------------------------------
    if hum > 90 and stress != "LOW":
        fan_level = _bump_fan_level(fan_level)

    # -------------------------------------------------------------
    # Step 5 — AI reasoning generation (environment + stress, fewer numbers)
    # -------------------------------------------------------------
    if stress == "LOW":
        stress_reason = "Stress level LOW — energy-saving mode (fan LOW, AC OFF)."
    elif stress == "MEDIUM":
        stress_reason = "Stress level MEDIUM — optimized balance between comfort and energy."
    else:
        stress_reason = "Stress level HIGH — plant safety priority (fan HIGH, AC MEDIUM)."
    reasoning = " ".join(env_reasons) + " " + stress_reason if env_reasons else stress_reason

    # -------------------------------------------------------------
    # Step 6 — Return structure
    # -------------------------------------------------------------
    return {
        "fan_level": fan_level,
        "ac_level": ac_level,
        "water_pump": water_pump,
        "uv_light_intensity": uv_light_intensity,
        "energy_mode": energy_mode,
        "estimated_energy_saving": estimated_energy_saving,
        "reasoning": reasoning,
    }
