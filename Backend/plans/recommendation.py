from __future__ import annotations

from collections.abc import Mapping

from core.constants import RiskLevel, RISK_SCORES


_EPS = 1e-9


_RISK_VALUES = {
    "LOW": RiskLevel.LOW,
    "MODERATE": RiskLevel.MODERATE,
    "HIGH": RiskLevel.HIGH,
    "SEVERE": RiskLevel.SEVERE,
    "NO_TRAVEL": RiskLevel.NO_TRAVEL,
}


_RISK_ORDER = [
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
]


def _to_float(value, default: float = 0.0) -> float:
    """
    Safely convert a value to float.

    None, invalid strings, and NaN become the default value.
    """
    if value is None:
        return float(default)

    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)

    # NaN check.
    if result != result:
        return float(default)

    return result


def _risk_key(value) -> RiskLevel:
    """
    Normalize a risk value into a RiskLevel member.

    Accepts:
        - RiskLevel members
        - strings like "LOW", "No Travel", "no-travel"
        - None
    """
    raw = getattr(value, "value", value)
    risk = str(raw).strip().upper().replace(" ", "_").replace("-", "_")

    return _RISK_VALUES.get(risk, RiskLevel.LOW)


def _score(risk) -> float:
    """
    Return numeric risk score for a risk value.
    """
    normalized = _risk_key(risk)
    return float(RISK_SCORES.get(normalized, 0.0))


def _higher_risk(a, b) -> RiskLevel:
    """
    Return the higher/more severe risk between a and b.
    """
    ra = _risk_key(a)
    rb = _risk_key(b)

    if _score(ra) >= _score(rb):
        return ra

    return rb


def _deduplicate_rows(rows: list[dict]) -> list[dict]:
    """
    Deduplicate checkpoint rows with nearly identical mile markers.

    When two rows have the same mile marker, keep the higher risk.
    """
    dedup: list[dict] = []

    for row in rows:
        if dedup and abs(row["mile"] - dedup[-1]["mile"]) <= 1e-6:
            dedup[-1]["risk"] = _higher_risk(dedup[-1]["risk"], row["risk"])
        else:
            dedup.append(
                {
                    "mile": row["mile"],
                    "risk": row["risk"],
                }
            )

    return dedup


def _normalize_checkpoint_rows(checkpoints) -> list[dict]:
    """
    Normalize checkpoint mappings into sorted rows:

        [
            {"mile": float, "risk": RiskLevel},
            ...
        ]
    """
    rows: list[dict] = []

    if not checkpoints:
        return rows

    for checkpoint in checkpoints:
        if not isinstance(checkpoint, Mapping):
            continue

        mile = checkpoint.get("mile", checkpoint.get("mile_marker"))

        if mile is None:
            continue

        risk = _risk_key(checkpoint.get("overall_risk", RiskLevel.LOW))

        rows.append(
            {
                "mile": _to_float(mile),
                "risk": risk,
            }
        )

    rows.sort(key=lambda row: row["mile"])

    return _deduplicate_rows(rows)


def aggregate_route_metrics(
    checkpoints,
    distance_miles: float,
    duration_seconds: float = 0.0,
) -> dict:
    """
    Aggregate checkpoint risks into route-level metrics.

    Returns a dictionary compatible with RouteOption fields:
        - distance_miles
        - duration_seconds
        - average_risk_score
        - low_miles
        - moderate_miles
        - high_miles
        - severe_miles
        - no_travel_miles
        - has_no_travel
        - worst_risk
        - worst_mile
    """
    total_miles = max(0.0, _to_float(distance_miles))
    duration = max(0.0, _to_float(duration_seconds))

    rows = _normalize_checkpoint_rows(checkpoints)

    miles_by_risk = {risk: 0.0 for risk in _RISK_ORDER}

    weighted = 0.0
    worst_risk = RiskLevel.LOW
    worst_mile = None

    has_no_travel = any(
        row["risk"] == RiskLevel.NO_TRAVEL
        for row in rows
    )

    # No checkpoints: treat the whole route as Low for deterministic behavior.
    if not rows:
        if total_miles > _EPS:
            miles_by_risk[RiskLevel.LOW] = total_miles

        return {
            "distance_miles": total_miles,
            "duration_seconds": duration,
            "average_risk_score": 0.0,
            "low_miles": miles_by_risk[RiskLevel.LOW],
            "moderate_miles": miles_by_risk[RiskLevel.MODERATE],
            "high_miles": miles_by_risk[RiskLevel.HIGH],
            "severe_miles": miles_by_risk[RiskLevel.SEVERE],
            "no_travel_miles": miles_by_risk[RiskLevel.NO_TRAVEL],
            "has_no_travel": False,
            "worst_risk": RiskLevel.LOW,
            "worst_mile": None,
        }

    # Zero-distance route: no mileage to aggregate, but checkpoint risk still matters.
    if total_miles <= _EPS:
        for row in rows:
            worst_risk = _higher_risk(worst_risk, row["risk"])

        worst_mile = rows[0]["mile"] if rows else None

        return {
            "distance_miles": total_miles,
            "duration_seconds": duration,
            "average_risk_score": 0.0,
            "low_miles": 0.0,
            "moderate_miles": 0.0,
            "high_miles": 0.0,
            "severe_miles": 0.0,
            "no_travel_miles": 0.0,
            "has_no_travel": bool(has_no_travel),
            "worst_risk": worst_risk,
            "worst_mile": worst_mile,
        }

    # Clamp checkpoint miles to the route range and re-deduplicate.
    points = [
        {
            "mile": min(max(row["mile"], 0.0), total_miles),
            "risk": row["risk"],
        }
        for row in rows
    ]

    points.sort(key=lambda point: point["mile"])
    points = _deduplicate_rows(points)

    if not points:
        miles_by_risk[RiskLevel.LOW] = total_miles

        return {
            "distance_miles": total_miles,
            "duration_seconds": duration,
            "average_risk_score": 0.0,
            "low_miles": miles_by_risk[RiskLevel.LOW],
            "moderate_miles": miles_by_risk[RiskLevel.MODERATE],
            "high_miles": miles_by_risk[RiskLevel.HIGH],
            "severe_miles": miles_by_risk[RiskLevel.SEVERE],
            "no_travel_miles": miles_by_risk[RiskLevel.NO_TRAVEL],
            "has_no_travel": False,
            "worst_risk": RiskLevel.LOW,
            "worst_mile": None,
        }

    # Ensure coverage from mile 0 to total route miles.
    if points[0]["mile"] > _EPS:
        points.insert(
            0,
            {
                "mile": 0.0,
                "risk": points[0]["risk"],
            },
        )
    else:
        points[0]["mile"] = 0.0

    if points[-1]["mile"] < total_miles - _EPS:
        points.append(
            {
                "mile": total_miles,
                "risk": points[-1]["risk"],
            }
        )
    else:
        points[-1]["mile"] = total_miles

    # Aggregate adjacent segments using the more severe endpoint risk.
    for i in range(len(points) - 1):
        start = points[i]
        end = points[i + 1]

        segment_miles = max(0.0, end["mile"] - start["mile"])

        if segment_miles <= _EPS:
            continue

        segment_risk = _higher_risk(start["risk"], end["risk"])

        miles_by_risk[segment_risk] += segment_miles
        weighted += segment_miles * _score(segment_risk)

        if _score(segment_risk) > _score(worst_risk):
            worst_risk = segment_risk
            worst_mile = end["mile"]

        if segment_risk == RiskLevel.NO_TRAVEL:
            has_no_travel = True

    # Safety net for tiny floating-point gaps.
    covered = sum(miles_by_risk.values())

    if total_miles - covered > 1e-6:
        remainder = total_miles - covered
        risk = points[-1]["risk"] if points else RiskLevel.LOW

        miles_by_risk[risk] += remainder
        weighted += remainder * _score(risk)

        if _score(risk) > _score(worst_risk):
            worst_risk = risk
            worst_mile = total_miles

        if risk == RiskLevel.NO_TRAVEL:
            has_no_travel = True

    average_risk_score = weighted / total_miles if total_miles > _EPS else 0.0

    if -1e-9 < average_risk_score < 0:
        average_risk_score = 0.0

    return {
        "distance_miles": total_miles,
        "duration_seconds": duration,
        "average_risk_score": average_risk_score,
        "low_miles": miles_by_risk[RiskLevel.LOW],
        "moderate_miles": miles_by_risk[RiskLevel.MODERATE],
        "high_miles": miles_by_risk[RiskLevel.HIGH],
        "severe_miles": miles_by_risk[RiskLevel.SEVERE],
        "no_travel_miles": miles_by_risk[RiskLevel.NO_TRAVEL],
        "has_no_travel": bool(
            has_no_travel
            or miles_by_risk[RiskLevel.NO_TRAVEL] > _EPS
        ),
        "worst_risk": worst_risk,
        "worst_mile": worst_mile,
    }


def route_sort_key(route: Mapping) -> tuple:
    """
    Deterministic sort key for route recommendation.

    Ascending order means better/safer routes come first.
    """
    return (
        1 if route.get("has_no_travel") else 0,
        _to_float(route.get("no_travel_miles")),
        _to_float(route.get("severe_miles")),
        _to_float(route.get("high_miles")),
        _to_float(route.get("average_risk_score")),
        _to_float(route.get("duration_seconds")),
        _to_float(route.get("distance_miles")),
        str(route.get("label") or ""),
    )


def rank_routes(routes) -> list[dict]:
    """
    Rank route dictionaries from best to worst.

    Accepts an iterable of mappings. Returns copied dictionaries with
    normalized numeric fields.
    """
    normalized: list[dict] = []

    for route in routes or []:
        if not isinstance(route, Mapping):
            continue

        item = dict(route)

        item["label"] = str(item.get("label") or "")
        item["has_no_travel"] = bool(item.get("has_no_travel"))

        for field in (
            "no_travel_miles",
            "severe_miles",
            "high_miles",
            "average_risk_score",
            "duration_seconds",
            "distance_miles",
        ):
            item[field] = _to_float(item.get(field))

        normalized.append(item)

    normalized.sort(key=route_sort_key)

    return normalized


def _format_miles(value) -> str:
    """
    Human-readable miles formatter.
    """
    miles = _to_float(value)

    if miles <= _EPS:
        return "0 mi"

    if miles < 10:
        return f"{miles:.1f} mi"

    return f"{int(round(miles))} mi"


def _format_duration(seconds) -> str:
    """
    Human-readable duration formatter.
    """
    total_seconds = int(round(_to_float(seconds)))

    if total_seconds < 0:
        total_seconds = 0

    if total_seconds < 60:
        return f"{total_seconds}s"

    hours = total_seconds // 3600
    remainder = total_seconds % 3600
    minutes = remainder // 60
    secs = remainder % 60

    if hours:
        if minutes:
            return f"{hours}h {minutes}m"
        return f"{hours}h"

    if secs:
        return f"{minutes}m {secs}s"

    return f"{minutes}m"


def build_recommendation_reasons(best: Mapping | None, ranked=None) -> list[str]:
    """
    Build human-readable reasons explaining why a route is recommended.
    """
    if not best:
        return []

    reasons: list[str] = []

    no_travel_miles = _to_float(best.get("no_travel_miles"))
    has_no_travel = bool(best.get("has_no_travel"))

    if has_no_travel and no_travel_miles <= _EPS:
        reasons.append("Contains a No-Travel checkpoint")
    elif has_no_travel:
        reasons.append(
            f"Fewest No-Travel miles: {_format_miles(no_travel_miles)}"
        )
    else:
        reasons.append("No No-Travel segments")

    severe_miles = _to_float(best.get("severe_miles"))

    if severe_miles <= _EPS:
        reasons.append("No severe miles")
    else:
        reasons.append(f"Severe miles: {_format_miles(severe_miles)}")

    high_miles = _to_float(best.get("high_miles"))

    if high_miles <= _EPS:
        reasons.append("No high-risk miles")
    else:
        reasons.append(f"High-risk miles: {_format_miles(high_miles)}")

    average_risk_score = _to_float(best.get("average_risk_score"))
    reasons.append(f"Average risk score: {average_risk_score:.2f}")

    duration_seconds = _to_float(best.get("duration_seconds"))
    reasons.append(
        f"Estimated travel time: {_format_duration(duration_seconds)}"
    )

    if ranked:
        others = [
            route
            for route in ranked
            if route is not best
        ]

        if others:
            next_route = others[0]
            next_label = str(next_route.get("label") or "alternative")

            next_severe_miles = _to_float(next_route.get("severe_miles"))
            if severe_miles < next_severe_miles - _EPS:
                reasons.append(
                    f"Fewer severe miles than {next_label}"
                )

            next_high_miles = _to_float(next_route.get("high_miles"))
            if high_miles < next_high_miles - _EPS:
                reasons.append(
                    f"Fewer high-risk miles than {next_label}"
                )

            next_average_risk = _to_float(next_route.get("average_risk_score"))
            if average_risk_score < next_average_risk - _EPS:
                reasons.append(
                    f"Lower average risk than {next_label}"
                )

            next_duration = _to_float(next_route.get("duration_seconds"))

            if duration_seconds < next_duration - 30:
                reasons.append(
                    "Arrives "
                    f"{_format_duration(next_duration - duration_seconds)} "
                    f"earlier than {next_label}"
                )
            elif duration_seconds > next_duration + 30:
                reasons.append(
                    "Trades "
                    f"{_format_duration(duration_seconds - next_duration)} "
                    "extra time for lower weather risk"
                )

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(reasons))


def recommend_routes(routes) -> dict:
    """
    Rank routes and mark the best route as recommended.

    Returns:
        {
            "recommended": dict | None,
            "ranked_routes": list[dict],
        }
    """
    ranked = rank_routes(routes)

    if not ranked:
        return {
            "recommended": None,
            "ranked_routes": [],
        }

    best = ranked[0]

    best["is_recommended"] = True
    best["recommendation_reasons"] = build_recommendation_reasons(
        best,
        ranked,
    )

    for route in ranked[1:]:
        route["is_recommended"] = False

        if route.get("recommendation_reasons") is None:
            route["recommendation_reasons"] = []

    return {
        "recommended": best,
        "ranked_routes": ranked,
    }
