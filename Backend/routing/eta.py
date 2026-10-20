from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone

_EPS = 1e-9


def _as_utc(departure: datetime) -> datetime:
    """
    Return a timezone-aware UTC datetime.

    Naive datetimes are treated as UTC.
    Aware datetimes are converted to UTC.
    """
    if departure is None:
        raise ValueError("departure is required")

    if not isinstance(departure, datetime):
        raise TypeError("departure must be a datetime")

    if departure.tzinfo is None:
        return departure.replace(tzinfo=timezone.utc)

    return departure.astimezone(timezone.utc)


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

    # NaN check
    if result != result:
        return float(default)

    return result


def _clean_steps(steps: Sequence[Mapping] | None) -> list[tuple[float, float]]:
    """
    Convert OSRM-like step dictionaries into clean (distance, duration) tuples.

    Expected step shape:
        {
            "distance": meters,
            "duration": seconds
        }

    Distance units do not matter because we normalize by total step distance.
    """
    cleaned: list[tuple[float, float]] = []

    if not steps:
        return cleaned

    for step in steps:
        if not isinstance(step, Mapping):
            continue

        distance = _to_float(step.get("distance"), 0.0)
        duration = _to_float(step.get("duration"), 0.0)

        # Ignore zero-length steps for interpolation.
        if distance <= _EPS:
            continue

        if duration < 0:
            duration = 0.0

        cleaned.append((distance, duration))

    return cleaned


def _build_step_segments(
    steps: Sequence[Mapping] | None,
    total_duration_seconds: float,
) -> list[tuple[float, float, float, float]]:
    """
    Build normalized step segments for ETA interpolation.

    Returned segment shape:
        (
            start_distance_fraction,
            end_distance_fraction,
            start_duration_seconds,
            end_duration_seconds,
        )

    Step durations are scaled so the final cumulative duration matches
    total_duration_seconds. This protects against small mismatches between
    OSRM route duration and OSRM step duration sums.
    """
    cleaned = _clean_steps(steps)

    if not cleaned:
        return []

    total_distance = sum(distance for distance, _ in cleaned)

    if total_distance <= _EPS:
        return []

    total_duration_seconds = max(0.0, float(total_duration_seconds))
    raw_total_duration = sum(duration for _, duration in cleaned)

    # If step durations are all zero but route duration is positive,
    # we cannot meaningfully use steps. Fall back to linear interpolation.
    if raw_total_duration <= _EPS:
        return []

    scale = total_duration_seconds / raw_total_duration

    segments: list[tuple[float, float, float, float]] = []

    cumulative_distance = 0.0
    cumulative_duration = 0.0

    for distance, duration in cleaned:
        start_distance_fraction = cumulative_distance / total_distance
        start_duration = cumulative_duration

        cumulative_distance += distance
        cumulative_duration += duration * scale

        end_distance_fraction = cumulative_distance / total_distance
        end_duration = cumulative_duration

        segments.append(
            (
                start_distance_fraction,
                end_distance_fraction,
                start_duration,
                end_duration,
            )
        )

    # Force the final segment to end exactly at total duration.
    if segments:
        last = segments[-1]
        segments[-1] = (last[0], 1.0, last[2], total_duration_seconds)

    return segments


def _duration_for_fraction(
    fraction: float,
    segments: list[tuple[float, float, float, float]],
    total_duration_seconds: float,
) -> float:
    """
    Return elapsed seconds for a route fraction using step segments.
    """
    if fraction <= 0.0:
        return 0.0

    if fraction >= 1.0:
        return float(total_duration_seconds)

    for start_fraction, end_fraction, start_duration, end_duration in segments:
        if fraction <= end_fraction + 1e-12:
            denominator = end_fraction - start_fraction

            if denominator <= 1e-12:
                return float(start_duration)

            ratio = (fraction - start_fraction) / denominator

            if ratio < 0.0:
                ratio = 0.0
            elif ratio > 1.0:
                ratio = 1.0

            return float(start_duration + (end_duration - start_duration) * ratio)

    # Safety fallback.
    return float(total_duration_seconds * fraction)


def _estimate_eta_with_segments(
    departure_utc: datetime,
    mile_marker: float,
    total_miles: float,
    total_duration_seconds: float,
    segments: list[tuple[float, float, float, float]],
) -> datetime:
    """
    Internal ETA estimator using already-built step segments.
    """
    departure_utc = _as_utc(departure_utc)

    total_miles = _to_float(total_miles, 0.0)
    mile_marker = _to_float(mile_marker, 0.0)
    total_duration_seconds = max(0.0, _to_float(total_duration_seconds, 0.0))

    if total_miles <= _EPS or mile_marker <= _EPS:
        return departure_utc

    if mile_marker >= total_miles - _EPS:
        return departure_utc + timedelta(seconds=total_duration_seconds)

    fraction = mile_marker / total_miles

    if segments:
        elapsed_seconds = _duration_for_fraction(
            fraction=fraction,
            segments=segments,
            total_duration_seconds=total_duration_seconds,
        )
    else:
        elapsed_seconds = total_duration_seconds * fraction

    elapsed_seconds = min(max(elapsed_seconds, 0.0), total_duration_seconds)

    return departure_utc + timedelta(seconds=elapsed_seconds)


def estimate_eta(
    departure: datetime,
    mile_marker: float,
    total_miles: float,
    total_duration_seconds: float,
    steps: Sequence[Mapping] | None = None,
) -> datetime:
    """
    Estimate UTC arrival time for a single checkpoint mile marker.

    Args:
        departure:
            Timezone-aware or naive departure datetime.
            Naive datetimes are treated as UTC.

        mile_marker:
            Checkpoint distance from origin in miles.

        total_miles:
            Total route distance in miles.

        total_duration_seconds:
            Total route duration in seconds.

        steps:
            Optional OSRM-like step list.
            Each step may contain:
                {
                    "distance": meters,
                    "duration": seconds
                }

    Returns:
        Timezone-aware UTC datetime.
    """
    departure_utc = _as_utc(departure)
    total_duration_seconds = max(0.0, _to_float(total_duration_seconds, 0.0))
    segments = _build_step_segments(steps, total_duration_seconds)

    return _estimate_eta_with_segments(
        departure_utc=departure_utc,
        mile_marker=mile_marker,
        total_miles=total_miles,
        total_duration_seconds=total_duration_seconds,
        segments=segments,
    )


def estimate_checkpoint_etas(
    departure: datetime,
    checkpoints: Sequence[Mapping],
    total_miles: float,
    total_duration_seconds: float,
    steps: Sequence[Mapping] | None = None,
) -> list[dict]:
    """
    Estimate UTC ETAs for a list of checkpoints.

    Expected checkpoint shape:
        {
            "mile": float,
            "lat": float,
            "lng": float,
            ...
        }

    Also accepts:
        {
            "mile_marker": float,
            ...
        }

    Returns:
        A new list of checkpoint dictionaries sorted by mile marker.
        Each dictionary includes:
            eta_utc: timezone-aware UTC datetime
    """
    departure_utc = _as_utc(departure)
    total_duration_seconds = max(0.0, _to_float(total_duration_seconds, 0.0))
    total_miles_float = _to_float(total_miles, 0.0)
    segments = _build_step_segments(steps, total_duration_seconds)

    normalized: list[dict] = []

    for checkpoint in checkpoints or []:
        if isinstance(checkpoint, Mapping):
            item = dict(checkpoint)
            mile = item.get("mile", item.get("mile_marker", 0.0))
        else:
            item = {"mile": checkpoint}
            mile = checkpoint

        item["mile"] = _to_float(mile, 0.0)
        normalized.append(item)

    normalized.sort(key=lambda row: row["mile"])

    results: list[dict] = []
    previous_eta: datetime | None = None

    for item in normalized:
        eta = _estimate_eta_with_segments(
            departure_utc=departure_utc,
            mile_marker=item["mile"],
            total_miles=total_miles_float,
            total_duration_seconds=total_duration_seconds,
            segments=segments,
        )

        # Guarantee monotonic ETAs even if floating-point rounding
        # or unusual input ordering creates a tiny backward step.
        if previous_eta is not None and eta < previous_eta:
            eta = previous_eta

        previous_eta = eta
        item["eta_utc"] = eta
        results.append(item)

    return results
