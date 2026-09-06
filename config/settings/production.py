"""Production settings — DEBUG off, security hardened.

Secrets come from environment variables, which Azure App Service injects
from Key Vault references at runtime. There is no local .env in production.
"""
import sys

from .base import *  # noqa

DEBUG = False

# ── Static files via WhiteNoise (serves Django admin + DRF browsable assets) ──
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
    "whitenoise.middleware.WhiteNoiseMiddleware",
)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# ── HTTPS / security (App Service terminates TLS and sets X-Forwarded-Proto) ──
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# Django 4+ requires scheme-qualified origins for admin/CSRF over HTTPS.
CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in ALLOWED_HOSTS if h not in ("localhost", "127.0.0.1", "*")
]

# ── Logging ──────────────────────────────────────────────────────────────────
# Without this block a 500 leaves no trace at all: Django's default console
# handler carries the require_debug_true filter, so with DEBUG=False every
# record is dropped and `az webapp log tail` stays empty while the request
# fails. Gunicorn on App Service captures stdout into the container log, so
# writing there is enough to make errors visible.
#
# Raise the floor with the DJANGO_LOG_LEVEL app setting when debugging; the
# default stays quiet enough for a B1 plan.
LOG_LEVEL = env("DJANGO_LOG_LEVEL", default="INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "verbose",
        },
    },
    # Third-party libraries stay quiet unless something is actually wrong.
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        # The one that matters: every unhandled 500 with its full traceback.
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        # Project code: predictions, AI modules, telemetry.
        "ai_modules": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}
