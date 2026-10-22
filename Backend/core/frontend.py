"""
Views for serving the built React SPA from Frontend/dist/.

Dirmile uses a single Django process to serve:
  - /api/*          -> Django REST Framework endpoints
  - /admin/*        -> Django admin
  - /static/*       -> Django's own static files (via WhiteNoise)
  - /sw.js          -> Service worker (no-cache, forces browser update)
  - /assets/*       -> Hashed JS/CSS bundles (immutable cache)
  - /icons/*        -> PWA icons (short cache)
  - /*              -> index.html (SPA fallback for React Router)

Cache policy (must stay in sync with Backend/core/test_frontend.py):
  assets/*, workbox-*            -> public, max-age=31536000, immutable
                                    (filename carries the content hash)
  *.png/.jpg/.svg/.ico/.woff2...  -> public, max-age=86400
                                    (NOT hashed, so they must expire)
  manifest, offline.html, *.map   -> no-cache
  sw.js                           -> no-cache, no-store, must-revalidate
  index.html                      -> no-cache, no-store, must-revalidate

The dirmile CLI rebuilds the frontend and restarts Django. Because sw.js is
served no-cache and the worker uses skipWaiting + clientsClaim + autoUpdate,
browsers pick up every new build with no manual action.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import unquote

from django.conf import settings
from django.http import Http404, HttpResponse

IMMUTABLE_MAX_AGE = 31536000  # 1 year - content-hashed bundles
STATIC_ASSET_MAX_AGE = 86400  # 1 day - un-hashed images/fonts/icons

_IMMUTABLE_PREFIXES = ("assets/", "workbox-")
_STATIC_ASSET_SUFFIXES = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif",
    ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".otf",
)
_NO_CACHE = "no-cache, no-store, must-revalidate"

_SPECIAL_CONTENT_TYPES = {
    ".webmanifest": "application/manifest+json",
    ".mjs": "application/javascript",
    ".map": "application/json",
}


def _dist_root() -> Path:
    """Absolute path to Frontend/dist/. Raises Http404 if unusable."""
    dist = getattr(settings, "FRONTEND_DIST_DIR", None)
    if not dist:
        raise Http404("FRONTEND_DIST_DIR is not configured.")
    dist = Path(dist)
    if not dist.is_dir():
        raise Http404(
            "Frontend build directory not found. "
            "Run: dirmile start (or: cd Frontend && npm run build)"
        )
    return dist


def _safe_resolve(dist: Path, rel_path: str) -> Path:
    """Resolve rel_path inside dist/ and verify it is a real file."""
    rel_path = unquote(rel_path).lstrip("/")
    if not rel_path or "\x00" in rel_path:
        raise Http404("Empty path.")
    target = (dist / rel_path).resolve()
    try:
        target.relative_to(dist.resolve())
    except ValueError:
        raise Http404("Path escapes frontend build directory.")
    if not target.is_file():
        raise Http404(f"File not found: {rel_path}")
    return target


def _safe_dist_path(rel_path: str) -> Path:
    """Public helper: resolve against the configured dist dir (Http404 on escape)."""
    return _safe_resolve(_dist_root(), rel_path)


def _guess_content_type(path: Path) -> str:
    ct, _ = mimetypes.guess_type(str(path))
    if ct is None:
        ct = _SPECIAL_CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return ct


def _cache_control_for(rel_path: str) -> str:
    lower = unquote(rel_path).lstrip("/").lower()
    if lower.startswith(_IMMUTABLE_PREFIXES):
        return f"public, max-age={IMMUTABLE_MAX_AGE}, immutable"
    if lower.endswith(_STATIC_ASSET_SUFFIXES):
        return f"public, max-age={STATIC_ASSET_MAX_AGE}"
    return "no-cache"


def _looks_like_file(path: str) -> bool:
    """True when the last path segment has an extension. Such paths must
    never be answered with index.html, or a broken bundle URL becomes a
    confusing 'Unexpected token <' error in the browser."""
    cleaned = unquote(path).rstrip("/")
    if not cleaned:
        return False
    return "." in cleaned.rsplit("/", 1)[-1]


# ── SPA fallback ─────────────────────────────────────────────────────

def spa_index(request, **kwargs):
    """Serve dist/index.html for every non-API, non-asset route so React
    Router can handle /login, /register, /app, /settings, etc."""
    rel = request.path_info.lstrip("/")
    if _looks_like_file(rel):
        raise Http404("Not found.")

    try:
        index = _safe_dist_path("index.html")
    except Http404 as exc:
        return HttpResponse(
            "<!DOCTYPE html><html><head><title>Dirmile</title></head>"
            "<body style='font-family:sans-serif;padding:2rem'>"
            "<h1>Dirmile</h1>"
            f"<p>{exc}</p>"
            "<p>Run <code>dirmile start</code> to build and launch.</p>"
            "</body></html>",
            status=503,
            content_type="text/html; charset=utf-8",
        )

    response = HttpResponse(index.read_bytes(), content_type="text/html; charset=utf-8")
    response["Cache-Control"] = _NO_CACHE
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


# ── Service worker ───────────────────────────────────────────────────

def serve_sw(request, **kwargs):
    """sw.js is always revalidated, so a new build activates immediately."""
    sw = _safe_dist_path("sw.js")
    response = HttpResponse(sw.read_bytes(), content_type="application/javascript; charset=utf-8")
    response["Cache-Control"] = _NO_CACHE
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    response["Service-Worker-Allowed"] = "/"
    return response


# ── Generic dist file server ─────────────────────────────────────────

def serve_dist_file(request, file_path: str = "", **kwargs):
    """Serve any file from Frontend/dist/ by relative path, applying the
    cache policy in _cache_control_for()."""
    fp = _safe_dist_path(file_path)
    response = HttpResponse(fp.read_bytes(), content_type=_guess_content_type(fp))
    response["Cache-Control"] = _cache_control_for(file_path)
    return response
