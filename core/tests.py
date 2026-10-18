"""Tests for the Phase 3 template conversion.

Covers: all 56 original URLs still resolve; the converted core pages carry the
original design's structure; static references resolve to real files; no
third-party endpoint, tracker or external form action is served; CSRF protects
the local form stub; unknown/traversal URLs return the custom 404.
"""
import re

from django.contrib.staticfiles import finders
from django.test import Client, TestCase
from django.urls import reverse

# All 56 mirrored pages (legacy/ file stems).
ALL_SLUGS = [
    "404", "about", "accessibility-statement", "agb", "benign-conditions",
    "benign-hyperproliferative-diseases", "blog", "cabinet-irradiators",
    "careers", "case-studies", "category-type-pres",
    "characterization-and-biological-validation-of-photon-flash", "cix-flash",
    "cix2", "cix3", "clinical-systems", "contact-us", "cookie-policy",
    "events", "for-patients", "history-of-x-rays",
    "image-guided-irradiators", "impressum", "index",
    "introducing-the-sarrp-education-series-expert-training-from-penn-medicine-xstrahl",
    "legal-notices", "news", "nmsc-webcast",
    "non-melanoma-skin-cancer-nmsc", "palliative-applications",
    "palliative-care", "presentations", "privacy-policy",
    "product-information", "publications", "radiant", "radiation-research",
    "research-reviews", "sarrp-beamline", "sarrp-education-and-training-series",
    "sarrp-flash", "sarrp", "search", "service-support", "skin-cancer",
    "smart-rad-overview", "support", "terms-conditions", "user-spotlights",
    "vet", "xenx", "xstrahl-100", "xstrahl-150", "xstrahl-200",
    "xstrahl-300",
    "xstrahl-marks-30-years-of-advancing-radiation-therapy-on-world-radiotherapy-awareness-day",
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
    """Every original page URL must keep working."""

    def test_all_56_original_urls_return_200(self):
        bad = []
        for slug in ALL_SLUGS:
            r = self.client.get(url_for(slug))
            if r.status_code != 200:
                bad.append((url_for(slug), r.status_code))
        self.assertEqual(bad, [], f"URLs not returning 200: {bad}")

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
            'id="main-content"',
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
        self.assertIn("page-id-72", html)

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
        self.assertGreater(len(checked), 20, "too few static references parsed")
        self.assertEqual(missing, [], f"missing static files: {missing}")


class SanitizationTests(TestCase):
    """No third-party endpoint, tracker or external form action may be served."""

    def test_all_56_pages_are_clean(self):
        offenders = []
        for slug in ALL_SLUGS:
            html = self.client.get(url_for(slug)).content.decode("utf-8", "replace")
            for needle in FORBIDDEN:
                if needle in html:
                    offenders.append((url_for(slug), needle))
        self.assertEqual(offenders, [], f"third-party remnants: {offenders}")

    def test_no_external_form_actions(self):
        ext = re.compile(r"<form\b[^>]*\baction=[\"']https?://", re.I)
        for slug in ALL_SLUGS:
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
