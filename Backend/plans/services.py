from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from django.conf import settings
from django.db import transaction

from core.geo import (
    generate_checkpoints,
    generate_heatmap_points,
    geojson_linestring_to_points,
    total_route_miles,
)
from plans.models import Checkpoint, RouteOption, TripPlan
from plans.recommendation import aggregate_route_metrics, recommend_routes
from routing.eta import estimate_checkpoint_etas
from routing.osrm import RoutingError
from routing.osrm import fetch_routes as default_fetch_routes
from weather.forecast import WeatherError
from weather.forecast import fetch_forecast as default_fetch_forecast
from weather.forecast import get_weather_at_time
from weather.risk import classify_checkpoint


VALID_INTERVALS = {10, 25, 50}
HEATMAP_HOURS_DEFAULT = 49

_RISK_SCORES = {
    "LOW": 0.0,
    "MODERATE": 1.0,
    "HIGH": 2.0,
    "SEVERE": 3.0,
    "NO_TRAVEL": 4.0,
}


class PlanServiceError(Exception):
    """
    Base exception for trip plan orchestration failures.
    """


class PlaceResolutionError(PlanServiceError):
    """
    Raised when origin or destination cannot be resolved.
    """


class RouteGenerationError(PlanServiceError):
    """
    Raised when routing fails or returns unusable route data.
    """


class WeatherSamplingError(PlanServiceError):
    """
    Raised when weather sampling fails.
    """


def _safe_float(value, default: float = 0.0) -> float:
    """
    Convert a value to float safely.
    None, invalid strings, NaN, and infinity become the default value.
    """
    if value is None:
        return float(default)

    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)

    if not math.isfinite(result):
        return float(default)

    return result


def _as_utc(dt: datetime | str) -> datetime:
    """
    Return a timezone-aware UTC datetime.
    Naive datetimes are treated as UTC.
    Aware datetimes are converted to UTC.
    Strings are parsed as ISO 8601.
    """
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)

    if not isinstance(dt, datetime):
        raise TypeError("departure must be a datetime or ISO 8601 string")

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def _risk_string(risk) -> str:
    """
    Normalize a risk value into an uppercase string.
    Accepts RiskLevel members or plain strings.
    """
    raw = getattr(risk, "value", risk)
    return str(raw).strip().upper().replace(" ", "_").replace("-", "_")


def _risk_score(risk) -> float:
    """
    Return numeric risk score for a risk value.
    """
    return float(_RISK_SCORES.get(_risk_string(risk), 0.0))


def _coord_key(lat, lng) -> str:
    """
    Deterministic coordinate key rounded to 6 decimal places.
    """
    return f"{float(lat):.6f},{float(lng):.6f}"


def _default_weather() -> dict:
    """
    Safe default weather values when no forecast data is available.
    """
    return {
        "wind_speed_mph": 0.0,
        "wind_gust_mph": None,
        "rain_in_hr": 0.0,
        "snow_in_hr": 0.0,
        "temperature_f": None,
        "weather_code": None,
        "matched_time": None,
    }


def _chunked(sequence: Sequence, size: int):
    """
    Yield chunks from a sequence.
    """
    if size <= 0:
        size = 1

    for index in range(0, len(sequence), size):
        yield sequence[index : index + size]


def _clamp_routes(value) -> int:
    """
    Clamp requested route count to a safe integer range.
    """
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = 3

    return max(1, min(count, 10))


def _route_label(index: int) -> str:
    """
    Return a human-friendly route label.
    """
    if index < 26:
        return f"Route {chr(ord('A') + index)}"

    return f"Route {index + 1}"


def _unique_coordinates(raw_coords: Sequence) -> list[tuple[float, float]]:
    """
    Deduplicate coordinates while preserving order.
    """
    seen: set[str] = set()
    cleaned: list[tuple[float, float]] = []

    for coord in raw_coords:
        if isinstance(coord, Mapping):
            lat_raw = coord.get("lat", coord.get("latitude"))
            lng_raw = coord.get("lng", coord.get("lon", coord.get("longitude")))
        else:
            try:
                lat_raw, lng_raw = coord
            except (TypeError, ValueError):
                continue

        try:
            lat = float(lat_raw)
            lng = float(lng_raw)
        except (TypeError, ValueError):
            continue

        if not math.isfinite(lat) or not math.isfinite(lng):
            continue

        key = _coord_key(lat, lng)

        if key in seen:
            continue

        seen.add(key)
        cleaned.append((lat, lng))

    return cleaned


def _limit_checkpoints(checkpoints: list[dict], max_count: int) -> list[dict]:
    """
    Limit checkpoint count while preserving origin and destination.
    This is a safety cap for extremely long routes at small intervals.
    """
    if not checkpoints:
        return []

    try:
        max_count = int(max_count)
    except (TypeError, ValueError):
        max_count = 1000

    if max_count <= 0:
        max_count = 1000

    if len(checkpoints) <= max_count:
        return checkpoints

    if max_count == 1:
        return [checkpoints[0]]

    indices: list[int] = []
    last_index = -1
    final_index = len(checkpoints) - 1

    for i in range(max_count):
        index = round(i * final_index / float(max_count - 1))

        if index != last_index:
            indices.append(index)
            last_index = index

    if indices[-1] != final_index:
        indices.append(final_index)

    return [checkpoints[index] for index in indices]


def _normalize_place(place: Any, fallback_name: str = "") -> dict:
    """
    Normalize a geocoding result into Dirmile's internal place shape.
    """
    if not isinstance(place, Mapping):
        raise PlaceResolutionError("Geocoding result must be a JSON object.")

    lat_raw = place.get("latitude", place.get("lat"))
    lng_raw = place.get("longitude", place.get("lon", place.get("lng")))

    if lat_raw is None or lng_raw is None:
        raise PlaceResolutionError("Geocoding result is missing latitude or longitude.")

    try:
        lat = float(lat_raw)
        lng = float(lng_raw)
    except (TypeError, ValueError) as exc:
        raise PlaceResolutionError("Geocoding coordinates must be numeric.") from exc

    if not math.isfinite(lat) or not math.isfinite(lng):
        raise PlaceResolutionError("Geocoding coordinates must be finite numbers.")

    if lat < -90.0 or lat > 90.0:
        raise PlaceResolutionError("Geocoding latitude must be between -90 and 90.")

    if lng < -180.0 or lng > 180.0:
        raise PlaceResolutionError("Geocoding longitude must be between -180 and 180.")

    name = str(place.get("name") or fallback_name or "").strip()
    display_name = str(place.get("display_name") or name or fallback_name or "").strip()
    timezone_name = str(place.get("timezone") or "").strip()

    return {
        "name": name,
        "display_name": display_name,
        "latitude": lat,
        "longitude": lng,
        "timezone": timezone_name,
    }


def _default_geocode(query: str, country_code: str | None = None) -> Any:
    """
    Default geocoding adapter.

    This tries common function names exposed by Backend/weather/geocoding.py.
    Tests inject their own geocode_fn, so this adapter is mainly for runtime use.
    """
    from weather import geocoding as geocoding_module

    fn = None

    for name in ("search_places", "geocode", "search", "autocomplete"):
        candidate = getattr(geocoding_module, name, None)

        if callable(candidate):
            fn = candidate
            break

    if fn is None:
        raise NotImplementedError(
            "No geocoding function found in weather.geocoding. "
            "Expected one of: search_places, geocode, search, autocomplete."
        )

    attempts: list[dict] = []

    if country_code:
        attempts.append({"query": query, "country_code": country_code})
        attempts.append({"q": query, "country": country_code})

    attempts.append({"query": query})
    attempts.append({"q": query})

    last_exc: Exception | None = None

    for kwargs in attempts:
        try:
            return fn(**kwargs)
        except TypeError as exc:
            last_exc = exc
            continue

    try:
        return fn(query)
    except Exception as exc:
        if last_exc is not None:
            raise last_exc

        raise exc


def resolve_place(
    query: str,
    country_code: str | None = None,
    geocode_fn: Callable[..., Any] | None = None,
) -> dict:
    """
    Resolve a free-text place query into a normalized place dictionary.
    """
    query = str(query or "").strip()

    if not query:
        raise PlaceResolutionError("Place query cannot be empty.")

    fn = geocode_fn or _default_geocode

    try:
        results = fn(query=query, country_code=country_code)
    except TypeError:
        try:
            results = fn(query)
        except Exception as exc:
            raise PlaceResolutionError(
                f'Unable to resolve location for "{query}".'
            ) from exc
    except Exception as exc:
        raise PlaceResolutionError(
            f'Unable to resolve location for "{query}".'
        ) from exc

    if isinstance(results, Mapping):
        results = [results]

    if not results:
        raise PlaceResolutionError(f'No location found for "{query}".')

    return _normalize_place(results[0], fallback_name=query)


def _prepare_route(
    route: Mapping,
    plan: TripPlan,
    index: int,
    max_heatmap_points: int,
) -> dict:
    """
    Convert one normalized OSRM route into checkpoints, ETAs, and heatmap points.
    """
    geometry = route.get("geometry")

    if not isinstance(geometry, Mapping):
        raise ValueError("Route is missing GeoJSON geometry.")

    points = geojson_linestring_to_points(geometry)

    checkpoints = generate_checkpoints(points, plan.interval_miles)

    max_checkpoints = int(
        getattr(settings, "PLAN_MAX_CHECKPOINTS_PER_ROUTE", 1000)
    )

    checkpoints = _limit_checkpoints(checkpoints, max_checkpoints)

    geometry_distance = total_route_miles(points)
    distance_miles = _safe_float(route.get("distance_miles"), geometry_distance)

    if distance_miles <= 0.0:
        distance_miles = geometry_distance

    duration_seconds = max(0.0, _safe_float(route.get("duration_seconds"), 0.0))

    checkpoints = estimate_checkpoint_etas(
        departure=plan.departure,
        checkpoints=checkpoints,
        total_miles=distance_miles,
        total_duration_seconds=duration_seconds,
        steps=route.get("steps"),
    )

    heatmap_points = generate_heatmap_points(
        points,
        max_points=max_heatmap_points,
    )

    label = str(route.get("label") or _route_label(index)).strip()

    try:
        route_index = int(route.get("route_index", index))
    except (TypeError, ValueError):
        route_index = index

    return {
        "label": label,
        "route_index": route_index,
        "distance_miles": float(distance_miles),
        "duration_seconds": float(duration_seconds),
        "geometry": dict(geometry),
        "steps": route.get("steps") or [],
        "checkpoints": checkpoints,
        "heatmap_points": heatmap_points,
    }


def _collect_coordinates(prepared_routes: Sequence[Mapping]) -> list[tuple[float, float]]:
    """
    Collect all unique coordinates needed for weather sampling.
    """
    raw_coords: list[tuple[float, float]] = []

    for prepared in prepared_routes:
        for checkpoint in prepared.get("checkpoints", []):
            raw_coords.append((checkpoint["lat"], checkpoint["lng"]))

        for heatmap_point in prepared.get("heatmap_points", []):
            raw_coords.append((heatmap_point["lat"], heatmap_point["lng"]))

    return _unique_coordinates(raw_coords)


def _fetch_weather_lookup(
    coordinates: Sequence[tuple[float, float]],
    start_time: datetime,
    end_time: datetime,
    forecast_fn: Callable[..., Any] | None = None,
) -> dict[str, dict]:
    """
    Fetch weather for all coordinates in safe batches and return a lookup map.
    """
    if not coordinates:
        return {}

    fn = forecast_fn or default_fetch_forecast
    max_batch = int(getattr(settings, "WEATHER_MAX_BATCH_COORDINATES", 200))

    if max_batch <= 0:
        max_batch = 200

    results: list[Any] = []

    try:
        for chunk in _chunked(list(coordinates), max_batch):
            chunk_results = fn(chunk, start_time, end_time)

            if chunk_results is None:
                continue

            if isinstance(chunk_results, Mapping):
                chunk_results = [chunk_results]

            results.extend(list(chunk_results))
    except WeatherError as exc:
        raise WeatherSamplingError(str(exc)) from exc

    lookup: dict[str, dict] = {}

    for index, item in enumerate(results):
        if not isinstance(item, Mapping):
            continue

        lat = item.get("latitude")
        lng = item.get("longitude")

        if (lat is None or lng is None) and index < len(coordinates):
            lat, lng = coordinates[index]

        if lat is None or lng is None:
            continue

        try:
            key = _coord_key(float(lat), float(lng))
        except (TypeError, ValueError):
            continue

        lookup[key] = dict(item)

    return lookup


def _build_heatmap_points(
    heatmap_points: Sequence[Mapping],
    weather_lookup: Mapping[str, Mapping],
    start_time: datetime,
    load_lb: int,
) -> list[dict]:
    """
    Build dense corridor heatmap points with hourly arrays for the 0–48 slider.
    """
    try:
        hours = int(getattr(settings, "PLAN_HEATMAP_HOURS", HEATMAP_HOURS_DEFAULT))
    except (TypeError, ValueError):
        hours = HEATMAP_HOURS_DEFAULT

    if hours < 1:
        hours = 1

    built: list[dict] = []

    for point in heatmap_points:
        lat = float(point["lat"])
        lng = float(point["lng"])
        mile = float(point["mile"])

        coordinate_data = weather_lookup.get(_coord_key(lat, lng))

        hourly_risk: list[int] = []
        hourly_wind: list[float] = []
        hourly_rain: list[float] = []
        hourly_snow: list[float] = []

        for hour in range(hours):
            target_time = start_time + timedelta(hours=hour)

            if coordinate_data:
                weather = get_weather_at_time(coordinate_data, target_time)
            else:
                weather = _default_weather()

            risk = classify_checkpoint(
                wind_mph=weather["wind_speed_mph"],
                rain_in_hr=weather["rain_in_hr"],
                snow_in_hr=weather["snow_in_hr"],
                load_lb=load_lb,
            )

            hourly_risk.append(int(_risk_score(risk["overall_risk"])))
            hourly_wind.append(float(weather["wind_speed_mph"]))
            hourly_rain.append(float(weather["rain_in_hr"]))
            hourly_snow.append(float(weather["snow_in_hr"]))

        built.append(
            {
                "mile": mile,
                "lat": lat,
                "lng": lng,
                "hourly_risk": hourly_risk,
                "hourly_wind": hourly_wind,
                "hourly_rain": hourly_rain,
                "hourly_snow": hourly_snow,
            }
        )

    return built


def _mark_plan_failed(plan: TripPlan, message: Any) -> None:
    """
    Persist failure state on a TripPlan.
    """
    plan.status = TripPlan.STATUS_FAILED
    plan.error_message = str(message or "")[:2000]
    plan.save(update_fields=["status", "error_message", "updated_at"])


def build_plan_response(
    plan: TripPlan,
    heatmap_by_route_id: Mapping[str, Sequence[Mapping]] | None = None,
) -> dict:
    """
    Build the JSON-ready response for a completed or failed TripPlan.
    """
    heatmap_by_route_id = heatmap_by_route_id or {}
    routes: list[dict] = []

    for route in plan.route_options.all():
        checkpoints: list[dict] = []

        for checkpoint in route.checkpoints.all():
            checkpoints.append(
                {
                    "id": str(checkpoint.id),
                    "mile_marker": checkpoint.mile_marker,
                    "lat": checkpoint.lat,
                    "lng": checkpoint.lng,
                    "eta_utc": checkpoint.eta_utc.isoformat(),
                    "wind_mph": checkpoint.wind_mph,
                    "wind_gust_mph": checkpoint.wind_gust_mph,
                    "rain_in_hr": checkpoint.rain_in_hr,
                    "snow_in_hr": checkpoint.snow_in_hr,
                    "temperature_f": checkpoint.temperature_f,
                    "weather_code": checkpoint.weather_code,
                    "wind_risk": checkpoint.wind_risk,
                    "rain_risk": checkpoint.rain_risk,
                    "snow_risk": checkpoint.snow_risk,
                    "overall_risk": checkpoint.overall_risk,
                    "load_override_applied": checkpoint.load_override_applied,
                }
            )

        worst_risk = "LOW"
        worst_score = 0.0

        for checkpoint in checkpoints:
            score = _risk_score(checkpoint["overall_risk"])

            if score > worst_score:
                worst_score = score
                worst_risk = _risk_string(checkpoint["overall_risk"])

        has_no_travel = (
            route.no_travel_miles > 0
            or any(cp["overall_risk"] == "NO_TRAVEL" for cp in checkpoints)
        )

        routes.append(
            {
                "id": str(route.id),
                "label": route.label,
                "route_index": route.route_index,
                "recommended": bool(route.is_recommended),
                "distance_miles": route.distance_miles,
                "duration_seconds": route.duration_seconds,
                "duration_hours": round(route.duration_seconds / 3600.0, 2),
                "arrival": (
                    plan.departure + timedelta(seconds=route.duration_seconds)
                ).isoformat(),
                "average_risk": route.average_risk_score,
                "low_miles": route.low_miles,
                "moderate_miles": route.moderate_miles,
                "high_miles": route.high_miles,
                "severe_miles": route.severe_miles,
                "no_travel_miles": route.no_travel_miles,
                "has_no_travel": has_no_travel,
                "worst_risk": worst_risk,
                "recommendation_reasons": route.recommendation_reasons or [],
                "geometry": route.geometry,
                "checkpoints": checkpoints,
                "heatmap_points": list(
                    heatmap_by_route_id.get(str(route.id), [])
                ),
            }
        )

    recommended_route_id = None

    for route in routes:
        if route["recommended"]:
            recommended_route_id = route["id"]
            break

    return {
        "plan_id": str(plan.id),
        "status": plan.status,
        "error_message": plan.error_message,
        "origin": {
            "name": plan.origin_name,
            "latitude": plan.origin_lat,
            "longitude": plan.origin_lng,
            "timezone": plan.origin_timezone,
        },
        "destination": {
            "name": plan.destination_name,
            "latitude": plan.destination_lat,
            "longitude": plan.destination_lng,
            "timezone": plan.destination_timezone,
        },
        "departure": plan.departure.isoformat(),
        "load_lb": plan.load_lb,
        "interval_miles": plan.interval_miles,
        "recommended_route_id": recommended_route_id,
        "routes": routes,
    }


def create_trip_plan(
    *,
    user,
    origin: str,
    destination: str,
    departure: datetime | str,
    load_lb: int,
    interval_miles: int,
    geocode_fn: Callable[..., Any] | None = None,
    route_fn: Callable[..., Any] | None = None,
    forecast_fn: Callable[..., Any] | None = None,
    max_heatmap_points: int | None = None,
) -> dict:
    """
    Create and process a full trip plan.

    This is the main orchestration entry point for the backend plan API.
    """
    try:
        interval = int(interval_miles)
    except (TypeError, ValueError) as exc:
        raise ValueError("interval_miles must be an integer.") from exc

    if interval not in VALID_INTERVALS:
        raise ValueError("interval_miles must be one of: 10, 25, 50.")

    try:
        load = int(load_lb)
    except (TypeError, ValueError) as exc:
        raise ValueError("load_lb must be an integer.") from exc

    if load < 0:
        raise ValueError("load_lb cannot be negative.")

    departure_dt = _as_utc(departure)

    country_code = getattr(user, "country_code", "") or None

    origin_place = resolve_place(
        origin,
        country_code=country_code,
        geocode_fn=geocode_fn,
    )

    destination_place = resolve_place(
        destination,
        country_code=country_code,
        geocode_fn=geocode_fn,
    )

    if (
        abs(origin_place["latitude"] - destination_place["latitude"]) < 1e-9
        and abs(origin_place["longitude"] - destination_place["longitude"]) < 1e-9
    ):
        raise PlaceResolutionError("Origin and destination cannot be identical.")

    plan = TripPlan.objects.create(
        user=user,
        origin_name=origin_place["display_name"] or origin_place["name"],
        origin_lat=origin_place["latitude"],
        origin_lng=origin_place["longitude"],
        origin_timezone=origin_place["timezone"],
        destination_name=(
            destination_place["display_name"] or destination_place["name"]
        ),
        destination_lat=destination_place["latitude"],
        destination_lng=destination_place["longitude"],
        destination_timezone=destination_place["timezone"],
        departure=departure_dt,
        load_lb=load,
        interval_miles=interval,
        status=TripPlan.STATUS_PROCESSING,
    )

    try:
        route_fn = route_fn or default_fetch_routes
        max_routes = _clamp_routes(
            getattr(settings, "ROUTING_MAX_ALTERNATIVES", 3)
        )

        origin_coord = (
            origin_place["latitude"],
            origin_place["longitude"],
        )

        destination_coord = (
            destination_place["latitude"],
            destination_place["longitude"],
        )

        try:
            routes = route_fn(
                origin_coord,
                destination_coord,
                alternatives=max_routes,
            )
        except TypeError:
            routes = route_fn(origin_coord, destination_coord)
        except RoutingError as exc:
            raise RouteGenerationError(str(exc)) from exc

        if isinstance(routes, Mapping):
            routes = [routes]

        if not routes:
            raise RouteGenerationError("Routing API returned no routes.")

        if max_heatmap_points is None:
            heatmap_limit = int(
                getattr(settings, "PLAN_MAX_HEATMAP_POINTS", 500)
            )
        else:
            heatmap_limit = int(max_heatmap_points)

        if heatmap_limit < 1:
            heatmap_limit = 1

        prepared_routes: list[dict] = []

        for index, route in enumerate(list(routes)[:max_routes]):
            try:
                prepared_routes.append(
                    _prepare_route(
                        route=route,
                        plan=plan,
                        index=index,
                        max_heatmap_points=heatmap_limit,
                    )
                )
            except ValueError as exc:
                raise RouteGenerationError(
                    f"Invalid route geometry for route {index + 1}: {exc}"
                ) from exc

        coordinates = _collect_coordinates(prepared_routes)

        last_eta = plan.departure

        for prepared in prepared_routes:
            for checkpoint in prepared["checkpoints"]:
                if checkpoint["eta_utc"] > last_eta:
                    last_eta = checkpoint["eta_utc"]

        buffer_hours = float(
            getattr(settings, "PLAN_WEATHER_BUFFER_HOURS", 2.0)
        )

        if buffer_hours < 0:
            buffer_hours = 0.0

        end_time = max(
            plan.departure + timedelta(hours=48),
            last_eta + timedelta(hours=buffer_hours),
        )

        max_forecast_end = plan.departure + timedelta(days=16)

        if end_time > max_forecast_end:
            end_time = max_forecast_end

        if end_time <= plan.departure:
            end_time = plan.departure + timedelta(hours=1)

        weather_lookup = _fetch_weather_lookup(
            coordinates=coordinates,
            start_time=plan.departure,
            end_time=end_time,
            forecast_fn=forecast_fn,
        )

        heatmap_by_route_id: dict[str, list[dict]] = {}

        with transaction.atomic():
            route_dicts: list[dict] = []

            for prepared in prepared_routes:
                route_obj = RouteOption.objects.create(
                    plan=plan,
                    label=prepared["label"],
                    route_index=prepared["route_index"],
                    distance_miles=prepared["distance_miles"],
                    duration_seconds=prepared["duration_seconds"],
                    geometry=prepared["geometry"],
                )

                checkpoint_rows: list[dict] = []

                for checkpoint in prepared["checkpoints"]:
                    coordinate_data = weather_lookup.get(
                        _coord_key(checkpoint["lat"], checkpoint["lng"])
                    )

                    if coordinate_data:
                        weather = get_weather_at_time(
                            coordinate_data,
                            checkpoint["eta_utc"],
                        )
                    else:
                        weather = _default_weather()

                    risk = classify_checkpoint(
                        wind_mph=weather["wind_speed_mph"],
                        rain_in_hr=weather["rain_in_hr"],
                        snow_in_hr=weather["snow_in_hr"],
                        load_lb=plan.load_lb,
                    )

                    matched_time = weather.get("matched_time")

                    Checkpoint.objects.create(
                        route=route_obj,
                        mile_marker=float(checkpoint["mile"]),
                        lat=float(checkpoint["lat"]),
                        lng=float(checkpoint["lng"]),
                        eta_utc=checkpoint["eta_utc"],
                        wind_mph=float(weather["wind_speed_mph"]),
                        wind_gust_mph=weather.get("wind_gust_mph"),
                        rain_in_hr=float(weather["rain_in_hr"]),
                        snow_in_hr=float(weather["snow_in_hr"]),
                        temperature_f=weather.get("temperature_f"),
                        weather_code=weather.get("weather_code"),
                        wind_risk=_risk_string(risk["wind_risk"]),
                        rain_risk=_risk_string(risk["rain_risk"]),
                        snow_risk=_risk_string(risk["snow_risk"]),
                        overall_risk=_risk_string(risk["overall_risk"]),
                        load_override_applied=bool(
                            risk["load_override_applied"]
                        ),
                        raw_weather={
                            "matched_time": (
                                matched_time.isoformat()
                                if isinstance(matched_time, datetime)
                                else None
                            )
                        },
                    )

                    checkpoint_rows.append(
                        {
                            "mile": float(checkpoint["mile"]),
                            "overall_risk": _risk_string(
                                risk["overall_risk"]
                            ),
                        }
                    )

                metrics = aggregate_route_metrics(
                    checkpoints=checkpoint_rows,
                    distance_miles=prepared["distance_miles"],
                    duration_seconds=prepared["duration_seconds"],
                )

                route_obj.average_risk_score = float(
                    metrics["average_risk_score"]
                )
                route_obj.low_miles = float(metrics["low_miles"])
                route_obj.moderate_miles = float(metrics["moderate_miles"])
                route_obj.high_miles = float(metrics["high_miles"])
                route_obj.severe_miles = float(metrics["severe_miles"])
                route_obj.no_travel_miles = float(metrics["no_travel_miles"])
                route_obj.save(
                    update_fields=[
                        "average_risk_score",
                        "low_miles",
                        "moderate_miles",
                        "high_miles",
                        "severe_miles",
                        "no_travel_miles",
                    ]
                )

                heatmap_points = _build_heatmap_points(
                    heatmap_points=prepared["heatmap_points"],
                    weather_lookup=weather_lookup,
                    start_time=plan.departure,
                    load_lb=plan.load_lb,
                )

                heatmap_by_route_id[str(route_obj.id)] = heatmap_points

                route_dicts.append(
                    {
                        "id": str(route_obj.id),
                        "label": route_obj.label,
                        "has_no_travel": bool(metrics["has_no_travel"]),
                        "no_travel_miles": float(metrics["no_travel_miles"]),
                        "severe_miles": float(metrics["severe_miles"]),
                        "high_miles": float(metrics["high_miles"]),
                        "average_risk_score": float(
                            metrics["average_risk_score"]
                        ),
                        "duration_seconds": float(route_obj.duration_seconds),
                        "distance_miles": float(route_obj.distance_miles),
                    }
                )

            recommendation = recommend_routes(route_dicts)

            for ranked_route in recommendation["ranked_routes"]:
                RouteOption.objects.filter(pk=ranked_route["id"]).update(
                    is_recommended=bool(ranked_route.get("is_recommended")),
                    recommendation_reasons=(
                        ranked_route.get("recommendation_reasons") or []
                    ),
                )

            plan.status = TripPlan.STATUS_COMPLETED
            plan.error_message = ""
            plan.save(
                update_fields=["status", "error_message", "updated_at"]
            )

        plan.refresh_from_db()

        return build_plan_response(
            plan=plan,
            heatmap_by_route_id=heatmap_by_route_id,
        )

    except PlanServiceError as exc:
        _mark_plan_failed(plan, exc)
        raise

    except Exception as exc:
        _mark_plan_failed(plan, exc)
        raise PlanServiceError(str(exc)) from exc
