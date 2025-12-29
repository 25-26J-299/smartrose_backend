"""Service layer for INM decision logic.

Provides rule-based recommendations for EC, pH, and NPK based on sensor readings
and predicted values. Designed for rose cultivation in hydroponic/controlled
environment agriculture.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# -----------------------------------------------------------------------------
# Constants for Rose Cultivation
# -----------------------------------------------------------------------------

# EC thresholds for roses (µS/cm or mS/cm depending on sensor)
EC_LOW_THRESHOLD = 0.8
EC_OPTIMAL_MIN = 1.0
EC_OPTIMAL_MAX = 2.0
EC_HIGH_THRESHOLD = 2.5
EC_CRITICAL_HIGH = 3.0

# pH thresholds for roses
PH_LOW_THRESHOLD = 5.5
PH_OPTIMAL_MIN = 5.8
PH_OPTIMAL_MAX = 6.5
PH_HIGH_THRESHOLD = 7.0

# NPK thresholds (mg/kg) vary by growth stage
# These are baseline values for general vegetative growth


class ECStatus(str, Enum):
    """EC level classification."""
    CRITICAL_LOW = "critical_low"
    LOW = "low"
    OPTIMAL = "optimal"
    HIGH = "high"
    CRITICAL_HIGH = "critical_high"


class GrowthStage(str, Enum):
    """Rose growth stages affecting nutrient requirements."""
    VEGETATIVE = "vegetative"
    FLOWERING = "flowering"
    MAINTENANCE = "maintenance"


@dataclass
class INMRecommendation:
    """Complete INM recommendation for the current state."""
    ec_status: ECStatus
    ec_action: str
    ph_action: str
    npk_action: str
    priority: str  # "immediate", "routine", "monitor"


def classify_ec_status(ec: float) -> ECStatus:
    """Classify EC value into status categories."""
    if ec < EC_LOW_THRESHOLD:
        return ECStatus.CRITICAL_LOW
    elif ec < EC_OPTIMAL_MIN:
        return ECStatus.LOW
    elif ec <= EC_OPTIMAL_MAX:
        return ECStatus.OPTIMAL
    elif ec <= EC_CRITICAL_HIGH:
        return ECStatus.HIGH
    else:
        return ECStatus.CRITICAL_HIGH


def get_ec_action(current_ec: float, predicted_ec: Optional[float]) -> str:
    """Generate EC action recommendation based on current and predicted values."""
    status = classify_ec_status(current_ec)
    
    # Factor in prediction if available
    predicted_trend = ""
    if predicted_ec is not None:
        delta = predicted_ec - current_ec
        if delta > 0.3:
            predicted_trend = " EC is predicted to rise significantly in 24h."
        elif delta < -0.3:
            predicted_trend = " EC is predicted to drop in 24h."
    
    actions = {
        ECStatus.CRITICAL_LOW: (
            "Critical: EC severely low. Immediately increase nutrient solution "
            "concentration. Check for dilution issues or nutrient depletion."
            + predicted_trend
        ),
        ECStatus.LOW: (
            "EC below optimal range. Increase fertilizer concentration gradually. "
            "Monitor daily and adjust as needed."
            + predicted_trend
        ),
        ECStatus.OPTIMAL: (
            "EC within optimal range for rose cultivation. "
            "Maintain current nutrient management schedule."
            + predicted_trend
        ),
        ECStatus.HIGH: (
            "EC above optimal range. Reduce fertilizer concentration or increase "
            "irrigation frequency to dilute nutrient solution."
            + predicted_trend
        ),
        ECStatus.CRITICAL_HIGH: (
            "Critical: EC dangerously high. Risk of root burn. "
            "Flush growing medium with clean water immediately. "
            "Reduce fertilizer by 50% after flushing."
            + predicted_trend
        ),
    }
    
    return actions[status]


def get_ph_action(ph: float) -> str:
    """Generate pH action recommendation for rose cultivation."""
    if ph < PH_LOW_THRESHOLD:
        return (
            "pH too acidic. Add pH-up solution (potassium hydroxide or sodium "
            "bicarbonate). Target pH 5.8-6.2 for optimal nutrient uptake."
        )
    elif ph < PH_OPTIMAL_MIN:
        return (
            "pH slightly low. Consider minor pH adjustment upward. "
            "Monitor for potential nutrient lockout, especially calcium and magnesium."
        )
    elif ph <= PH_OPTIMAL_MAX:
        return (
            "pH within optimal range (5.8-6.5). No adjustment needed. "
            "Continue monitoring."
        )
    elif ph <= PH_HIGH_THRESHOLD:
        return (
            "pH slightly high. Consider minor pH adjustment downward with pH-down "
            "solution. Monitor for iron and manganese deficiency signs."
        )
    else:
        return (
            "pH too alkaline. Add pH-down solution (phosphoric or nitric acid). "
            "High pH causes nutrient lockout. Target pH 5.8-6.2."
        )


def get_npk_action(
    nitrogen: float,
    phosphorus: float,
    potassium: float,
    growth_stage: GrowthStage = GrowthStage.VEGETATIVE,
) -> str:
    """Generate NPK action recommendation based on values and growth stage."""
    recommendations = []
    
    # Stage-specific thresholds
    if growth_stage == GrowthStage.VEGETATIVE:
        n_min, n_target = 100, 150
        p_min, p_target = 40, 60
        k_min, k_target = 100, 150
        stage_note = "During vegetative growth, nitrogen is critical for leaf development."
    elif growth_stage == GrowthStage.FLOWERING:
        n_min, n_target = 60, 100
        p_min, p_target = 50, 70
        k_min, k_target = 150, 200
        stage_note = "Flowering stage: reduce nitrogen, maintain high potassium for color."
    else:  # MAINTENANCE
        n_min, n_target = 80, 120
        p_min, p_target = 40, 60
        k_min, k_target = 80, 120
        stage_note = "Maintenance stage: balanced nutrition for plant health."
    
    # Check each nutrient
    if nitrogen < n_min:
        recommendations.append(
            f"Nitrogen low ({nitrogen} mg/kg). Increase N to {n_target} mg/kg "
            "using ammonium nitrate or calcium nitrate."
        )
    elif nitrogen > n_target * 1.5:
        recommendations.append(
            f"Nitrogen high ({nitrogen} mg/kg). Reduce N-rich fertilizer to prevent "
            "excessive vegetative growth at expense of blooms."
        )
    
    if phosphorus < p_min:
        recommendations.append(
            f"Phosphorus low ({phosphorus} mg/kg). Add phosphorus source "
            f"(target {p_target} mg/kg) to support root and flower development."
        )
    
    if potassium < k_min:
        recommendations.append(
            f"Potassium low ({potassium} mg/kg). Increase K to {k_target} mg/kg "
            "using potassium sulfate for improved flower quality and disease resistance."
        )
    elif potassium > k_target * 1.5:
        recommendations.append(
            f"Potassium high ({potassium} mg/kg). Reduce K fertilization to avoid "
            "calcium and magnesium uptake interference."
        )
    
    if not recommendations:
        return f"NPK levels adequate for current growth stage. {stage_note}"
    
    return " ".join(recommendations) + f" {stage_note}"


def generate_inm_recommendation(
    current_ec: float,
    predicted_ec: Optional[float],
    ph: float,
    nitrogen: float,
    phosphorus: float,
    potassium: float,
    growth_stage: GrowthStage = GrowthStage.VEGETATIVE,
) -> INMRecommendation:
    """Generate complete INM recommendation from sensor data.
    
    Args:
        current_ec: Current EC reading
        predicted_ec: ML-predicted EC for 24h ahead (can be None)
        ph: Current pH reading
        nitrogen: Nitrogen content (mg/kg)
        phosphorus: Phosphorus content (mg/kg)
        potassium: Potassium content (mg/kg)
        growth_stage: Current growth stage of roses
    
    Returns:
        Complete recommendation with actions and priority level.
    """
    ec_status = classify_ec_status(current_ec)
    ec_action = get_ec_action(current_ec, predicted_ec)
    ph_action = get_ph_action(ph)
    npk_action = get_npk_action(nitrogen, phosphorus, potassium, growth_stage)
    
    # Determine priority
    if ec_status in (ECStatus.CRITICAL_LOW, ECStatus.CRITICAL_HIGH):
        priority = "immediate"
    elif ec_status in (ECStatus.LOW, ECStatus.HIGH) or ph < PH_LOW_THRESHOLD or ph > PH_HIGH_THRESHOLD:
        priority = "routine"
    else:
        priority = "monitor"
    
    return INMRecommendation(
        ec_status=ec_status,
        ec_action=ec_action,
        ph_action=ph_action,
        npk_action=npk_action,
        priority=priority,
    )
