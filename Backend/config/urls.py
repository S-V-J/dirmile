from django.contrib import admin
from django.urls import include, path, re_path

from core.frontend import (
    frontend_index,
    frontend_spa,
    frontend_static,
)
from core.views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health-check"),
    path("api/", include("accounts.urls")),
    path("api/", include("plans.urls")),
]

# ------------------------------------------------------------------
# Frontend serving.
#
# These patterns must stay after /admin/ and /api/ patterns.
#
# The (?!api/|admin/|static/|media/) negative lookahead guarantees that
# backend namespaces are never captured by the SPA fallback, so a mistyped
# API URL returns a real 404 instead of index.html with status 200.
#
# Order:
#   1. root URL serves index.html
#   2. paths containing a dot are treated as static frontend assets
#   3. all other paths fall back to index.html for React Router SPA routes
# ------------------------------------------------------------------
urlpatterns += [
    path("", frontend_index, name="frontend-index"),
    re_path(
        r"^(?!api/|admin/|static/|media/)(?P<path>.*\..*)$",
        frontend_static,
        name="frontend-static",
    ),
    re_path(
        r"^(?!api/|admin/|static/|media/)(?P<route>.*)$",
        frontend_spa,
        name="frontend-spa",
    ),
]
