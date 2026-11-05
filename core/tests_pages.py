"""Render tests for the site's own page set (templates/core/ + site_pages.py).

Architecture: every page in core.site_pages.PAGES renders through the site's
own Django templates (templates/core/page.html, or the bespoke core page for
the main URLs). Nothing is served from mirror HTML any more.
"""
from django.test import TestCase
from django.utils.html import escape

from .site_pages import PAGES

# Slugs served by a dedicated view at a root URL (core/urls.py) instead of the
# generic registry page template.
ROOT_SERVED = {
    "index", "about", "product-information", "service-support",
    "contact-us", "search",
}
# PAGES now holds only the legal pages and careers; the main pages above are
# templates served by their own views.


class RegistryPagesRender(TestCase):
    """Every registry page renders as our own template, cleanly."""

    def _content(self, html):
        return html.split("<main", 1)[1].split("</main>", 1)[0]

    def test_every_registry_page_renders_with_its_title(self):
        for slug, page in PAGES.items():
            if slug in ROOT_SERVED:
                continue  # covered by the bespoke core-page tests
            response = self.client.get(f"/{slug}/")
            self.assertEqual(response.status_code, 200, slug)
            # Titles carry & and quotes; the template escapes them.
            self.assertIn(f"<title>{escape(page['title'])}", response.content.decode(), slug)

    def test_pages_do_not_leak_template_syntax(self):
        for slug in PAGES:
            if slug in ROOT_SERVED:
                continue
            response = self.client.get(f"/{slug}/")
            self.assertEqual(response.status_code, 200, slug)
            html = response.content.decode()
            self.assertNotIn("{%", html, slug)
            self.assertNotIn("{{", html, slug)

    def test_pages_avoid_external_and_scripted_content(self):
        """The content area carries text and internal links only.

        Same guarantee the old mirror sanitiser gave, now by construction: the
        registry stores plain text and page.html emits links from it.
        """
        for slug in PAGES:
            if slug in ROOT_SERVED:
                continue
            response = self.client.get(f"/{slug}/")
            self.assertEqual(response.status_code, 200, slug)
            body = self._content(response.content.decode())
            self.assertNotIn("<script", body, slug)
            self.assertNotIn("<iframe", body, slug)
            self.assertNotIn("<form", body, slug)
            self.assertNotIn('src="http', body, slug)
            self.assertNotIn('action="http', body, slug)

    def test_every_page_has_the_site_shell(self):
        """Header/footer are shared: every page shows the logo and newsletter."""
        for slug in PAGES:
            if slug in ROOT_SERVED:
                continue
            response = self.client.get(f"/{slug}/")
            self.assertEqual(response.status_code, 200, slug)
            html = response.content.decode()
            self.assertIn("techno-mate-logo", html, slug)
            self.assertIn("Join Our Newsletter", html, slug)

    def test_unknown_slug_is_a_404(self):
        self.assertEqual(self.client.get("/no-such-page/").status_code, 404)

    def test_traversal_like_slugs_404(self):
        """The catch-all accepts strict lowercase slugs only."""
        self.assertEqual(self.client.get("/..%2fabout/").status_code, 404)
        self.assertEqual(self.client.get("/index.html/").status_code, 404)
        self.assertEqual(self.client.get("/legacy/").status_code, 404)
