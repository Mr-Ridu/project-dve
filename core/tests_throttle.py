"""Rate limiting (core.throttle): brakes on the abuse-prone endpoints.

Limits are settings-driven so tests can shrink them. Every test starts from a
cleared cache because the counters live there (same convention as the
dashboard/catalog test bases).
"""
import urllib.error

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from tutorials.models import Tutorial

from .throttle import record, too_many

TINY = {
    "playback": (3, 60),
    "progress": (3, 60),
    "forms": (2, 60),
    "search": (2, 60),
    "upload": (2, 60),
}


class ThrottleUnit(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(RATE_LIMITS={"playback": (3, 60)})
    def test_counts_up_to_the_limit_then_blocks(self):
        for i in range(3):
            self.assertFalse(too_many("playback", "127.0.0.1", "user:1"), i)
            record("playback", "127.0.0.1", "user:1")
        self.assertTrue(too_many("playback", "127.0.0.1", "user:1"))

    @override_settings(RATE_LIMITS={"playback": (3, 60)})
    def test_accounts_and_ips_are_counted_separately(self):
        for _ in range(3):
            record("playback", "127.0.0.1", "user:1")
        self.assertFalse(too_many("playback", "127.0.0.1", "user:2"))
        self.assertFalse(too_many("playback", "10.0.0.9", "user:1"))

    @override_settings(RATE_LIMITS={"playback": (3, 60)})
    def test_scopes_are_independent(self):
        for _ in range(3):
            record("playback", "127.0.0.1", "user:1")
        self.assertFalse(too_many("progress", "127.0.0.1", "user:1"))


class PlaybackThrottle(TestCase):
    """authorize/redeem answer 429 JSON once hammered."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="viewer", email="viewer@example.com",
            password="Sup3r-strong-pass!", approval_status="approved",
        )
        self.tutorial = Tutorial.objects.create(
            title="T", slug="t", is_published=True, video_provider="url",
            video_ref="https://cdn.example.com/v.mp4",
        )
        from tutorials.models import TutorialAccess

        TutorialAccess.objects.create(user=self.user, tutorial=self.tutorial)
        self.client = Client()
        self.client.force_login(self.user)

    @override_settings(RATE_LIMITS=TINY)
    def test_authorize_429_json_after_the_limit(self):
        url = reverse("tutorials:authorize", args=["t"])
        for _ in range(3):
            self.assertEqual(self.client.post(url).status_code, 201)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "rate_limited")

    @override_settings(RATE_LIMITS=TINY)
    def test_redeem_shares_the_playback_budget(self):
        for _ in range(3):
            self.client.post(reverse("tutorials:authorize", args=["t"]))
        response = self.client.post(reverse("tutorials:redeem"), {"token": "x"})
        self.assertEqual(response.status_code, 429)

    @override_settings(RATE_LIMITS=TINY)
    def test_limit_is_per_account(self):
        url = reverse("tutorials:authorize", args=["t"])
        for _ in range(3):
            self.client.post(url)
        self.assertEqual(self.client.post(url).status_code, 429)
        other = User.objects.create_user(
            username="viewer2", email="v2@example.com",
            password="Sup3r-strong-pass!", approval_status="approved",
        )
        from tutorials.models import TutorialAccess

        TutorialAccess.objects.create(user=other, tutorial=self.tutorial)
        second = Client()
        second.force_login(other)
        self.assertEqual(second.post(url).status_code, 201)  # unaffected

    @override_settings(RATE_LIMITS=TINY)
    def test_progress_429_when_hammered(self):
        url = reverse("tutorials:progress", args=["t"])
        for _ in range(3):
            self.client.post(url, {"seconds": "5"})
        response = self.client.post(url, {"seconds": "5"})
        self.assertEqual(response.status_code, 429)


class PublicEndpointThrottle(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    @override_settings(RATE_LIMITS=TINY)
    def test_form_stub_429_page(self):
        url = reverse("core:form-placeholder")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Too many requests", status_code=429)

    @override_settings(RATE_LIMITS=TINY)
    def test_search_429_when_hammered(self):
        url = reverse("core:search")
        for _ in range(2):
            self.client.get(url, {"s": "x"})
        self.assertEqual(self.client.get(url, {"s": "x"}).status_code, 429)

    @override_settings(RATE_LIMITS=TINY)
    def test_rate_limited_page_never_reveals_secrets(self):
        url = reverse("core:form-placeholder")
        for _ in range(3):
            response = self.client.get(url)
        body = response.content.decode()
        self.assertEqual(response.status_code, 429)
        for marker in ("BUNNY", "SECRET_KEY", "Traceback", "File \""):
            self.assertNotIn(marker, body)


class UploadThrottle(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_user(
            username="staffer", email="s@example.com",
            password="Sup3r-strong-pass!", approval_status="approved", is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.staff)

    @override_settings(RATE_LIMITS=TINY)
    def test_dashboard_saves_are_rate_limited(self):
        url = reverse("dashboard:tutorial_create")
        payload = {
            "title": "T1", "description": "", "video_provider": "none",
            "video_ref": "", "ordering": "0", "duration_seconds": "0",
            "estimated_minutes": "0",
        }
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.assertEqual(self.client.post(url, {**payload, "title": "T2"}).status_code, 302)
        response = self.client.post(url, {**payload, "title": "T3"})
        self.assertEqual(response.status_code, 429)
        self.assertFalse(Tutorial.objects.filter(title="T3").exists())  # view never ran


class ErrorPathsLeakNothing(TestCase):
    """Credentials must not survive into any error a staff member sees."""

    def test_upload_error_contains_no_key_material(self):
        from unittest import mock

        from django.core.files.uploadedfile import SimpleUploadedFile

        from tutorials.providers import bunny_upload

        sentinel = "SENTINEL-MGMT-KEY"
        with override_settings(BUNNY_STREAM_API_KEY=sentinel, BUNNY_STREAM_LIBRARY_ID="759"):
            with mock.patch(
                "urllib.request.urlopen",
                side_effect=urllib.error.HTTPError(
                    "https://video.bunnycdn.com/x", 401, "Unauthorized", {}, None
                ),
            ):
                with self.assertRaises(bunny_upload.UploadError) as ctx:
                    bunny_upload.upload_file(
                        SimpleUploadedFile("t.mp4", b"x"), title="T"
                    )
        message = str(ctx.exception)
        self.assertIn("401", message)          # the operator learns what failed
        self.assertNotIn(sentinel, message)    # but never the credential
