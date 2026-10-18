"""Production settings for cPanel shared hosting (Passenger WSGI).

Requires environment variables:
  DJANGO_SECRET_KEY        (mandatory)
  DJANGO_ALLOWED_HOSTS     comma-separated, e.g. "example.com,www.example.com"
Optional:
  DJANGO_SSL_REDIRECT      "1" (default) to force HTTPS
  DJANGO_HSTS_SECONDS      default 0; raise only after HTTPS is verified
  DB_ENGINE/DB_NAME/DB_USER/DB_PASSWORD/DB_HOST/DB_PORT
"""
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import env_bool

DEBUG = False

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")  # noqa: F405
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production.")

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]  # noqa: F405
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set in production.")

# --- HTTPS / cookie hardening (report §12 item 7) ---------------------------
SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
# HSTS stays off (0) until the certificate is confirmed active on the host.
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "0"))  # noqa: F405
# cPanel/Passenger often sits behind a proxy that terminates TLS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Server-friendly logging to stderr (cPanel captures it in the app log).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},  # noqa: F405
}
