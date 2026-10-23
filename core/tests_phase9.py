"""Phase 9 tests: accessibility invariants, responsive guards, security review.

The accessibility checks run against the HTML the server actually renders for
every converted page, so a regression in a partial fails here rather than in a
manual review. They assert the *floor* (no unlabelled control, no image without
an alt attribute, exactly one h1) — not that the design is pleasant.
"""
import os
import re
import subprocess
import sys
from html.parser import HTMLParser

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase

from tutorials.validators import MAX_THUMBNAIL_BYTES, validate_thumbnail_size

BASE_DIR = settings.BASE_DIR

PAGES = [
    "/",
    "/about/",
    "/products/",
    "/services/",
    "/contact/",
    "/tutorials/",
    "/search/?s=sarrp",
    "/accounts/login/",
    "/accounts/register/",
]

VOID = {"img", "input", "br", "meta", "link", "hr", "source", "area", "col", "embed", "track", "wbr"}


class _Audit(HTMLParser):
    """Collects the handful of facts the a11y tests need from rendered HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.h1 = 0
        self.tags = []           # (tag, attrs dict)
        self.labels_for = set()
        self.controls = []       # attrs dicts of input/select/textarea
        self.inside_label = 0
        self.control_in_label = []
        self.lang = None
        self._stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "h1":
            self.h1 += 1
        if tag == "label":
            self.inside_label += 1
            if a.get("for"):
                self.labels_for.add(a["for"])
        if tag in ("input", "select", "textarea"):
            self.controls.append(a)
            if self.inside_label:
                self.control_in_label.append(a)
        self.tags.append((tag, a))

    def handle_endtag(self, tag):
        if tag == "label" and self.inside_label:
            self.inside_label -= 1


def audit(client, url):
    response = client.get(url)
    parser = _Audit()
    parser.feed(response.content.decode())
    return response, parser


def has_accessible_name(control, parser):
    if control.get("type") == "hidden":
        return True
    if control.get("aria-label") or control.get("aria-labelledby"):
        return True
    if control.get("id") and control["id"] in parser.labels_for:
        return True
    return any(control is c for c in parser.control_in_label)


class AccessibilityInvariants(TestCase):
    """Rendered-HTML checks that apply to every page in the shell."""

    @classmethod
    def setUpTestData(cls):
        client = Client()
        cls.pages = {}
        for url in PAGES:
            response = client.get(url)
            cls.pages[url] = {"status": response.status_code, "html": response.content.decode()}

    def parser(self, url):
        parser = _Audit()
        parser.feed(self.pages[url]["html"])
        return parser

    def test_skip_link_and_main_landmark(self):
        for url, page in self.pages.items():
            html = page["html"]
            self.assertEqual(page["status"], 200, url)
            self.assertIn('class="skip-to-content"', html, url)
            self.assertIn('href="#site-main"', html, url)
            self.assertIn('<main id="site-main"', html, url)

    def test_viewport_allows_pinch_zoom(self):
        for url, page in self.pages.items():
            html = page["html"]
            m = re.search(r'<meta name="viewport" content="([^"]+)"', html)
            self.assertIsNotNone(m, url)
            self.assertNotIn("maximum-scale", m.group(1), url)
            self.assertNotIn("user-scalable=0", m.group(1), url)

    def test_accessibility_stylesheet_loads_after_theme(self):
        html = self.pages["/"]["html"]
        a11y = html.find("site-a11y.css")
        theme = html.find("style.css")
        self.assertGreater(a11y, -1, "site-a11y.css is not linked")
        self.assertGreater(a11y, theme, "a11y overrides must come after the theme")

    def test_each_page_has_exactly_one_h1(self):
        for url in self.pages:
            count = self.parser(url).h1
            self.assertEqual(count, 1, f"{url} has {count} h1 elements")

    def test_html_language_declared(self):
        for url in self.pages:
            lang = self.parser(url).lang
            self.assertTrue(lang, f"{url} has no <html lang>")
            self.assertTrue(lang.lower().startswith("en"), url)

    def test_every_image_has_an_alt_attribute(self):
        for url in self.pages:
            parser = self.parser(url)
            missing = [a.get("src", "?") for tag, a in parser.tags if tag == "img" and "alt" not in a]
            self.assertEqual(missing, [], f"{url}: images without alt: {missing[:5]}")

    def test_every_form_control_has_an_accessible_name(self):
        for url in self.pages:
            parser = self.parser(url)
            unnamed = [
                c.get("name") or c.get("id") or c.get("type")
                for c in parser.controls
                if not has_accessible_name(c, parser)
            ]
            self.assertEqual(unnamed, [], f"{url}: unlabelled controls: {unnamed}")

    def test_header_search_is_named(self):
        html = self.pages["/"]["html"]
        self.assertIn('aria-label="Search the site"', html)

    def test_search_page_has_a_labelled_field(self):
        html = self.pages["/search/?s=sarrp"]["html"]
        self.assertIn('for="site-search"', html)
        self.assertIn('id="site-search"', html)

    def test_player_iframe_gets_a_title(self):
        """WCAG 4.1.2 — the video iframe is created in JS, so check the source."""
        source = (BASE_DIR / "templates" / "tutorials" / "detail.html").read_text(encoding="utf-8")
        self.assertIn("iframe.title", source)


class ResponsiveGuards(SimpleTestCase):
    """The mobile overflow fixes are CSS; assert the rules survive edits."""

    def setUp(self):
        self.css = (BASE_DIR / "static" / "css" / "site-a11y.css").read_text(encoding="utf-8")

    def test_mobile_breakpoint_present(self):
        self.assertIn("@media (max-width: 767px)", self.css)

    def test_secondary_mobile_menu_is_stacked(self):
        # The theme absolutely positioned this panel 49px past a 375px viewport.
        self.assertIn("#menu-mobile-secondary-menu > li > ul.sub-menu", self.css)
        self.assertIn("position: static !important", self.css)

    def test_modules_are_capped_to_their_column(self):
        self.assertIn(".et_pb_column,", self.css)
        self.assertIn("max-width: 100% !important", self.css)

    def test_dashboard_tables_scroll_instead_of_widening_the_page(self):
        self.assertIn("main table {", self.css)
        self.assertIn("overflow-x: auto", self.css)


class DashboardAccessibility(SimpleTestCase):
    def test_table_headers_are_scoped(self):
        for path in (BASE_DIR / "templates" / "dashboard").glob("*.html"):
            html = path.read_text(encoding="utf-8")
            bare = re.findall(r"<th>", html)
            self.assertEqual(bare, [], f"{path.name}: <th> without scope")

    def test_filter_form_controls_are_labelled(self):
        html = (BASE_DIR / "templates" / "dashboard" / "user_list.html").read_text(encoding="utf-8")
        self.assertIn('for="user-q"', html)
        self.assertIn('for="user-status"', html)


def _run_with_prod_settings(code, extra_env=None):
    """Run `code` in a subprocess with the production settings module."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS", "DJANGO_SETTINGS_MODULE"}
    }
    env["PYTHONPATH"] = str(BASE_DIR)
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(BASE_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


class ProductionSettingsTests(SimpleTestCase):
    """The production profile must fail closed (Phase 1 report §12 item 7)."""

    def test_refuses_to_start_without_secret_key(self):
        result = _run_with_prod_settings(
            "import config.settings.prod", {"DJANGO_SETTINGS_MODULE": "config.settings.prod"}
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", result.stderr)

    def test_refuses_to_start_without_allowed_hosts(self):
        result = _run_with_prod_settings(
            "import config.settings.prod",
            {"DJANGO_SETTINGS_MODULE": "config.settings.prod", "DJANGO_SECRET_KEY": "x" * 50},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_ALLOWED_HOSTS", result.stderr)

    def test_hardening_flags(self):
        code = (
            "import os, django\n"
            "os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.prod'\n"
            "django.setup()\n"
            "from django.conf import settings as s\n"
            "print(s.DEBUG, s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE, "
            "s.SESSION_COOKIE_HTTPONLY, s.SECURE_SSL_REDIRECT, s.X_FRAME_OPTIONS, "
            "s.SECURE_CONTENT_TYPE_NOSNIFF, s.SECURE_HSTS_SECONDS)\n"
        )
        result = _run_with_prod_settings(
            code,
            {
                "DJANGO_SETTINGS_MODULE": "config.settings.prod",
                "DJANGO_SECRET_KEY": "x" * 50,
                "DJANGO_ALLOWED_HOSTS": "example.com",
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            "False True True True True DENY True 0",
        )

    def test_media_is_not_routed_in_production(self):
        code = (
            "import os, django\n"
            "os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.prod'\n"
            "django.setup()\n"
            "from django.urls import get_resolver\n"
            "print([str(p.pattern) for p in get_resolver().url_patterns])\n"
        )
        result = _run_with_prod_settings(
            code,
            {
                "DJANGO_SETTINGS_MODULE": "config.settings.prod",
                "DJANGO_SECRET_KEY": "x" * 50,
                "DJANGO_ALLOWED_HOSTS": "example.com",
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("media/", result.stdout)


class UploadValidationTests(TestCase):
    """Staff uploads are allow-listed and capped (report §12 item 7)."""

    def test_oversized_file_is_rejected(self):
        big = SimpleUploadedFile("big.png", b"0" * (MAX_THUMBNAIL_BYTES + 1), content_type="image/png")
        with self.assertRaises(ValidationError):
            validate_thumbnail_size(big)

    def test_small_file_passes(self):
        small = SimpleUploadedFile("small.png", b"0" * 1024, content_type="image/png")
        validate_thumbnail_size(small)  # must not raise

    def test_form_rejects_wrong_extension(self):
        from dashboard.forms import TutorialForm

        payload = SimpleUploadedFile("payload.exe", b"MZ" + b"0" * 64, content_type="application/octet-stream")
        form = TutorialForm(data={"title": "T", "video_provider": "none"}, files={"thumbnail": payload})
        self.assertFalse(form.is_valid())
        self.assertIn("thumbnail", form.errors)

    def test_form_rejects_oversized_image(self):
        from dashboard.forms import TutorialForm

        big = SimpleUploadedFile("big.png", b"0" * (MAX_THUMBNAIL_BYTES + 1), content_type="image/png")
        form = TutorialForm(data={"title": "T", "video_provider": "none"}, files={"thumbnail": big})
        self.assertFalse(form.is_valid())
        self.assertIn("thumbnail", form.errors)

    def test_transport_level_limits_are_configured(self):
        self.assertLessEqual(settings.FILE_UPLOAD_MAX_MEMORY_SIZE, 5 * 1024 * 1024)
        self.assertLessEqual(settings.DATA_UPLOAD_MAX_MEMORY_SIZE, 10 * 1024 * 1024)
