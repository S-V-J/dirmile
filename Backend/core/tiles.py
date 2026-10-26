"""
Same-origin OSM tile proxy.

Why: browsers fetching tile.openstreetmap.org cross-origin are subject to
edge policies (referer / Sec-Fetch / TLS fingerprint / decommissioned a.b.c
subdomains) that a server-side fetch is not. Proxying makes tiles same-origin,
lets the service worker cache them normally, and lets us present one honest
User-Agent per OSM's tile usage policy instead of one per visitor.

Bounds-checked so this can never be used as an open crawler.
"""
from __future__ import annotations

import re

import requests
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.views.decorators.http import require_safe

UPSTREAM = "https://tile.openstreetmap.org"
MAX_ZOOM = 19
TIMEOUT_SECONDS = 10
USER_AGENT = "Dirmile/0.1 (weather-aware truck routing; tile proxy)"
_TILE_RE = re.compile(r"^(?:png|jpe?g)$", re.IGNORECASE)


def _blank_tile() -> HttpResponse:
    """
    Empty tile (upstream hiccup / non-image). Must never be cached: a
    transient 502 upstream would otherwise punch a hole in the map for the
    full max-age window. Successful tiles get their own long-lived header.
    """
    response = HttpResponse(status=204)
    response["Cache-Control"] = "no-store"
    return response


@require_safe
def tile_proxy(request, z: int, x: int, y: int, ext: str):
    if not _TILE_RE.match(ext or ""):
        return HttpResponseBadRequest("Unsupported tile extension.")
    if z < 0 or z > MAX_ZOOM:
        return HttpResponseBadRequest("Zoom out of range.")
    limit = 2 ** z
    if x < 0 or y < 0 or x >= limit or y >= limit:
        return HttpResponseNotFound("Tile out of range.")

    url = f"{UPSTREAM}/{z}/{x}/{y}.{ext.lower()}"
    try:
        upstream = requests.get(
            url,
            timeout=TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.8"},
        )
    except requests.RequestException:
        # Never leak the upstream failure as a 500 storm; serve a blank 204 so
        # Leaflet simply shows no tile there.
        return _blank_tile()

    if upstream.status_code != 200:
        return _blank_tile()

    content_type = upstream.headers.get("Content-Type", "image/png")
    if not content_type.startswith("image/"):
        return _blank_tile()

    response = HttpResponse(upstream.content, content_type=content_type)
    response["Cache-Control"] = "public, max-age=604800, immutable"
    return response
