"""cPanel Passenger entry point.

cPanel's "Setup Python App" looks for this exact file at the application root and
expects a module-level WSGI callable. It stays thin on purpose: the application
object lives in config/wsgi.py so the web server and manage.py share one
configuration.

Passenger does not read .env files. Set the variables in the cPanel UI
(Setup Python App -> Environment variables), or point DJANGO_ENV_FILE at a file
outside public_html and this module will load it before Django starts. A
non-empty environment variable always wins over the file.

See docs/PHASE10_DEPLOYMENT_CPANEL.md.
"""
import os
from pathlib import Path


def _load_env_file(path):
    """Minimal KEY=VALUE loader (no extra dependency). Returns True if read."""
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
        if key and not os.environ.get(key):
            # A blank variable in the cPanel UI should be filled from the file
            # rather than silently overriding it with "".
            os.environ[key] = value
    return True


BASE_DIR = Path(__file__).resolve().parent
_load_env_file(os.environ.get("DJANGO_ENV_FILE", str(BASE_DIR / ".env")))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

from config.wsgi import application  # noqa: E402  (must follow env loading)
