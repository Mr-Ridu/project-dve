"""Tests for the template conversion.

Covers: the live industrial pages resolve and the removed medical pages are
gone; the converted core pages carry the site shell; static references resolve
to real files; no third-party endpoint, tracker or external form action is
served; CSRF protects the local form stub; unknown/traversal URLs return 404.
"""
import re

from django.contrib.staticfiles import finders
from django.test import Client, TestCase
from django.urls import reverse

# Pages the industrial site keeps live.
LIVE_SLUGS = [
    "about", "accessibility-statement", "careers", "contact-us", "cookie-policy",
    "legal-notices", "privacy-policy", "product-information", "service-support",
    "terms-conditions",
]

# Former medical URLs that must no longer resolve after the rebrand.
REMOVED_SLUGS = [
    "clinical-systems", "radiant", "xstrahl-100", "xstrahl-150", "xstrahl-200",
    "xstrahl-300", "radiation-research", "sarrp", "sarrp-flash", "sarrp-beamline",
    "xenx", "cix2", "cix3", "cix-flash", "image-guided-irradiators",
    "cabinet-irradiators", "skin-cancer", "non-melanoma-skin-cancer-nmsc",
    "benign-conditions", "palliative-care", "for-patients", "events", "news",
    "presentations", "case-studies", "publications", "vet", "impressum", "agb",
]

CORE_URLS = {
    "index": "/",
    "about": "/about/",
    "product-information": "/product-information/",
    "service-support": "/service-support/",
    "contact-us": "/contact-us/",
}

FORBIDDEN = [
    "admin-ajax.php",          # original WordPress form endpoint
    "app.jazz.co",             # third-party chat widget
    "bat.bing.com",            # Bing tracking pixel
    "desk.zoho.com",           # original company's support desk
    "use.typekit.net",         # external font CSS
    "Meta Pixel",              # Facebook pixel blocks
    "FacebookSignal",          # Facebook signal bootstrap
]


def url_for(slug):
    """Original URL of a mirrored page (approved: original slugs preserved)."""
    if slug in CORE_URLS:
        return CORE_URLS[slug]
    return f"/{slug}/"


class ScaffoldTests(TestCase):
    """Phase 2 smoke tests: the project serves pages and resolves URLs."""

    def test_home_renders(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)

    def test_admin_login_page_loads(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)

    def test_404_for_unknown_page(self):
        response = self.client.get("/no-such-page/")
        self.assertEqual(response.status_code, 404)


class UrlCoverageTests(TestCase):
    """The live pages resolve; the removed medical pages return 404."""

    def test_live_page_urls_return_200(self):
        bad = []
        for slug in LIVE_SLUGS:
            r = self.client.get(url_for(slug))
            if r.status_code != 200:
                bad.append((url_for(slug), r.status_code))
        self.assertEqual(bad, [], f"URLs not returning 200: {bad}")

    def test_removed_medical_urls_are_gone(self):
        still_live = [slug for slug in REMOVED_SLUGS if self.client.get(f"/{slug}/").status_code != 404]
        self.assertEqual(still_live, [], f"removed pages still resolving: {still_live}")

    def test_core_aliases_and_named_urls(self):
        for name in ("core:home", "core:about", "core:products",
                     "core:services", "core:contact"):
            url = reverse(name)
            self.assertEqual(self.client.get(url).status_code, 200, name)
        for url in ("/products/", "/services/", "/contact/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)


class DesignFidelityTests(TestCase):
    """The converted pages must carry the original design's structure."""

    def test_shell_markers_on_core_pages(self):
        markers = [
            "techno-mate-logo",       # logo asset
            # Intentional change (user-requested navbar cleanup): the dead
            # industry strip (Pharma & Biotech… — all href="#") was removed
            # from the header, so the kept CTA button now marks the shell.
            "Request Support",
            "Techno Mate Technologies",  # footer/site name
            'id="site-main"',
            "Join Our Newsletter",
        ]
        for slug in CORE_URLS:
            html = self.client.get(url_for(slug)).content.decode("utf-8", "replace")
            for m in markers:
                self.assertIn(m, html, f"{slug}: missing {m!r}")

    def test_body_class_per_page(self):
        html = self.client.get("/").content.decode("utf-8", "replace")
        self.assertIn('<body class="home', html)
        html = self.client.get("/about/").content.decode("utf-8", "replace")
        self.assertIn('class="page-about', html)

    def test_no_unrendered_template_tags(self):
        for slug in CORE_URLS:
            html = self.client.get(url_for(slug)).content.decode("utf-8", "replace")
            self.assertNotIn("{% static", html, slug)
            self.assertNotIn("{% url", html, slug)
            self.assertNotIn("{{ request.path }}", html, slug)

    def test_page_titles_preserved(self):
        self.assertIn("<title>About Techno Mate Technologies</title>",
                      self.client.get("/about/").content.decode("utf-8", "replace"))


class StaticResolutionTests(TestCase):
    """Every /static/... reference in rendered core pages must exist."""

    def test_static_references_resolve(self):
        missing = []
        checked = set()
        for slug in CORE_URLS:
            html = self.client.get(url_for(slug)).content.decode("utf-8", "replace")
            for ref in set(re.findall(r"/static/([A-Za-z0-9_%\-./]+\.[A-Za-z0-9]{1,6})", html)):
                ref = ref.split("?")[0].split("#")[0]
                if ref in checked:
                    continue
                checked.add(ref)
                if not finders.find(ref):
                    missing.append(ref)
        for required in ("css/app.css", "js/app.js"):
            self.assertIn(required, checked, "shell lost a required asset")
        self.assertEqual(missing, [], f"missing static files: {missing}")


class SanitizationTests(TestCase):
    """No third-party endpoint, tracker or external form action may be served."""

    def test_all_live_pages_are_clean(self):
        offenders = []
        for slug in LIVE_SLUGS:
            html = self.client.get(url_for(slug)).content.decode("utf-8", "replace")
            for needle in FORBIDDEN:
                if needle in html:
                    offenders.append((url_for(slug), needle))
        self.assertEqual(offenders, [], f"third-party remnants: {offenders}")

    def test_no_external_form_actions(self):
        ext = re.compile(r"<form\b[^>]*\baction=[\"']https?://", re.I)
        for slug in LIVE_SLUGS:
            html = self.client.get(url_for(slug)).content.decode("utf-8", "replace")
            self.assertIsNone(ext.search(html), f"{slug}: external form action")

    def test_forms_target_local_stub(self):
        html = self.client.get("/").content.decode("utf-8", "replace")
        self.assertIn('action="/forms/placeholder/"', html)


class FormCsrfTests(TestCase):
    """The local form stub must enforce CSRF on state-changing requests."""

    def test_post_without_csrf_token_is_rejected(self):
        c = Client(enforce_csrf_checks=True)
        r = c.post("/forms/placeholder/", {"name": "x"})
        self.assertEqual(r.status_code, 403)

    def test_get_stub_renders(self):
        r = self.client.get("/forms/placeholder/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Thank you", r.content.decode("utf-8", "replace"))


class NotFoundTests(TestCase):
    """Unknown and malformed paths return the custom 404 — never 500."""

    def test_unknown_slug_404(self):
        r = self.client.get("/no-such-page/")
        self.assertEqual(r.status_code, 404)
        self.assertIn("Page not found", r.content.decode("utf-8", "replace"))

    def test_traversal_like_slugs_404(self):
        for url in ("/....%2F....%2Fetc/", "/.git/", "/UPPER/", "/a%20b/",
                    "/legacy/", "/index.html/"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 404, url)
