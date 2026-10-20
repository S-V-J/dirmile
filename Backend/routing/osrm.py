from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests
from django.conf import settings


DEFAULT_ROUTING_BASE_URL = "https://router.project-osrm.org"
METERS_PER_MILE = 1609.344
USER_AGENT = "Dirmile/0.1 (+https://github.com/S-V-J/dirmile)"


class RoutingError(Exception):
    """
    Base exception for routing failures.
    """


class RoutingNoRouteError(RoutingError):
    """
    Raised when the routing provider cannot find a route.
    """


class RoutingAPIError(RoutingError):
    """
    Raised when the routing provider returns an HTTP or provider-level error.
    """

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _safe_float(value, default: float = 0.0) -> float:
    """
    Convert a value to float safely.

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


def _clamp_alternatives(value) -> int:
    """
    Clamp requested alternatives to a safe integer range.

    OSRM public demo supports multiple alternatives, but Dirmile intentionally
    caps this to avoid abusive requests.
    """
    if value is None:
        value = 3

    try:
        alternatives = int(value)
    except (TypeError, ValueError):
        alternatives = 3

    return max(1, min(alternatives, 10))


def _format_coordinate_number(value: float) -> str:
    """
    Format a coordinate number for OSRM URL paths.

    Avoids unnecessary trailing zeros and negative zero.
    """
    number = float(value)

    if abs(number) < 1e-12:
        number = 0.0

    return format(number, ".10g")


def _validate_coordinate(coordinate, label: str) -> tuple[float, float]:
    """
    Validate a coordinate pair.

    Expected:
        (latitude, longitude)

    Returns:
        (lat, lng) as floats.
    """
    if isinstance(coordinate, Mapping):
        lat_raw = coordinate.get("lat", coordinate.get("latitude"))
        lng_raw = coordinate.get("lng", coordinate.get("lon", coordinate.get("longitude")))
    elif isinstance(coordinate, Sequence) and not isinstance(coordinate, (str, bytes)):
        if len(coordinate) != 2:
            raise ValueError(f"{label} must contain exactly two values: (lat, lng).")

        lat_raw, lng_raw = coordinate
    else:
        raise ValueError(f"{label} must be a (lat, lng) pair or mapping.")

    try:
        lat = float(lat_raw)
        lng = float(lng_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} coordinates must be numeric.") from exc

    if not math.isfinite(lat) or not math.isfinite(lng):
        raise ValueError(f"{label} coordinates must be finite numbers.")

    if lat < -90.0 or lat > 90.0:
        raise ValueError(f"{label} latitude must be between -90 and 90.")

    if lng < -180.0 or lng > 180.0:
        raise ValueError(f"{label} longitude must be between -180 and 180.")

    return lat, lng


def _route_label(index: int) -> str:
    """
    Return a human-friendly route label.

    Examples:
        0 -> Route A
        1 -> Route B
        2 -> Route C
    """
    if index < 26:
        return f"Route {chr(ord('A') + index)}"

    return f"Route {index + 1}"


def build_route_url(
    origin,
    destination,
    alternatives=3,
    base_url: str | None = None,
) -> str:
    """
    Build an OSRM driving route URL.

    Args:
        origin:
            (lat, lng) or mapping with lat/lng.

        destination:
            (lat, lng) or mapping with lat/lng.

        alternatives:
            Number of alternative routes to request.
            Dirmile normally uses 3.

        base_url:
            Optional OSRM base URL.
            Defaults to settings.ROUTING_BASE_URL.

    Returns:
        Full OSRM URL string.
    """
    lat1, lng1 = _validate_coordinate(origin, "origin")
    lat2, lng2 = _validate_coordinate(destination, "destination")

    if abs(lat1 - lat2) < 1e-9 and abs(lng1 - lng2) < 1e-9:
        raise ValueError("Origin and destination cannot be identical.")

    alternatives = _clamp_alternatives(alternatives)

    base = (
        base_url
        or getattr(settings, "ROUTING_BASE_URL", DEFAULT_ROUTING_BASE_URL)
        or DEFAULT_ROUTING_BASE_URL
    )

    base = str(base).strip()

    if not base:
        raise ValueError("Routing base URL cannot be empty.")

    if "://" not in base:
        base = f"https://{base}"

    parsed = urlsplit(base)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Routing base URL must use http or https.")

    if not parsed.netloc:
        raise ValueError("Routing base URL must include a host.")

    coords = (
        f"{_format_coordinate_number(lng1)},"
        f"{_format_coordinate_number(lat1)};"
        f"{_format_coordinate_number(lng2)},"
        f"{_format_coordinate_number(lat2)}"
    )

    base_path = parsed.path.rstrip("/")
    path = f"{base_path}/route/v1/driving/{coords}"

    params = {
        "alternatives": str(alternatives),
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
    }

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            path,
            urlencode(params),
            "",
        )
    )


def _extract_steps(route: Mapping) -> list[dict]:
    """
    Extract flattened OSRM steps from a route.

    OSRM returns steps inside legs:
        route.legs[].steps[]

    Dirmile ETA logic only needs a flat ordered list of steps.
    """
    steps: list[dict] = []

    legs = route.get("legs")

    if not isinstance(legs, list):
        return steps

    for leg in legs:
        if not isinstance(leg, Mapping):
            continue

        leg_steps = leg.get("steps")

        if not isinstance(leg_steps, list):
            continue

        for step in leg_steps:
            if not isinstance(step, Mapping):
                continue

            steps.append(
                {
                    "distance": _safe_float(step.get("distance"), 0.0),
                    "duration": _safe_float(step.get("duration"), 0.0),
                    "name": str(step.get("name") or ""),
                }
            )

    return steps


def normalize_osrm_response(payload, max_routes=3) -> list[dict]:
    """
    Normalize an OSRM route response into Dirmile route dictionaries.

    Returns:
        [
            {
                "label": "Route A",
                "route_index": 0,
                "distance_miles": float,
                "duration_seconds": float,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[lng, lat], ...]
                },
                "steps": [
                    {
                        "distance": float,
                        "duration": float,
                        "name": str
                    },
                    ...
                ]
            },
            ...
        ]
    """
    if not isinstance(payload, Mapping):
        raise RoutingError("OSRM response must be a JSON object.")

    code = str(payload.get("code") or "").strip()

    if code == "NoRoute":
        raise RoutingNoRouteError("OSRM could not find a route for these coordinates.")

    if code != "Ok":
        raise RoutingAPIError(f"OSRM returned unexpected code: {code or 'unknown'}.")

    raw_routes = payload.get("routes")

    if not isinstance(raw_routes, list) or not raw_routes:
        raise RoutingNoRouteError("OSRM returned no routes.")

    max_routes = _clamp_alternatives(max_routes)
    normalized: list[dict] = []

    for index, route in enumerate(raw_routes[:max_routes]):
        if not isinstance(route, Mapping):
            raise RoutingError("Each OSRM route must be a JSON object.")

        geometry = route.get("geometry")

        if not isinstance(geometry, Mapping):
            raise RoutingError("OSRM route is missing geometry.")

        if geometry.get("type") != "LineString":
            raise RoutingError("OSRM route geometry must be a GeoJSON LineString.")

        coordinates = geometry.get("coordinates")

        if not isinstance(coordinates, list) or len(coordinates) < 2:
            raise RoutingError("OSRM route geometry must contain at least two coordinates.")

        distance_meters = max(0.0, _safe_float(route.get("distance"), 0.0))
        duration_seconds = max(0.0, _safe_float(route.get("duration"), 0.0))

        normalized.append(
            {
                "label": _route_label(index),
                "route_index": index,
                "distance_miles": distance_meters / METERS_PER_MILE,
                "duration_seconds": duration_seconds,
                "geometry": dict(geometry),
                "steps": _extract_steps(route),
            }
        )

    return normalized


def fetch_routes(
    origin,
    destination,
    alternatives=3,
    *,
    base_url: str | None = None,
    timeout: float | None = None,
    session=None,
) -> list[dict]:
    """
    Fetch normalized route options from OSRM.

    Args:
        origin:
            (lat, lng) or mapping with lat/lng.

        destination:
            (lat, lng) or mapping with lat/lng.

        alternatives:
            Number of route alternatives to request.

        base_url:
            Optional OSRM base URL.

        timeout:
            Optional request timeout in seconds.
            Defaults to settings.ROUTING_TIMEOUT_SECONDS.

        session:
            Optional requests-like session object.
            Defaults to the global requests module.

    Returns:
        List of normalized route dictionaries.

    Raises:
        ValueError:
            For invalid coordinates or invalid base URL.

        RoutingNoRouteError:
            When OSRM cannot find a route.

        RoutingAPIError:
            When OSRM returns HTTP or provider-level errors.

        RoutingError:
            For malformed responses or transport failures.
    """
    alternatives = _clamp_alternatives(alternatives)
    url = build_route_url(
        origin=origin,
        destination=destination,
        alternatives=alternatives,
        base_url=base_url,
    )

    if timeout is None:
        timeout = getattr(settings, "ROUTING_TIMEOUT_SECONDS", 10.0)

    timeout = max(1.0, _safe_float(timeout, 10.0))

    http_session = session or requests

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    try:
        response = http_session.get(
            url,
            timeout=timeout,
            headers=headers,
        )
    except requests.RequestException as exc:
        raise RoutingError(f"Routing request failed: {exc}") from exc

    status_code = getattr(response, "status_code", None)

    if status_code is not None and status_code >= 400:
        body = str(getattr(response, "text", "") or "")[:200]
        raise RoutingAPIError(
            f"Routing API HTTP {status_code}: {body}",
            status_code=status_code,
        )

    try:
        payload = response.json()
    except Exception as exc:
        raise RoutingError("Routing API returned invalid JSON.") from exc

    return normalize_osrm_response(payload, max_routes=alternatives)
