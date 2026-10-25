from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

# Load environment variables from:
# 1. /home/ML/dirmile/.env
# 2. /home/ML/dirmile/Backend/.env, if someone creates one later
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = env_bool("DEBUG", True)

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-change-this-only-for-local-development"
    else:
        raise RuntimeError("SECRET_KEY must be set when DEBUG=False.")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")

# Trust X-Forwarded-Proto header from Cloudflare Tunnel
# This makes request.is_secure() return True when CF sends https
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if DEBUG and "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("testserver")

# CSRF settings.
# For Cloudflare Tunnel or custom domains, add them to CSRF_TRUSTED_ORIGINS in .env.
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

# CORS settings.
# Local dynamic ports are allowed by regex.
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https?://(localhost|127\.0\.0\.1)(:\d+)$",
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "corsheaders",
    # Dirmile apps
    "accounts",
    "core",
    "plans",
    "routing",
    "weather",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Custom user model must be set before first migration.
AUTH_USER_MODEL = "accounts.User"

# Use only Dirmile's authentication backend.
AUTHENTICATION_BACKENDS = [
    "accounts.backends.DirmileAuthBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ── Static files ─────────────────────────────────────────────────────
# Django's own static files (admin CSS/JS) are served by WhiteNoise
# from STATIC_ROOT after collectstatic.
#
# The React frontend build (Frontend/dist/) is served DIRECTLY by
# core.frontend views at /assets/, /sw.js, /icons/, etc.
# It is NOT included in STATICFILES_DIRS to avoid duplication.

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = []  # Django's own extra static dirs only (currently none)

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

if DEBUG:
    WHITENOISE_AUTOREFRESH = True

# Prevent WhiteNoise warning during development/tests.
STATIC_ROOT.mkdir(parents=True, exist_ok=True)

# Path to the built React SPA. Served by core.frontend views.
FRONTEND_DIST_DIR = PROJECT_ROOT / "Frontend" / "dist"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.DirmileSessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

if DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"].append(
        "rest_framework.renderers.BrowsableAPIRenderer"
    )

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "dirmile-cache",
    }
}

# Django 6.1 mailer configuration.
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# External routing API settings.
ROUTING_BASE_URL = os.getenv("ROUTING_BASE_URL", "https://router.project-osrm.org")
ROUTING_TIMEOUT_SECONDS = float(os.getenv("ROUTING_TIMEOUT_SECONDS", "10"))
ROUTING_MAX_ALTERNATIVES = int(os.getenv("ROUTING_MAX_ALTERNATIVES", "3"))
ROUTING_CACHE_TTL_SECONDS = int(os.getenv("ROUTING_CACHE_TTL_SECONDS", "900"))

# ── External weather API settings ────────────────────────────────────
WEATHER_BASE_URL = os.getenv("WEATHER_BASE_URL", "https://api.open-meteo.com")
WEATHER_TIMEOUT_SECONDS = float(os.getenv("WEATHER_TIMEOUT_SECONDS", "15"))
WEATHER_CACHE_TTL_SECONDS = int(os.getenv("WEATHER_CACHE_TTL_SECONDS", "900"))
WEATHER_MAX_BATCH_COORDINATES = int(os.getenv("WEATHER_MAX_BATCH_COORDINATES", "200"))

# ── External geocoding API settings ──────────────────────────────────
GEOCODING_BASE_URL = os.getenv("GEOCODING_BASE_URL", "https://geocoding-api.open-meteo.com")
GEOCODING_TIMEOUT_SECONDS = float(os.getenv("GEOCODING_TIMEOUT_SECONDS", "10"))
GEOCODING_CACHE_TTL_SECONDS = int(os.getenv("GEOCODING_CACHE_TTL_SECONDS", "86400"))

# ── Trip plan limits ─────────────────────────────────────────────────
PLAN_MAX_HEATMAP_POINTS = int(os.getenv("PLAN_MAX_HEATMAP_POINTS", "500"))
PLAN_HEATMAP_HOURS = int(os.getenv("PLAN_HEATMAP_HOURS", "49"))
PLAN_WEATHER_BUFFER_HOURS = float(os.getenv("PLAN_WEATHER_BUFFER_HOURS", "2"))
PLAN_MAX_CHECKPOINTS_PER_ROUTE = int(os.getenv("PLAN_MAX_CHECKPOINTS_PER_ROUTE", "1000"))
