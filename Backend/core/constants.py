from django.db import models


class RiskLevel(models.TextChoices):
    LOW = "LOW", "Low"
    MODERATE = "MODERATE", "Moderate"
    HIGH = "HIGH", "High"
    SEVERE = "SEVERE", "Severe"
    NO_TRAVEL = "NO_TRAVEL", "No Travel"


RISK_SCORES = {
    RiskLevel.LOW: 0,
    RiskLevel.MODERATE: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.SEVERE: 3,
    RiskLevel.NO_TRAVEL: 4,
}


RISK_LEVEL_ORDER = [
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
]


def higher_risk(a, b):
    """
    Return the higher/more severe risk level between a and b.

    Accepts string values or RiskLevel enum values.
    """
    a_value = str(a)
    b_value = str(b)

    a_score = RISK_SCORES.get(a_value, 0)
    b_score = RISK_SCORES.get(b_value, 0)

    if a_score >= b_score:
        return a_value

    return b_value
