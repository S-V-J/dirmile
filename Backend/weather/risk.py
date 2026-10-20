from core.constants import RiskLevel, higher_risk


def _to_nonnegative_float(value):
    """
    Convert a weather/load value to a non-negative float.

    Missing or invalid values are treated as 0.0 so that absent weather
    does not artificially increase risk.
    """
    if value is None:
        return 0.0

    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0

    # NaN check
    if number != number:
        return 0.0

    if number < 0:
        return 0.0

    return number


def _to_nonnegative_int(value):
    """
    Convert load weight to a non-negative integer.
    """
    return int(_to_nonnegative_float(value))


def classify_wind(wind_mph, load_lb=0):
    """
    Classify wind risk with truck load overrides.

    Returns:
        tuple[str, bool]
            (risk_level, load_override_applied)
    """
    wind = _to_nonnegative_float(wind_mph)
    load = _to_nonnegative_int(load_lb)

    # Load rule:
    # >=55 mph -> No Travel for any load
    if wind >= 55:
        return RiskLevel.NO_TRAVEL, True

    # Load rule:
    # 45-54 mph + >30,000 lb -> No Travel
    if wind >= 45:
        if load > 30000:
            return RiskLevel.NO_TRAVEL, True
        return RiskLevel.SEVERE, False

    # Load rule:
    # 35-44 mph + >40,000 lb -> Severe
    if wind >= 35:
        if load > 40000:
            return RiskLevel.SEVERE, True
        return RiskLevel.HIGH, False

    if wind >= 25:
        return RiskLevel.MODERATE, False

    return RiskLevel.LOW, False


def classify_rain(rain_in_hr):
    """
    Classify rain risk.

    Rain is measured in inches per hour.
    """
    rain = _to_nonnegative_float(rain_in_hr)

    if rain > 1.00:
        return RiskLevel.NO_TRAVEL

    if rain >= 0.50:
        return RiskLevel.SEVERE

    if rain >= 0.25:
        return RiskLevel.HIGH

    if rain >= 0.10:
        return RiskLevel.MODERATE

    return RiskLevel.LOW


def classify_snow(snow_in_hr):
    """
    Classify snow risk.

    Snow is measured in inches per hour.

    Important:
        Open-Meteo returns snowfall in centimeters.
        Conversion to inches must happen before calling this function.
    """
    snow = _to_nonnegative_float(snow_in_hr)

    if snow > 3.0:
        return RiskLevel.NO_TRAVEL

    if snow >= 2.0:
        return RiskLevel.SEVERE

    if snow >= 1.0:
        return RiskLevel.HIGH

    if snow >= 0.5:
        return RiskLevel.MODERATE

    return RiskLevel.LOW


def classify_checkpoint(wind_mph, rain_in_hr, snow_in_hr, load_lb=0):
    """
    Classify a single checkpoint using wind, rain, snow, and load rules.

    Returns:
        dict:
            {
                "wind_risk": str,
                "rain_risk": str,
                "snow_risk": str,
                "overall_risk": str,
                "load_override_applied": bool,
            }
    """
    wind_risk, load_override_applied = classify_wind(
        wind_mph=wind_mph,
        load_lb=load_lb,
    )

    rain_risk = classify_rain(rain_in_hr)
    snow_risk = classify_snow(snow_in_hr)

    overall_risk = higher_risk(
        higher_risk(wind_risk, rain_risk),
        snow_risk,
    )

    return {
        "wind_risk": wind_risk,
        "rain_risk": rain_risk,
        "snow_risk": snow_risk,
        "overall_risk": overall_risk,
        "load_override_applied": load_override_applied,
    }
