from django.contrib import admin
from django.urls import include, path, re_path

from core.views import health_check
from core.frontend import serve_dist_file, serve_sw, spa_index

urlpatterns = [
    # ── API routes (must come before SPA fallback) ───────────────────
    path("api/health/", health_check, name="health-check"),
    path("api/", include("accounts.urls")),
    path("api/", include("plans.urls")),
    path("api/", include("weather.urls")),

    # ── Django admin ─────────────────────────────────────────────────
    path("admin/", admin.site.urls),

    # ── Service worker (no-cache: browser checks every load) ─────────
    path("sw.js", serve_sw, name="service-worker"),
    re_path(
        r"^sw\.js\.map$",
        serve_dist_file,
        {"file_path": "sw.js.map"},
        name="service-worker-map",
    ),

    # ── Frontend hashed assets (immutable cache) ─────────────────────
    re_path(
        r"^(?P<file_path>assets/.+)$",
        serve_dist_file,
        name="frontend-assets",
    ),
    re_path(
        r"^(?P<file_path>workbox-[^/]+(?:\.map)?)$",
        serve_dist_file,
        name="frontend-workbox",
    ),

    # ── PWA icons ────────────────────────────────────────────────────
    re_path(
        r"^(?P<file_path>icons/.+)$",
        serve_dist_file,
        name="frontend-icons",
    ),

    # ── Other frontend root files ────────────────────────────────────
    re_path(
        r"^(?P<file_path>manifest\.webmanifest)$",
        serve_dist_file,
        name="frontend-manifest",
    ),
    re_path(
        r"^(?P<file_path>offline\.html)$",
        serve_dist_file,
        name="frontend-offline",
    ),
    re_path(
        r"^(?P<file_path>favicon\.\w+)$",
        serve_dist_file,
        name="frontend-favicon",
    ),
    re_path(
        r"^(?P<file_path>robots\.txt)$",
        serve_dist_file,
        name="frontend-robots",
    ),

    # ── SPA fallback (MUST be the last pattern) ──────────────────────
    # Matches any GET that is not /api/, /admin/, /static/,
    # or one of the explicit frontend file patterns above.
    # React Router then handles /login, /register, /app, /settings, etc.
    re_path(
        r"^(?!api/|admin/|static/|sw\.js|assets/|workbox-|icons/|manifest\.|offline\.|favicon|robots)",
        spa_index,
        name="spa-index",
    ),
]
