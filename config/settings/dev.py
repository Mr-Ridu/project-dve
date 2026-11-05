"""Development settings — never used in production."""
import os
from pathlib import Path

# --- local .env -------------------------------------------------------------
# `manage.py` reads real environment variables only, so put development secrets
# in a gitignored `.env` at the project root instead of exporting them in every
# new terminal. Loaded BEFORE importing base, because base reads the environment
# at import time. A variable already present in the environment wins.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _load_env_file(path):
    """Minimal KEY=VALUE loader (same rules as passenger_wsgi.py)."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and value and not os.environ.get(key):
            os.environ[key] = value
    return True


_load_env_file(os.environ.get("DJANGO_ENV_FILE", BASE_DIR / ".env"))

from .base import *  # noqa: F401,F403
from .base import BASE_DIR  # noqa: F811

DEBUG = True

# Clearly-insecure fallback so the project runs out of the box locally.
# Real development against shared data should set DJANGO_SECRET_KEY.
SECRET_KEY = os.environ.get(  # noqa: F405
    "DJANGO_SECRET_KEY", "dev-only-insecure-key-never-use-in-production"
)

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# Verbose, immediate errors during development.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
