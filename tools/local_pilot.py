"""Local-only pilot: SQLite + Mongo on loopback; never uses cloud databases."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for key, value in {
    "DJANGO_SECRET_KEY": "local-block3-pilot-not-production-2026-abcdef123456",
    "SQL_DB": "unused", "SQL_USER": "unused", "SQL_PASSWORD": "unused",
    "SQL_HOST": "localhost", "MONGO_URI": "mongodb://127.0.0.1:27019",
    "MONGO_DB": "ig_block3_pilot",
}.items():
    os.environ.setdefault(key, value)
os.environ["DJANGO_SECRET_KEY"] = "local-block3-pilot-not-production-2026-abcdef123456"
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.test"

import django
from django.conf import settings
from django.core.management import call_command

settings.DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3",
    "NAME": str(Path(tempfile.gettempdir()) / "ig-block3-pilot.sqlite3")}}
settings.MONGODB = {"URI": "mongodb://127.0.0.1:27019", "DB": "ig_block3_pilot"}
settings.ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.PBKDF2PasswordHasher"]
django.setup()

from django.contrib.auth import get_user_model

call_command("migrate", interactive=False, verbosity=0)
for code in ("LOCAL_B3", "LOCAL_B3_2"):
    user, created = get_user_model().objects.get_or_create(
        username=code, defaults={"email": f"{code.lower()}@example.com"})
    if created:
        # Synthetic credentials restricted to this disposable local database.
        user.set_password("Local-B3-only-2026!")
        user.save()
print("Local pilot at http://127.0.0.1:8000; accounts LOCAL_B3 / LOCAL_B3_2.", flush=True)
call_command("runserver", "127.0.0.1:8000", use_reloader=False)
