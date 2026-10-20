from __future__ import annotations

import hashlib
from collections.abc import Mapping
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests
from django.conf import settings
from django.core.cache import cache

DEFAULT_GEOCODING_BASE_URL = "https://geocoding-api.open-meteo.com"
USER_AGENT = "Dirmile/0.1 (+https://github.com/S-V-J/dirmile)"


class GeocodingError(Exception):
    """
    Base exception for geocoding failures.
    """


class GeocodingAPIError(GeocodingError):
    """
    Raised when the geocoding provider returns an HTTP or provider-level error.
    """

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _safe_float(value, default: float | None = None) -> float | None:
    """
    Convert a value to float safely.
    None, invalid strings, and NaN become the default value.
    """
    if value is None:
        return default

    try:
        result = float(value)
    except (TypeError, ValueError):
        return default

    # NaN check.
    if result != result:
        return default

    return result


def _safe_str(value, default: str = "") -> str:
    """
    Convert a value to a stripped string.
    None becomes the default.
    """
    if value is None:
        return default

    return str(value).strip()


def _clamp_count(value) -> int:
    """
    Clamp requested result count to a safe integer range.
    """
    if value is None:
        value = 5

    try:
        count = int(value)
    except (TypeError, ValueError):
        count = 5

    return max(1, min(count, 20))


def build_geocoding_url(
    query: str,
    count: int = 5,
    language: str = "en",
    base_url: str | None = None,
) -> str:
    """
    Build an Open-Meteo geocoding search URL.

    Args:
        query:
            Place name to search for.

        count:
            Maximum number of results to request.

        language:
            Language code for result names.

        base_url:
            Optional geocoding base URL.
            Defaults to settings.GEOCODING_BASE_URL.

    Returns:
        Full Open-Meteo geocoding URL string.
    """
    query = _safe_str(query)

    if not query:
        raise ValueError("Geocoding query cannot be empty.")

    count = _clamp_count(count)
    language = _safe_str(language, "en") or "en"

    base = (
        base_url
        or getattr(settings, "GEOCODING_BASE_URL", DEFAULT_GEOCODING_BASE_URL)
        or DEFAULT_GEOCODING_BASE_URL
    )

    base = str(base).strip()

    if not base:
        raise ValueError("Geocoding base URL cannot be empty.")

    if "://" not in base:
        base = f"https://{base}"

    parsed = urlsplit(base)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Geocoding base URL must use http or https.")

    if not parsed.netloc:
        raise ValueError("Geocoding base URL must include a host.")

    base_path = parsed.path.rstrip("/")
    path = f"{base_path}/v1/search"

    params = {
        "name": query,
        "count": str(count),
        "language": language,
        "format": "json",
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


def _cache_key(query: str, count: int, language: str, country_code: str) -> str:
    """
    Build a deterministic cache key for geocoding results.
    """
    raw = f"{query.lower()}|{count}|{language}|{country_code.upper()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"dirmile:geocode:{digest}"


def normalize_geocoding_response(
    payload,
    country_code: str = "",
) -> list[dict]:
    """
    Normalize an Open-Meteo geocoding response into Dirmile place dictionaries.

    Args:
        payload:
            Parsed JSON response from Open-Meteo geocoding API.

        country_code:
            Optional ISO 2-letter country code to filter results.
            For example, "US" or "CA".
            If provided, only results matching this country are returned.
            If no results match, an empty list is returned.

    Returns:
        [
            {
                "id": int | None,
                "name": str,
                "display_name": str,
                "latitude": float,
                "longitude": float,
                "timezone": str,
                "country_code": str,
                "country": str,
                "admin1": str,
                "admin2": str,
                "population": int | None,
                "elevation": float | None,
                "feature_code": str,
            },
            ...
        ]

    Raises:
        GeocodingError:
            When the payload is malformed.
    """
    if not isinstance(payload, Mapping):
        raise GeocodingError("Geocoding response must be a JSON object.")

    raw_results = payload.get("results")

    if raw_results is None:
        return []

    if not isinstance(raw_results, list):
        raise GeocodingError("Geocoding response 'results' must be a list.")

    country_filter = _safe_str(country_code).upper()

    normalized: list[dict] = []

    for item in raw_results:
        if not isinstance(item, Mapping):
            continue

        latitude = _safe_float(item.get("latitude"))
        longitude = _safe_float(item.get("longitude"))

        if latitude is None or longitude is None:
            continue

        item_country_code = _safe_str(item.get("country_code")).upper()

        if country_filter and item_country_code != country_filter:
            continue

        name = _safe_str(item.get("name"))
        admin1 = _safe_str(item.get("admin1"))
        admin2 = _safe_str(item.get("admin2"))
        country = _safe_str(item.get("country"))

        display_parts = [
            part
            for part in (name, admin1, admin2, country)
            if part
        ]
        display_name = ", ".join(display_parts) if display_parts else name

        population_raw = item.get("population")
        population = None
        if population_raw is not None:
            try:
                population = int(population_raw)
            except (TypeError, ValueError):
                population = None

        elevation = _safe_float(item.get("elevation"))

        feature_code = _safe_str(item.get("feature_code"))
        timezone = _safe_str(item.get("timezone"))

        id_raw = item.get("id")
        place_id = None
        if id_raw is not None:
            try:
                place_id = int(id_raw)
            except (TypeError, ValueError):
                place_id = None

        normalized.append(
            {
                "id": place_id,
                "name": name,
                "display_name": display_name,
                "latitude": latitude,
                "longitude": longitude,
                "timezone": timezone,
                "country_code": item_country_code,
                "country": country,
                "admin1": admin1,
                "admin2": admin2,
                "population": population,
                "elevation": elevation,
                "feature_code": feature_code,
            }
        )

    return normalized


def search_places(
    query: str,
    count: int = 5,
    language: str = "en",
    country_code: str = "",
    *,
    base_url: str | None = None,
    timeout: float | None = None,
    session=None,
    use_cache: bool = True,
) -> list[dict]:
    """
    Search for places using the Open-Meteo geocoding API.

    Args:
        query:
            Place name to search for.

        count:
            Maximum number of results.

        language:
            Language code for result names.

        country_code:
            Optional ISO 2-letter country code to filter results.

        base_url:
            Optional geocoding base URL.

        timeout:
            Optional request timeout in seconds.
            Defaults to settings.GEOCODING_TIMEOUT_SECONDS.

        session:
            Optional requests-like session object.
            Defaults to the global requests module.

        use_cache:
            Whether to use Django cache. Defaults to True.

    Returns:
        List of normalized place dictionaries.

    Raises:
        ValueError:
            For empty query or invalid base URL.

        GeocodingAPIError:
            When the geocoding API returns HTTP or provider-level errors.

        GeocodingError:
            For malformed responses or transport failures.
    """
    query = _safe_str(query)

    if not query:
        raise ValueError("Geocoding query cannot be empty.")

    count = _clamp_count(count)
    language = _safe_str(language, "en") or "en"
    country_code = _safe_str(country_code).upper()

    cache_ttl = getattr(settings, "GEOCODING_CACHE_TTL_SECONDS", 86400)
    cache_key = _cache_key(query, count, language, country_code)

    if use_cache and cache_ttl > 0:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    url = build_geocoding_url(
        query=query,
        count=count,
        language=language,
        base_url=base_url,
    )

    if timeout is None:
        timeout = getattr(settings, "GEOCODING_TIMEOUT_SECONDS", 10.0)

    timeout = max(1.0, _safe_float(timeout, 10.0) or 10.0)

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
        raise GeocodingError(f"Geocoding request failed: {exc}") from exc

    status_code = getattr(response, "status_code", None)

    if status_code is not None and status_code >= 400:
        body = str(getattr(response, "text", "") or "")[:200]
        raise GeocodingAPIError(
            f"Geocoding API HTTP {status_code}: {body}",
            status_code=status_code,
        )

    try:
        payload = response.json()
    except Exception as exc:
        raise GeocodingError("Geocoding API returned invalid JSON.") from exc

    results = normalize_geocoding_response(payload, country_code=country_code)

    if use_cache and cache_ttl > 0:
        cache.set(cache_key, results, timeout=cache_ttl)

    return results
