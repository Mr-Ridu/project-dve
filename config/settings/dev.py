"""Development settings — never used in production."""
from .base import *  # noqa: F401,F403
from .base import BASE_DIR

DEBUG = True

# Clearly-insecure fallback so the project runs out of the box locally.
# Real development against shared data should set DJANGO_SECRET_KEY.
SECRET_KEY = os.environ.get(  # noqa: F405
    "DJANGO_SECRET_KEY", "dev-only-insecure-key-never-use-in-production"
)

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# Verbose, immediate errors during development.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
