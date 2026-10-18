"""Phase 8 tests: search, watch progress, category pages, player wiring."""
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from .tests_catalog import CatalogBase


class SearchTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_empty_query_renders_hint(self):
        r = self.client.get("/search/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Type what you are looking for", r.content.decode())

    def test_accuracy_terms_reverse_for_legacy_pages(self):
        """A term matching a page title/slug outranks mere body matches."""
        r = self.client.get("/search/", {"s": "SARRP"})
        html = r.content.decode()
        self.assertIn("sarrp", html.lower())  # result link present
        # top result must be a SARRP page, not a random body mention
        first = html[html.find("<h2>Pages</h2>"):]
        first_link = first[first.find('href="/') + 7:]
        first_link = first_link[:first_link.find("/")]
        self.assertTrue(first_link.startswith("sarrp"), first_link)

    def test_no_results_message(self):
        r = self.client.get("/search/", {"s": "xyzzyspooncompareToNothing"})
        self.assertIn("No results", r.content.decode())

    def test_query_is_escaped_not_executed(self):
        r = self.client.get("/search/", {"s": "<script>alert(1)</script>"})
        html = r.content.decode()
        self.assertNotIn("<script>alert(1)</script>", html)  # echoed escaped
        self.assertIn("&lt;script&gt;", html)

    def test_search_page_never_leaks_third_party(self):
        from core.tests import FORBIDDEN
        r = self.client.get("/search/", {"s": "xstrahl"})
        html = r.content.decode()
        for needle in FORBIDDEN:
            self.assertNotIn(needle, html, needle)


class ProgressTests(CatalogBase):
    """POST heartbeats. Access first; numbers second; capped per request."""

    def _grant_and_login(self):
        from tutorials.models import TutorialAccess

        TutorialAccess.objects.create(user=self.approved_with_grant, tutorial=self.published)
        client = self.login(self.approved_with_grant)
        return client

    def test_seconds_are_capped_per_report(self):
        self.published.duration_seconds = 3600
        self.published.save()
        client = self._grant_and_login()
        # a liar claims 10 minutes of watching in one POST...
        r = client.post(reverse("tutorials:progress", args=["radiant-aura-setup"]), {"seconds": "600"})
        self.assertEqual(r.json()["seconds_watched"], 60)  # ...reality moves 60s
        r = client.post(reverse("tutorials:progress", args=["radiant-aura-setup"]), {"seconds": "600"})
        self.assertEqual(r.json()["seconds_watched"], 120)

    def test_completion_marks_completed_and_audits_not(self):
        from tutorials.models import TutorialProgress

        self.published.duration_seconds = 1000
        self.published.save()
        client = self._grant_and_login()
        # 900 of 1000 watched = 90% -> completed (industry threshold)
        for _ in range(15):
            client.post(reverse("tutorials:progress", args=["radiant-aura-setup"]), {"seconds": "60"})
        progress = TutorialProgress.objects.get(user=self.approved_with_grant, tutorial=self.published)
        self.assertTrue(progress.completed)
        self.assertIsNotNone(progress.completed_at)
        self.assertEqual(progress.percent, 90)

    def test_bad_payload_is_400(self):
        client = self._grant_and_login()
        r = client.post(reverse("tutorials:progress", args=["radiant-aura-setup"]), {"seconds": "abc"})
        self.assertEqual(r.status_code, 400)
        r = client.post(reverse("tutorials:progress", args=["radiant-aura-setup"]), {"seconds": "-5"})
        self.assertEqual(r.status_code, 400)

    def test_access_required_before_numbers(self):
        client = self.login(self.approved_no_grant)
        r = client.post(reverse("tutorials:progress", args=["radiant-aura-setup"]), {"seconds": "600"})
        self.assertEqual(r.status_code, 403)
        from tutorials.models import TutorialProgress

        self.assertFalse(TutorialProgress.objects.filter(user=self.approved_no_grant).exists())

    def test_pending_user_reporting_is_probably_denied(self):
        client = self.login(self.pending)
        r = client.post(reverse("tutorials:progress", args=["radiant-aura-setup"]), {"seconds": "60"})
        self.assertEqual(r.status_code, 403)

    def test_revocation_stops_reporting_mid_watch(self):
        client = self._grant_and_login()
        self.assertEqual(client.post(reverse("tutorials:progress", args=["radiant-aura-setup"]), {"seconds": "60"}).status_code, 200)
        from tutorials.models import TutorialAccess

        TutorialAccess.objects.get(user=self.approved_with_grant).delete()
        r = client.post(reverse("tutorials:progress", args=["radiant-aura-setup"]), {"seconds": "60"})
        self.assertEqual(r.status_code, 403)

    def test_get_rejected(self):
        client = self._grant_and_login()
        self.assertEqual(client.get(reverse("tutorials:progress", args=["radiant-aura-setup"])).status_code, 405)

    def test_csrf_required(self):
        client = self._grant_and_login()
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.approved_with_grant)
        r = strict.post(reverse("tutorials:progress", args=["radiant-aura-setup"]), {"seconds": "60"})
        self.assertEqual(r.status_code, 403)

    def test_progress_never_widens_access(self):
        client = self._grant_and_login()
        client.post(reverse("tutorials:progress", args=["radiant-aura-setup"]), {"seconds": "60"})
        from tutorials.models import TutorialAccess

        TutorialAccess.objects.get(user=self.approved_with_grant).delete()
        # 100% watched but access revoked: detail page denies again
        self.assertEqual(client.get(reverse("tutorials:detail", args=["radiant-aura-setup"])).status_code, 403)


class CategoryPage(CatalogBase):
    def test_published_only_listed_with_access_flags(self):
        self.unpublished.category = self.category  # unpublished, must not leak
        self.unpublished.save()
        client = self.login(self.approved_with_grant)
        r = client.get(reverse("tutorials:category", args=["basic-operation"]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Radiant Aura setup")
        self.assertNotContains(r, "Draft internals")

    def test_unknown_category_404(self):
        self.assertEqual(self.login(self.approved_with_grant).get(
            reverse("tutorials:category", args=["nope"])).status_code, 404)


class PlayerWiring(CatalogBase):
    def test_detail_carries_authorize_and_progress_urls(self):
        client = self.login(self.approved_with_grant)
        from tutorials.models import TutorialAccess

        TutorialAccess.objects.create(user=self.approved_with_grant, tutorial=self.published)
        r = client.get(reverse("tutorials:detail", args=["radiant-aura-setup"]))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn(f'data-authorize-url="{reverse("tutorials:authorize", args=["radiant-aura-setup"])}"', html)
        self.assertIn(f'data-progress-url="{reverse("tutorials:progress", args=["radiant-aura-setup"])}"', html)
        self.assertIn("csrfmiddlewaretoken", html)

    def test_denied_page_has_no_player_wiring(self):
        client = self.login(self.approved_no_grant)
        r = client.get(reverse("tutorials:detail", args=["radiant-aura-setup"]))
        self.assertEqual(r.status_code, 403)
        self.assertNotIn("data-authorize-url", r.content.decode())
