"""Base settings shared by development and production.

Configuration is environment-driven so the same code runs locally and on
cPanel shared hosting (see docs/PHASE1_INSPECTION_REPORT.md §9). Secrets are
never committed; they arrive via environment variables only.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env_bool(name, default=False):
    """Read a boolean environment variable (1/true/yes/on)."""
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on") if name in os.environ else default


# --- Security ---------------------------------------------------------------
# dev.py supplies an insecure development fallback; prod.py refuses to start
# without a real value.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")

# --- Applications -----------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

LOCAL_APPS = [
    "core.apps.CoreConfig",
    "accounts.apps.AccountsConfig",
    "tutorials.apps.TutorialsConfig",
    "dashboard.apps.DashboardConfig",
]

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# --- Templates --------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.company",
            ],
        },
    },
]

# --- Database ---------------------------------------------------------------
# SQLite is the default everywhere, including cPanel. The database file lives
# outside public_html, so the web server cannot serve it. Set DB_ENGINE=mysql
# plus the connection variables to move to MySQL 8.0.11+/MariaDB 10.5+ later.
# No SQLite-specific behaviour is used in application code (see
# docs/PHASE1_INSPECTION_REPORT.md §7).
if os.environ.get("DB_ENGINE", "sqlite").strip().lower() == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("DB_NAME", ""),
            "USER": os.environ.get("DB_USER", ""),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "3306"),
            # utf8mb4 everywhere — set the database collation to
            # utf8mb4_unicode_ci when creating it (Phase 10 guide).
            "OPTIONS": {"charset": "utf8mb4"},
        }
    }
else:
    sqlite_path = Path(os.environ.get("DJANGO_DB_PATH") or (BASE_DIR / "db.sqlite3"))
    if not sqlite_path.is_absolute():
        sqlite_path = BASE_DIR / sqlite_path
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": sqlite_path,
            # Passenger may handle a few writes at once; wait for the lock
            # instead of failing immediately with "database is locked".
            "OPTIONS": {"timeout": 20},
        }
    }

# Custom user model — must stay set before the first migration (approved
# decision: extend AbstractUser).
AUTH_USER_MODEL = "accounts.User"

# --- Auth flow --------------------------------------------------------------
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "core:home"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Tutorial access ---------------------------------------------------------
# Approved accounts open the whole published library by default: no manual
# per-tutorial grants are needed. Set TUTORIALS_REQUIRE_GRANTS=1 to restore the
# stricter model (access_all_tutorials flag or an explicit TutorialAccess row).
# The dashboard grant tools and the flag stay available either way.
TUTORIALS_REQUIRE_GRANTS = env_bool("TUTORIALS_REQUIRE_GRANTS", False)

# --- Internationalisation ---------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Static & media ---------------------------------------------------------
# static/ holds the existing site assets, unchanged; URLs stay /static/... so
# converted templates need only {% static %} tags around existing paths.
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
# collectstatic target. On cPanel without SSH, point this at a public_html
# subfolder (DJANGO_STATIC_ROOT=/home/USER/public_html/static) so the web
# server serves the files without a symlink.
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT") or (BASE_DIR / "staticfiles"))

# media/ is for public uploads only (e.g. tutorial thumbnails).
# Private video must never live here — see report §8/§9.
MEDIA_URL = "/media/"
# Public uploads only (tutorial thumbnails). Point DJANGO_MEDIA_ROOT at
# /home/USER/public_html/media on cPanel so thumbnails are web-served.
MEDIA_ROOT = Path(os.environ.get("DJANGO_MEDIA_ROOT") or (BASE_DIR / "media"))

# --- Upload limits (Phase 9 security checklist) ------------------------------
# Django refuses requests above DATA_UPLOAD_MAX_MEMORY_SIZE and spills files
# above FILE_UPLOAD_MAX_MEMORY_SIZE to disk. The thumbnail validator applies the
# per-file rule on top of these transport-level caps.
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# --- Video signing (Phase 6 provider, Phase 10 wiring) -----------------------
# Bunny Stream keys live in the environment, never in the repository. Empty
# values mean "not configured yet": the playback endpoint answers 503 rather
# than handing out an unsigned embed.
BUNNY_STREAM_LIBRARY_ID = os.environ.get("BUNNY_STREAM_LIBRARY_ID", "")
BUNNY_STREAM_SECURITY_KEY = os.environ.get("BUNNY_STREAM_SECURITY_KEY", "")
# Management key for dashboard uploads (Bunny -> Stream -> library -> API).
# Different value from the security key above, which only signs playback.
# Empty means "upload disabled": the dashboard form explains what is missing.
BUNNY_STREAM_API_KEY = os.environ.get("BUNNY_STREAM_API_KEY", "")

# --- Rate limits ------------------------------------------------------------
# {scope: (max_requests, window_seconds)}, consumed by core.throttle. Counted
# per (action, client IP, account) in the cache; a burst past the limit gets an
# honest 429. These are brakes against hammering, not authorization.
RATE_LIMITS = {
    "auth": (5, 300),          # login/register failures (accounts.throttle)
    "playback": (60, 300),     # authorize + redeem together: ~30 plays / 5 min
    "progress": (120, 300),    # watch heartbeats
    "forms": (30, 300),        # form stub submissions
    "search": (60, 300),       # search queries
    "upload": (30, 900),       # dashboard tutorial saves (uploads included)
}

# --- Cache -------------------------------------------------------------------
# The playback handshake stores a one-time token in the cache. LocMem is
# per-process, so on a host with several workers the redeem request can land on
# a worker that never saw the token. Development uses LocMem; production
# overrides this with the shared database cache (see prod.py).
if os.environ.get("DJANGO_CACHE_BACKEND", "locmem").strip().lower() == "database":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "django_cache",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "tmt-locmem",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
