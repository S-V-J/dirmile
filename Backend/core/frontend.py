from __future__ import annotations

import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.views.decorators.http import require_GET

INDEX_NAME = "index.html"

# Paths that must never be swallowed by the SPA fallback.
RESERVED_PREFIXES = ("api/", "admin/", "static/", "media/")

# Ensure common frontend MIME types are available even on minimal systems.
mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("font/woff2", ".woff2")


def _dist_dir() -> Path | None:
    """
    Return the configured frontend build directory, if present.
    """
    dist = getattr(settings, "FRONTEND_DIST_DIR", None)
    if not dist:
        return None
    return Path(dist)


def _index_path() -> Path | None:
    """
    Return the frontend index.html path if the build exists.
    """
    dist = _dist_dir()
    if dist is None:
        return None

    index = dist / INDEX_NAME
    if index.is_file():
        return index

    return None


def _not_built_response() -> HttpResponse:
    """
    Friendly development response when frontend build is missing.
    """
    return HttpResponse(
        "Frontend build not found. Run `npm run build` inside Frontend/.",
        status=503,
        content_type="text/plain; charset=utf-8",
    )


def _safe_dist_path(relative_path: str) -> Path:
    """
    Resolve a requested frontend asset path safely inside FRONTEND_DIST_DIR.

    This prevents path traversal attacks such as:
        /../Backend/config/settings.py
        /..%2F..%2Fetc%2Fpasswd
    """
    dist = _dist_dir()
    if dist is None:
        raise Http404("Frontend build is not configured.")

    dist = dist.resolve()

    cleaned = (relative_path or "").replace("\\", "/")

    while cleaned.startswith("/"):
        cleaned = cleaned[1:]

    if not cleaned:
        raise Http404("Frontend asset path is required.")

    candidate = (dist / cleaned).resolve()

    try:
        candidate.relative_to(dist)
    except ValueError as exc:
        raise Http404("Invalid frontend asset path.") from exc

    if not candidate.is_file():
        raise Http404("Frontend asset not found.")

    return candidate


def _content_type(path: Path) -> str:
    """
    Return a suitable Content-Type for a frontend file.
    """
    guessed, _ = mimetypes.guess_type(str(path))
    suffix = path.suffix.lower()

    if not guessed:
        guessed = {
            ".webmanifest": "application/manifest+json",
            ".svg": "image/svg+xml",
            ".js": "text/javascript",
            ".mjs": "text/javascript",
            ".css": "text/css",
            ".html": "text/html",
            ".htm": "text/html",
            ".json": "application/json",
            ".map": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".ico": "image/x-icon",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".ttf": "font/ttf",
            ".otf": "font/otf",
        }.get(suffix, "application/octet-stream")

    if guessed.startswith(
        (
            "text/",
            "application/json",
            "application/manifest+json",
            "image/svg+xml",
        )
    ):
        return f"{guessed}; charset=utf-8"

    return guessed


def _cache_control(relative_path: str) -> str:
    """
    Return cache headers suitable for frontend assets.

    Hashed Vite assets can be cached immutably.
    Service worker, manifest, index.html, and offline.html should not be cached
    aggressively because they control app updates.
    """
    normalized = (relative_path or "").replace("\\", "/").lstrip("/")
    name = Path(normalized).name

    if normalized.startswith("assets/"):
        return "public, max-age=31536000, immutable"

    if name.startswith("workbox-"):
        return "public, max-age=31536000, immutable"

    if name in {
        "sw.js",
        "sw.js.map",
        "manifest.webmanifest",
        "index.html",
        "offline.html",
        "favicon.svg",
        "favicon.ico",
    }:
        return "no-cache, no-store, must-revalidate"

    if normalized.startswith("icons/"):
        return "public, max-age=86400"

    return "no-cache, no-store, must-revalidate"


def _serve_file(path: Path, relative_path: str) -> FileResponse:
    """
    Serve a file from the frontend build directory.

    IMPORTANT:
    Django's FileResponse requires a *file-like object*, not a filesystem path.
    Passing a Path raises:
        TypeError: 'PosixPath' object is not iterable
    because StreamingHttpResponse tries to iterate it as streaming_content.

    Django closes the opened handle automatically when the response finishes
    streaming, so this file must NOT be wrapped in a `with` block.
    """
    handle = path.open("rb")

    try:
        response = FileResponse(
            handle,
            content_type=_content_type(path),
            filename=path.name,
        )
    except Exception:
        # Only reachable if construction itself fails; Django would have owned
        # the handle otherwise.
        handle.close()
        raise

    cache_control = _cache_control(relative_path)
    response["Cache-Control"] = cache_control

    if cache_control.startswith("no-cache"):
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"

    return response


@require_GET
def frontend_index(request):
    """
    Serve Frontend/dist/index.html for the root URL.
    """
    index = _index_path()
    if index is None:
        return _not_built_response()

    return _serve_file(index, INDEX_NAME)


@require_GET
def frontend_static(request, path: str):
    """
    Serve a concrete file from Frontend/dist.

    Examples:
        /assets/index-abc123.js
        /icons/icon-192.png
        /sw.js
        /manifest.webmanifest
        /offline.html
    """
    file_path = _safe_dist_path(path)
    return _serve_file(file_path, path)


@require_GET
def frontend_spa(request, route: str = ""):
    """
    SPA fallback.

    For extensionless routes such as:
        /app
        /settings
        /account
        /about
        /login
        /register

    Return index.html so React Router can handle the route.

    Reserved backend prefixes are rejected with 404 instead of HTML so that a
    mistyped API URL never masquerades as a successful page load.
    """
    normalized = (route or "").lstrip("/")

    if normalized.startswith(RESERVED_PREFIXES):
        raise Http404("Not found.")

    index = _index_path()
    if index is None:
        return _not_built_response()

    return _serve_file(index, INDEX_NAME)
