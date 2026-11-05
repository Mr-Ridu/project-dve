#!/usr/bin/env python
"""One-click cPanel setup for a host with no SSH access.

Run this from cPanel -> Setup Python App -> "Run Python script", with the app's
virtualenv selected. It:

1. loads the app's .env file (or DJANGO_ENV_FILE),
2. generates DJANGO_SECRET_KEY and saves it to .env if it is missing,
3. installs requirements.txt into the app's virtualenv,
4. runs migrate, createcachetable and collectstatic,
5. creates the first superuser from DJANGO_SUPERUSER_* variables,
6. touches tmp/restart.txt so Passenger reloads the app.

It is safe to run again after an update: migrations and createcachetable are
idempotent and collectstatic overwrites changed files. It never deletes data.

Read docs/GO_LIVE_MANUAL_BN.md before running it.
"""
from __future__ import annotations

import os
import secrets
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = Path(os.environ.get("DJANGO_ENV_FILE") or (BASE_DIR / ".env"))
REQUIRED_PROD_VARS = (
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_STATIC_ROOT",
    "DJANGO_MEDIA_ROOT",
)


def load_env_file(path: Path) -> None:
    """Minimal KEY=VALUE loader. Existing environment variables win."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and value and not os.environ.get(key):
            os.environ[key] = value


def save_env_value(path: Path, key: str, value: str) -> None:
    """Set one key in .env, preserving the rest of the file."""
    lines = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    replaced = False
    for index, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == key:
            lines[index] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def fail(message: str) -> None:
    print("\nSETUP STOPPED\n" + message)
    sys.exit(1)


def main() -> None:
    os.chdir(BASE_DIR)
    print("Techno Mate site setup")
    print("Python:", sys.version.split()[0])
    print("Project:", BASE_DIR)

    load_env_file(ENV_FILE)
    settings_module = os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
    is_prod = settings_module.endswith(".prod")

    if is_prod:
        missing = [name for name in REQUIRED_PROD_VARS if not os.environ.get(name)]
        if missing:
            fail(
                "These values are missing from .env:\n  "
                + "\n  ".join(missing)
                + "\n\nAdd them, save the file, then run this script again."
            )
        if os.environ.get("DB_ENGINE", "").strip().lower() == "mysql":
            missing_db = [
                name
                for name in ("DB_NAME", "DB_USER", "DB_PASSWORD")
                if not os.environ.get(name)
            ]
            if missing_db:
                fail(
                    "DB_ENGINE=mysql but these database values are missing from .env:\n  "
                    + "\n  ".join(missing_db)
                )

    if not os.environ.get("DJANGO_SECRET_KEY"):
        generated = secrets.token_urlsafe(64)
        os.environ["DJANGO_SECRET_KEY"] = generated
        save_env_value(ENV_FILE, "DJANGO_SECRET_KEY", generated)
        print(f"Generated a new DJANGO_SECRET_KEY and saved it to {ENV_FILE}.")

    print("\n[1/5] Installing Python packages ...")
    if os.environ.get("CPANEL_SETUP_SKIP_PIP") == "1":
        print("Skipped (CPANEL_SETUP_SKIP_PIP=1).")
    else:
        try:
            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "-r",
                    str(BASE_DIR / "requirements.txt"),
                ]
            )
        except subprocess.CalledProcessError:
            fail(
                "pip install failed. Check that the host allows package installs "
                "and that the app's virtualenv is selected, then run again."
            )

    import django
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.core.management import call_command

    django.setup()

    print("\n[2/5] Checking settings ...")
    call_command("check", deploy=True)

    print("\n[3/5] Creating/updating database tables ...")
    database = settings.DATABASES["default"]
    if "sqlite3" in database["ENGINE"]:
        db_path = Path(database["NAME"])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if not os.access(db_path.parent, os.W_OK):
            fail(
                "The database folder is not writable:\n  "
                f"{db_path.parent}\n\n"
                "Fix the folder permission in cPanel -> File Manager, then run again."
            )
        print(f"Database: SQLite ({db_path})")
    else:
        print(f"Database: MySQL ({database['NAME']})")
    call_command("migrate", interactive=False)
    call_command("createcachetable")

    print("\n[4/5] Collecting static files ...")
    call_command("collectstatic", interactive=False, verbosity=0)
    Path(settings.STATIC_ROOT).mkdir(parents=True, exist_ok=True)
    Path(settings.MEDIA_ROOT).mkdir(parents=True, exist_ok=True)
    static_count = sum(
        1 for item in Path(settings.STATIC_ROOT).rglob("*") if item.is_file()
    )
    print(f"Static root: {settings.STATIC_ROOT} ({static_count} files)")
    print(f"Media root:  {settings.MEDIA_ROOT}")

    print("\n[5/5] Admin account ...")
    username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
    password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
    email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()
    if username and password:
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            print(f"Account '{username}' already exists; password left unchanged.")
        else:
            User.objects.create_superuser(
                username=username, email=email, password=password
            )
            print(f"Created superuser '{username}'.")
    else:
        print(
            "Skipped: set DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL and "
            "DJANGO_SUPERUSER_PASSWORD in .env, then run this script again."
        )

    (BASE_DIR / "tmp").mkdir(exist_ok=True)
    (BASE_DIR / "tmp" / "restart.txt").touch()

    print(
        "\nDONE. The app restart was requested.\n"
        "Open https://YOUR-DOMAIN/ and https://YOUR-DOMAIN/admin/ to check.\n"
        "If the site still shows an old page, use cPanel -> Setup Python App -> Restart."
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # keep the cPanel log readable for a non-developer
        print(f"\nSETUP FAILED: {type(exc).__name__}: {exc}")
        print("Copy the lines above and send them to your developer or host support.")
        raise
