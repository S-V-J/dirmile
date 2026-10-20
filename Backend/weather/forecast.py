from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests
from django.conf import settings
from django.core.cache import cache

DEFAULT_WEATHER_BASE_URL = "https://api.open-meteo.com"
USER_AGENT = "Dirmile/0.1 (+https://github.com/S-V-J/dirmile)"
CM_PER_INCH = 2.54

HOURLY_VARIABLES = [
    "wind_speed_10m",
    "wind_gusts_10m",
    "rain",
    "snowfall",
    "temperature_2m",
    "weather_code",
]


class WeatherError(Exception):
    """
    Base exception for weather forecast failures.
    """


class WeatherAPIError(WeatherError):
    """
    Raised when the weather API returns an HTTP or provider-level error.
    """

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _safe_float(value, default: float | None = None) -> float | None:
    """
    Convert a value to float safely.
    None, invalid strings, NaN, and infinity become the default value.
    """
    if value is None:
        return default

    try:
        result = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(result):
        return default

    return result


def _clamp_batch_size(value) -> int:
    """
    Clamp requested batch size to a safe integer range.
    """
    if value is None:
        value = 1000

    try:
        count = int(value)
    except (TypeError, ValueError):
        count = 1000

    return max(1, min(count, 1000))


def _format_datetime_iso(dt: datetime) -> str:
    """
    Format a datetime as ISO 8601 string for Open-Meteo API.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M")


def _validate_coordinate(lat, lng, label: str) -> tuple[float, float]:
    """
    Validate a single coordinate pair.
    """
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} coordinates must be numeric.") from exc

    if not math.isfinite(lat_f) or not math.isfinite(lng_f):
        raise ValueError(f"{label} coordinates must be finite numbers.")

    if lat_f < -90.0 or lat_f > 90.0:
        raise ValueError(f"{label} latitude must be between -90 and 90.")

    if lng_f < -180.0 or lng_f > 180.0:
        raise ValueError(f"{label} longitude must be between -180 and 180.")

    return lat_f, lng_f


def build_forecast_url(
    coordinates: Sequence[tuple[float, float]],
    start_time: datetime,
    end_time: datetime,
    base_url: str | None = None,
) -> str:
    """
    Build an Open-Meteo forecast API URL for one or more coordinates.

    Args:
        coordinates:
            List of (latitude, longitude) tuples.
            Open-Meteo supports up to 1000 locations in one request.

        start_time:
            Forecast start datetime (timezone-aware or naive).

        end_time:
            Forecast end datetime (timezone-aware or naive).

        base_url:
            Optional weather API base URL.
            Defaults to settings.WEATHER_BASE_URL.

    Returns:
        Full Open-Meteo forecast URL string.

    Raises:
        ValueError:
            For invalid coordinates, empty list, or invalid time range.
    """
    if not coordinates:
        raise ValueError("At least one coordinate is required.")

    if len(coordinates) > 1000:
        raise ValueError(
            "Open-Meteo supports a maximum of 1000 coordinates per request."
        )

    lat_list = []
    lng_list = []

    for index, coord in enumerate(coordinates):
        if isinstance(coord, Mapping):
            lat_raw = coord.get("lat", coord.get("latitude"))
            lng_raw = coord.get("lng", coord.get("lon", coord.get("longitude")))
        elif isinstance(coord, Sequence) and not isinstance(coord, (str, bytes)):
            if len(coord) != 2:
                raise ValueError(
                    f"Coordinate at index {index} must contain exactly two values: (lat, lng)."
                )
            lat_raw, lng_raw = coord
        else:
            raise ValueError(
                f"Coordinate at index {index} must be a (lat, lng) pair or mapping."
            )

        lat_f, lng_f = _validate_coordinate(
            lat_raw, lng_raw, f"Coordinate at index {index}"
        )
        lat_list.append(format(lat_f, ".6f"))
        lng_list.append(format(lng_f, ".6f"))

    if start_time >= end_time:
        raise ValueError("start_time must be before end_time.")

    base = (
        base_url
        or getattr(settings, "WEATHER_BASE_URL", DEFAULT_WEATHER_BASE_URL)
        or DEFAULT_WEATHER_BASE_URL
    )

    base = str(base).strip()

    if not base:
        raise ValueError("Weather base URL cannot be empty.")

    if "://" not in base:
        base = f"https://{base}"

    parsed = urlsplit(base)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Weather base URL must use http or https.")

    if not parsed.netloc:
        raise ValueError("Weather base URL must include a host.")

    base_path = parsed.path.rstrip("/")
    path = f"{base_path}/v1/forecast"

    params = {
        "latitude": ",".join(lat_list),
        "longitude": ",".join(lng_list),
        "hourly": ",".join(HOURLY_VARIABLES),
        "start_time": _format_datetime_iso(start_time),
        "end_time": _format_datetime_iso(end_time),
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "temperature_unit": "fahrenheit",
        "timezone": "UTC",
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


def _cache_key(
    coordinates: Sequence[tuple[float, float]],
    start_time: datetime,
    end_time: datetime,
) -> str:
    """
    Build a deterministic cache key for weather results.
    """
    coord_str = "|".join(
        f"{float(lat):.6f},{float(lng):.6f}" for lat, lng in coordinates
    )
    raw = (
        f"{coord_str}|"
        f"{start_time.isoformat()}|"
        f"{end_time.isoformat()}"
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"dirmile:weather:{digest}"


def _parse_hourly_array(data: list | None, length: int) -> list[float | None]:
    """
    Parse an hourly array from Open-Meteo response.
    Returns a list of the same length with float values or None.
    """
    if data is None:
        return [None] * length

    result: list[float | None] = []

    for index in range(length):
        if index < len(data):
            result.append(_safe_float(data[index]))
        else:
            result.append(None)

    return result


def _parse_timestamps(timestamps: list | None) -> list[datetime | None]:
    """
    Parse ISO timestamp strings from Open-Meteo response.
    """
    if timestamps is None:
        return []

    result: list[datetime | None] = []

    for ts in timestamps:
        if ts is None:
            result.append(None)
            continue

        try:
            dt = datetime.fromisoformat(str(ts))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            result.append(dt)
        except (ValueError, TypeError):
            result.append(None)

    return result


def normalize_forecast_response(
    payload,
    expected_count: int,
) -> list[dict]:
    """
    Normalize an Open-Meteo forecast response into per-coordinate hourly data.

    Args:
        payload:
            Parsed JSON response from Open-Meteo forecast API.
            Can be a single object or a list of objects (batch response).

        expected_count:
            Number of coordinates that were requested.

    Returns:
        List of dictionaries, one per coordinate:
        [
            {
                "latitude": float,
                "longitude": float,
                "hourly": {
                    "time": [datetime, ...],
                    "wind_speed_mph": [float, ...],
                    "wind_gust_mph": [float, ...],
                    "rain_in_hr": [float, ...],
                    "snow_in_hr": [float, ...],
                    "temperature_f": [float, ...],
                    "weather_code": [int, ...],
                },
            },
            ...
        ]

    Raises:
        WeatherError:
            When the payload is malformed.
    """
    if not isinstance(payload, (dict, list)):
        raise WeatherError("Weather response must be a JSON object or list.")

    # Open-Meteo batch response returns a list of objects.
    # Single-coordinate response returns a single object.
    if isinstance(payload, dict):
        items = [payload]
    else:
        items = payload

    if len(items) != expected_count:
        raise WeatherError(
            f"Weather response count mismatch: expected {expected_count}, "
            f"got {len(items)}."
        )

    normalized: list[dict] = []

    for item in items:
        if not isinstance(item, Mapping):
            raise WeatherError("Each weather response item must be a JSON object.")

        latitude = _safe_float(item.get("latitude"))
        longitude = _safe_float(item.get("longitude"))

        hourly_raw = item.get("hourly")

        if not isinstance(hourly_raw, Mapping):
            raise WeatherError("Weather response is missing 'hourly' data.")

        timestamps = _parse_timestamps(hourly_raw.get("time"))
        num_hours = len(timestamps)

        wind_speed = _parse_hourly_array(
            hourly_raw.get("wind_speed_10m"), num_hours
        )
        wind_gust = _parse_hourly_array(
            hourly_raw.get("wind_gusts_10m"), num_hours
        )
        rain = _parse_hourly_array(
            hourly_raw.get("rain"), num_hours
        )
        snowfall_cm = _parse_hourly_array(
            hourly_raw.get("snowfall"), num_hours
        )
        temperature = _parse_hourly_array(
            hourly_raw.get("temperature_2m"), num_hours
        )
        weather_code_raw = _parse_hourly_array(
            hourly_raw.get("weather_code"), num_hours
        )

        # Convert snowfall from centimeters to inches.
        snow_inches: list[float | None] = []
        for value in snowfall_cm:
            if value is None:
                snow_inches.append(None)
            else:
                snow_inches.append(round(value / CM_PER_INCH, 6))

        # Convert weather_code to integers.
        weather_codes: list[int | None] = []
        for value in weather_code_raw:
            if value is None:
                weather_codes.append(None)
            else:
                weather_codes.append(int(value))

        normalized.append(
            {
                "latitude": latitude,
                "longitude": longitude,
                "hourly": {
                    "time": timestamps,
                    "wind_speed_mph": wind_speed,
                    "wind_gust_mph": wind_gust,
                    "rain_in_hr": rain,
                    "snow_in_hr": snow_inches,
                    "temperature_f": temperature,
                    "weather_code": weather_codes,
                },
            }
        )

    return normalized


def get_weather_at_time(
    coordinate_data: dict,
    target_time: datetime,
) -> dict:
    """
    Extract interpolated weather values for a specific target time
    from a normalized coordinate forecast.

    Args:
        coordinate_data:
            One item from normalize_forecast_response output.

        target_time:
            The datetime at which to sample weather.

    Returns:
        {
            "wind_speed_mph": float,
            "wind_gust_mph": float | None,
            "rain_in_hr": float,
            "snow_in_hr": float,
            "temperature_f": float | None,
            "weather_code": int | None,
            "matched_time": datetime | None,
        }

    Values default to 0.0 or None when data is unavailable.
    Linear interpolation is used between hourly values.
    """
    hourly = coordinate_data.get("hourly", {})
    times = hourly.get("time", [])
    wind_speeds = hourly.get("wind_speed_mph", [])
    wind_gusts = hourly.get("wind_gust_mph", [])
    rains = hourly.get("rain_in_hr", [])
    snows = hourly.get("snow_in_hr", [])
    temps = hourly.get("temperature_f", [])
    codes = hourly.get("weather_code", [])

    if not times or target_time is None:
        return {
            "wind_speed_mph": 0.0,
            "wind_gust_mph": None,
            "rain_in_hr": 0.0,
            "snow_in_hr": 0.0,
            "temperature_f": None,
            "weather_code": None,
            "matched_time": None,
        }

    # Ensure target_time is timezone-aware UTC.
    if target_time.tzinfo is None:
        target_time = target_time.replace(tzinfo=timezone.utc)
    else:
        target_time = target_time.astimezone(timezone.utc)

    # Find the bracketing hours.
    lower_index = None
    upper_index = None

    for index, ts in enumerate(times):
        if ts is None:
            continue
        if ts <= target_time:
            lower_index = index
        if ts >= target_time and upper_index is None:
            upper_index = index

    # If target is before all data, use first available.
    if lower_index is None and upper_index is not None:
        lower_index = upper_index

    # If target is after all data, use last available.
    if upper_index is None and lower_index is not None:
        upper_index = lower_index

    if lower_index is None:
        return {
            "wind_speed_mph": 0.0,
            "wind_gust_mph": None,
            "rain_in_hr": 0.0,
            "snow_in_hr": 0.0,
            "temperature_f": None,
            "weather_code": None,
            "matched_time": None,
        }

    def _interpolate(values: list, idx_lo: int, idx_hi: int | None, t: datetime) -> float | None:
        """
        Linearly interpolate a value between two hourly indices.
        """
        if idx_hi is None or idx_hi == idx_lo:
            val = values[idx_lo] if idx_lo < len(values) else None
            return _safe_float(val, 0.0)

        val_lo = _safe_float(values[idx_lo] if idx_lo < len(values) else None)
        val_hi = _safe_float(values[idx_hi] if idx_hi < len(values) else None)

        if val_lo is None or val_hi is None:
            return val_lo if val_lo is not None else (val_hi or 0.0)

        t_lo = times[idx_lo]
        t_hi = times[idx_hi]

        if t_lo is None or t_hi is None:
            return val_lo

        total_seconds = (t_hi - t_lo).total_seconds()
        if total_seconds <= 0:
            return val_lo

        elapsed = (t - t_lo).total_seconds()
        fraction = max(0.0, min(1.0, elapsed / total_seconds))

        return val_lo + (val_hi - val_lo) * fraction

    matched_time = times[lower_index]

    wind_speed = _interpolate(wind_speeds, lower_index, upper_index, target_time) or 0.0
    rain = _interpolate(rains, lower_index, upper_index, target_time) or 0.0
    snow = _interpolate(snows, lower_index, upper_index, target_time) or 0.0

    wind_gust = _interpolate(wind_gusts, lower_index, upper_index, target_time)
    temperature = _interpolate(temps, lower_index, upper_index, target_time)

    # Weather code is not interpolated; use the lower index value.
    weather_code = None
    if lower_index < len(codes) and codes[lower_index] is not None:
        weather_code = int(codes[lower_index])

    return {
        "wind_speed_mph": round(wind_speed, 1),
        "wind_gust_mph": round(wind_gust, 1) if wind_gust is not None else None,
        "rain_in_hr": round(rain, 4),
        "snow_in_hr": round(snow, 4),
        "temperature_f": round(temperature, 1) if temperature is not None else None,
        "weather_code": weather_code,
        "matched_time": matched_time,
    }


def fetch_forecast(
    coordinates: Sequence[tuple[float, float]],
    start_time: datetime,
    end_time: datetime,
    *,
    base_url: str | None = None,
    timeout: float | None = None,
    session=None,
    use_cache: bool = True,
) -> list[dict]:
    """
    Fetch hourly weather forecast for one or more coordinates.

    Args:
        coordinates:
            List of (latitude, longitude) tuples.
            Maximum 1000 per request.

        start_time:
            Forecast start datetime.

        end_time:
            Forecast end datetime.

        base_url:
            Optional weather API base URL.

        timeout:
            Optional request timeout in seconds.
            Defaults to settings.WEATHER_TIMEOUT_SECONDS.

        session:
            Optional requests-like session object.
            Defaults to the global requests module.

        use_cache:
            Whether to use Django cache. Defaults to True.

    Returns:
        List of normalized coordinate forecast dictionaries.

    Raises:
        ValueError:
            For invalid coordinates or invalid time range.

        WeatherAPIError:
            When the weather API returns HTTP or provider-level errors.

        WeatherError:
            For malformed responses or transport failures.
    """
    if not coordinates:
        raise ValueError("At least one coordinate is required.")

    url = build_forecast_url(
        coordinates=coordinates,
        start_time=start_time,
        end_time=end_time,
        base_url=base_url,
    )

    cache_ttl = getattr(settings, "WEATHER_CACHE_TTL_SECONDS", 900)
    ck = _cache_key(
        [(float(lat), float(lng)) for lat, lng in coordinates],
        start_time,
        end_time,
    )

    if use_cache and cache_ttl > 0:
        cached = cache.get(ck)
        if cached is not None:
            return cached

    if timeout is None:
        timeout = getattr(settings, "WEATHER_TIMEOUT_SECONDS", 15.0)

    timeout = max(1.0, _safe_float(timeout, 15.0) or 15.0)

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
        raise WeatherError(f"Weather request failed: {exc}") from exc

    status_code = getattr(response, "status_code", None)

    if status_code is not None and status_code >= 400:
        body = str(getattr(response, "text", "") or "")[:200]
        raise WeatherAPIError(
            f"Weather API HTTP {status_code}: {body}",
            status_code=status_code,
        )

    try:
        payload = response.json()
    except Exception as exc:
        raise WeatherError("Weather API returned invalid JSON.") from exc

    results = normalize_forecast_response(payload, expected_count=len(coordinates))

    if use_cache and cache_ttl > 0:
        cache.set(ck, results, timeout=cache_ttl)

    return results
