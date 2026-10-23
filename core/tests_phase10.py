"""Phase 10 tests: the deployment configuration the guides rely on.

These are configuration assertions, not a deployment test — Passenger, MySQL and
cPanel itself cannot run here. They catch the failures that would otherwise only
appear on the host: a missing WSGI entry point, Bunny keys never wired to the
environment, a per-worker cache silently breaking the playback handshake, and
secrets accidentally committed inside the docs.
"""
import os
import re
import subprocess
import sys
import tempfile

from django.conf import settings
from django.test import SimpleTestCase

BASE_DIR = settings.BASE_DIR

CLEAN_ENV = {
    k: v
    for k, v in os.environ.items()
    if k
    not in {
        "DJANGO_SETTINGS_MODULE",
        "DJANGO_SECRET_KEY",
        "DJANGO_ALLOWED_HOSTS",
        "DJANGO_CACHE_BACKEND",
        "DJANGO_ENV_FILE",
        "DB_ENGINE",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
        "DB_HOST",
        "DB_PORT",
        "BUNNY_STREAM_LIBRARY_ID",
        "BUNNY_STREAM_SECURITY_KEY",
    }
}


def run_python(lines, extra_env=None):
    """Run a small program with the production settings module."""
    program = "\n".join(lines)
    env = dict(CLEAN_ENV)
    env["PYTHONPATH"] = str(BASE_DIR)
    env["PYTHONIOENCODING"] = "utf-8"
    env["DJANGO_SETTINGS_MODULE"] = "config.settings.prod"
    env["DJANGO_SECRET_KEY"] = "x" * 50
    env["DJANGO_ALLOWED_HOSTS"] = "example.com"
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, "-c", program],
        cwd=str(BASE_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


class PassengerEntryPointTests(SimpleTestCase):
    """cPanel loads passenger_wsgi.py; it must exist and expose `application`."""

    def test_file_exists_at_project_root(self):
        self.assertTrue((BASE_DIR / "passenger_wsgi.py").is_file())

    def test_exposes_a_callable_application(self):
        result = run_python(
            [
                "import passenger_wsgi as p",
                "from django.conf import settings",
                "print(callable(p.application))",
                "print(settings.DEBUG)",
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["True", "False"])

    def test_loads_env_file_when_pointed_at_one(self):
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as handle:
            handle.write("DJANGO_ALLOWED_HOSTS=envfile.example.com,www.envfile.example.com\n")
            path = handle.name
        try:
            result = run_python(
                [
                    "import passenger_wsgi",
                    "from django.conf import settings",
                    "print(settings.ALLOWED_HOSTS)",
                ],
                {"DJANGO_ENV_FILE": path, "DJANGO_ALLOWED_HOSTS": ""},
            )
        finally:
            os.unlink(path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("envfile.example.com", result.stdout)

    def test_absolute_paths_do_not_hardcode_a_username(self):
        source = (BASE_DIR / "passenger_wsgi.py").read_text(encoding="utf-8")
        self.assertNotIn("/home/", source)


class EnvironmentWiringTests(SimpleTestCase):
    """Settings the guides tell the operator to set must actually be read."""

    def test_bunny_keys_come_from_the_environment(self):
        result = run_python(
            [
                "from django.conf import settings",
                "print(settings.BUNNY_STREAM_LIBRARY_ID)",
                "print(settings.BUNNY_STREAM_SECURITY_KEY)",
            ],
            {"BUNNY_STREAM_LIBRARY_ID": "12345", "BUNNY_STREAM_SECURITY_KEY": "test-key-not-real"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["12345", "test-key-not-real"])

    def test_bunny_keys_default_to_empty_not_undefined(self):
        result = run_python(
            [
                "from django.conf import settings",
                "print(repr(settings.BUNNY_STREAM_LIBRARY_ID), repr(settings.BUNNY_STREAM_SECURITY_KEY))",
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "'' ''")

    def test_production_defaults_to_the_shared_database_cache(self):
        result = run_python(
            [
                "from django.conf import settings",
                "print(settings.CACHES['default']['BACKEND'])",
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DatabaseCache", result.stdout)

    def test_cache_can_be_overridden_to_locmem(self):
        result = run_python(
            [
                "from django.conf import settings",
                "print(settings.CACHES['default']['BACKEND'])",
            ],
            {"DJANGO_CACHE_BACKEND": "locmem"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("LocMemCache", result.stdout)

    def test_development_uses_locmem(self):
        self.assertIn("LocMemCache", settings.CACHES["default"]["BACKEND"])

    def test_mysql_engine_and_charset(self):
        result = run_python(
            [
                "from django.conf import settings",
                "db = settings.DATABASES['default']",
                "print(db['ENGINE'], db['OPTIONS']['charset'], db['NAME'], db['USER'])",
            ],
            {
                "DB_ENGINE": "mysql",
                "DB_NAME": "USER_tmt",
                "DB_USER": "USER_tmt",
                "DB_PASSWORD": "pw",
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("django.db.backends.mysql", result.stdout)
        self.assertIn("utf8mb4", result.stdout)
        self.assertIn("USER_tmt", result.stdout)

    def test_static_root_is_the_collectstatic_target(self):
        self.assertEqual(settings.STATIC_ROOT.name, "staticfiles")
        self.assertIn(BASE_DIR / "static", settings.STATICFILES_DIRS)


class DeploymentDocTests(SimpleTestCase):
    """The guides are deliverables; they must not leak real credentials."""

    DOCS = {
        "deployment": "docs/PHASE10_DEPLOYMENT_CPANEL.md",
        "mysql": "docs/PHASE10_SQLITE_TO_MYSQL.md",
    }

    def read(self, key):
        return (BASE_DIR / self.DOCS[key]).read_text(encoding="utf-8")

    def test_docs_exist(self):
        for key, path in self.DOCS.items():
            self.assertTrue((BASE_DIR / path).is_file(), path)

    def test_no_secret_values_in_docs(self):
        pattern = re.compile(
            r"(SECRET_KEY|SECURITY_KEY|DB_PASSWORD|API_KEY)\s*=\s*[\"']?([A-Za-z0-9_\-]{16,})"
        )
        for key in self.DOCS:
            for num, line in enumerate(self.read(key).splitlines(), 1):
                match = pattern.search(line)
                if match:
                    self.fail(
                        f"{self.DOCS[key]}:{num} contains what looks like a real secret: "
                        f"{match.group(0)[:40]}"
                    )

    def test_deployment_guide_covers_the_required_steps(self):
        text = self.read("deployment")
        for needle in (
            "passenger_wsgi.py",
            "DJANGO_SECRET_KEY",
            "DJANGO_ALLOWED_HOSTS",
            "collectstatic",
            "createcachetable",
            "clearsessions",
            "DJANGO_HSTS_SECONDS",
            "mysqldump",
        ):
            self.assertIn(needle, text)

    def test_deployment_guide_warns_about_media_mapping(self):
        text = self.read("deployment")
        self.assertIn("Do **not** symlink the whole `media/` directory", text)

    def test_mysql_guide_covers_export_and_rollback(self):
        text = self.read("mysql")
        for needle in ("dumpdata", "loaddata", "createcachetable", "Rollback", "utf8mb4"):
            self.assertIn(needle, text)
