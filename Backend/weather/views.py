from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from weather.geocoding import GeocodingAPIError, GeocodingError, search_places

MIN_QUERY_LENGTH = 2
DEFAULT_COUNT = 5
MAX_COUNT = 10

# Slim projection sent to the browser — enough for the dropdown label and
# a deterministic re-geocode on submit. Internal fields (elevation,
# feature_code, population) stay server-side.
PLACE_FIELDS = (
    "id",
    "name",
    "display_name",
    "latitude",
    "longitude",
    "country_code",
    "country",
    "admin1",
    "admin2",
    "timezone",
)


def _is_authenticated(request) -> bool:
    """
    Same explicit-auth check as plans/api.py.
    """
    user = getattr(request, "user", None)
    if user is None:
        return False
    return bool(
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", True)
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def places_search(request):
    """
    GET /api/places/?q=<query>&count=<1-10>&country=<ISO2>

    Autocomplete backing the Origin/Destination inputs.
    Explicit 401 for anonymous callers (mirrors plans/api.py so DRF's
    permission path can never emit a 403 here). Results are cached
    upstream by weather.geocoding (GEOCODING_CACHE_TTL_SECONDS = 24h),
    so debounced typing is cheap on repeat queries.
    """
    if not _is_authenticated(request):
        return Response(
            {"detail": "Authentication credentials were not provided."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    query = str(request.query_params.get("q", "")).strip()
    if len(query) < MIN_QUERY_LENGTH:
        return Response(
            {"detail": f"Query must be at least {MIN_QUERY_LENGTH} characters."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        count = int(request.query_params.get("count", DEFAULT_COUNT))
    except (TypeError, ValueError):
        count = DEFAULT_COUNT
    count = max(1, min(count, MAX_COUNT))

    country = str(request.query_params.get("country", "")).strip().upper()
    if len(country) != 2:
        country = ""

    try:
        results = search_places(query, count=count, country_code=country)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except (GeocodingAPIError, GeocodingError) as exc:
        return Response(
            {"detail": f"Place search failed: {exc}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    places = [
        {key: item.get(key) for key in PLACE_FIELDS}
        for item in results
        if isinstance(item, dict)
    ]
    return Response(places)
