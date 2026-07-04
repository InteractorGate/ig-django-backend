"""Test settings — fast, self-contained, no external services.

Runs on an in-memory SQLite database (no Azure SQL) and expects Cosmos DB to
be mocked in the tests (no real MongoDB connection). Safe to import in CI
without a ``.env`` file: required env vars get harmless dummy defaults *before*
``base`` is imported.

    python manage.py test --settings=config.settings.test
"""
import os

# Provide dummy values so base.py's env() calls don't fail in CI (no .env).
# env.read_env() uses setdefault semantics, so a real local .env never clashes
# with these — and every value here is overridden or unused during tests.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DJANGO_DEBUG", "False")
os.environ.setdefault("SQL_DB", "test")
os.environ.setdefault("SQL_USER", "test")
os.environ.setdefault("SQL_PASSWORD", "test")
os.environ.setdefault("SQL_HOST", "localhost")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test")
os.environ.setdefault("MONGO_DB", "test")

from .base import *  # noqa: E402,F403

# ── In-memory SQLite: fast, no Azure SQL / ODBC driver needed ─────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# ── Speed: cheap password hashing (tests create many users) ───────────────────
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# ── Throttling off by default so unrelated tests don't hit rate limits. ───────
# The dedicated throttle test re-enables a scope via override_settings.
REST_FRAMEWORK = {**REST_FRAMEWORK}  # noqa: F405 — copy base config, don't mutate it
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": None,
    "user": None,
    "login": None,
    "register": None,
}
