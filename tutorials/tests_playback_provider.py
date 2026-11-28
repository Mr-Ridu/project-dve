"""Phase 6 tests: provider selection + the redemption flow.

Bunny Stream was removed from this build, so the provider list is YouTube and
the development-only plain URL. Signing was never our code's job for YouTube —
the important assertions are that the reference is parsed strictly and that the
embed is privacy-enhanced.
"""
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .tests_catalog import CatalogBase
from tutorials.models import Tutorial, TutorialAccess


class ProviderChoices(TestCase):
    """The dashboard can only offer providers the model actually declares."""

    def test_youtube_is_a_selectable_provider(self):
        self.assertIn("youtube", dict(Tutorial.VideoProvider.choices))

    def test_bunny_is_gone(self):
        self.assertNotIn("bunny", dict(Tutorial.VideoProvider.choices))

    def test_video_ref_help_text_points_at_the_video_id(self):
        field = Tutorial._meta.get_field("video_ref")
        self.assertIn("video id", field.help_text)


class YouTubeIdParsing(TestCase):
    """One reference field accepts an id or any of YouTube's link shapes."""

    def test_accepts_common_link_shapes(self):
        from tutorials.providers import youtube

        cases = {
            "dQw4w9WgXcQ": "dQw4w9WgXcQ",
            "  dQw4w9WgXcQ  ": "dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ?si=ncucEF22YU7iLOi8": "dQw4w9WgXcQ",
            "youtu.be/dQw4w9WgXcQ": "dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s": "dQw4w9WgXcQ",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ": "dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ": "dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ": "dQw4w9WgXcQ",
            "https://www.youtube.com/live/dQw4w9WgXcQ": "dQw4w9WgXcQ",
        }
        for ref, expected in cases.items():
            with self.subTest(ref=ref):
                self.assertEqual(youtube.video_id(ref), expected)

    def test_rejects_anything_that_is_not_a_video(self):
        from tutorials.providers import youtube

        for ref in [
            "",
            "   ",
            "not-an-id",
            "https://www.youtube.com/@TechnoMateTechnologies",
            "https://www.youtube.com/playlist?list=PL123",
            "https://vimeo.com/12345",
            "https://cdn.example.com/master.m3u8",
        ]:
            with self.subTest(ref=ref):
                self.assertIsNone(youtube.video_id(ref))

    def test_embed_url_is_privacy_enhanced(self):
        from tutorials.providers import youtube

        url = youtube.embed_url("dQw4w9WgXcQ")
        self.assertTrue(url.startswith("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?"))
        self.assertNotIn("//www.youtube.com", url)  # cooking-setting domain avoided
        for flag in ("rel=0", "modestbranding=1", "iv_load_policy=3", "playsinline=1"):
            self.assertIn(flag, url)


@override_settings(TUTORIALS_REQUIRE_GRANTS=True)
class YouTubeRedemption(CatalogBase):
    def setUp(self):
        super().setUp()
        Tutorial.objects.filter(slug="radiant-aura-setup").update(
            video_provider="youtube", video_ref="https://youtu.be/dQw4w9WgXcQ?si=abc"
        )

    def _redeem_for_granted_user(self):
        TutorialAccess.objects.create(user=self.approved_with_grant, tutorial=self.published)
        client = self.login(self.approved_with_grant)
        token = client.post(
            reverse("tutorials:authorize", args=["radiant-aura-setup"])
        ).json()["token"]
        return client.post(reverse("tutorials:redeem"), {"token": token})

    def test_redeem_returns_unlisted_embed(self):
        response = self._redeem_for_granted_user()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["provider"], "youtube")
        self.assertTrue(
            body["embed_url"].startswith("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?")
        )

    def test_reference_without_a_video_id_is_503(self):
        Tutorial.objects.filter(slug="radiant-aura-setup").update(
            video_ref="https://www.youtube.com/@TechnoMateTechnologies"
        )
        response = self._redeem_for_granted_user()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "provider_not_configured")

    def test_ungranted_user_never_reaches_redemption(self):
        client = self.login(self.approved_with_grant)
        self.assertEqual(
            client.post(reverse("tutorials:authorize", args=["radiant-aura-setup"])).status_code,
            403,
        )


@override_settings(TUTORIALS_REQUIRE_GRANTS=True)
class RedemptionFlow(CatalogBase):
    def setUp(self):
        super().setUp()
        Tutorial.objects.filter(slug="radiant-aura-setup").update(
            video_provider="url", video_ref="https://cdn.example.com/dev/master.m3u8"
        )

    def _authorize(self, client):
        return client.post(reverse("tutorials:authorize", args=["radiant-aura-setup"]))

    def _redeem(self, client, token):
        return client.post(reverse("tutorials:redeem"), {"token": token})

    def test_dev_url_provider_redeems_to_stored_url(self):
        TutorialAccess.objects.create(user=self.approved_with_grant, tutorial=self.published)
        client = self.login(self.approved_with_grant)
        body = self._authorize(client).json()
        response = self._redeem(client, body["token"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["url"], "https://cdn.example.com/dev/master.m3u8")

    def test_token_is_one_time(self):
        TutorialAccess.objects.create(user=self.approved_with_grant, tutorial=self.published)
        client = self.login(self.approved_with_grant)
        token = self._authorize(client).json()["token"]
        self.assertEqual(self._redeem(client, token).status_code, 200)
        self.assertEqual(self._redeem(client, token).status_code, 403)

    def test_garbage_token_403(self):
        client = self.login(self.approved_with_grant)
        self.assertEqual(self._redeem(client, "not-a-real-token").status_code, 403)

    def test_tutorial_without_a_provider_returns_503(self):
        from tutorials.models import Tutorial as T

        T.objects.filter(slug="radiant-aura-setup").update(
            video_provider="none", video_ref=""
        )
        TutorialAccess.objects.create(user=self.approved_with_grant, tutorial=self.published)
        client = self.login(self.approved_with_grant)
        token = self._authorize(client).json()["token"]
        response = self._redeem(client, token)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "provider_not_configured")

    def test_revocation_between_authorize_and_redeem_wins(self):
        TutorialAccess.objects.create(user=self.approved_with_grant, tutorial=self.published)
        client = self.login(self.approved_with_grant)
        token = self._authorize(client).json()["token"]
        TutorialAccess.objects.get(user=self.approved_with_grant).delete()
        response = self._redeem(client, token)
        self.assertEqual(response.status_code, 403)
        # even a later re-grant can't resurrect the burned token
        TutorialAccess.objects.create(user=self.approved_with_grant, tutorial=self.published)
        self.assertEqual(self._redeem(client, token).status_code, 403)

    def test_redeem_requires_csrf(self):
        TutorialAccess.objects.create(user=self.approved_with_grant, tutorial=self.published)
        strict = self.login(self.approved_with_grant)
        strict.post(
            reverse("tutorials:authorize", args=["radiant-aura-setup"]),
            enforce_csrf_checks=True,
        )
        strict_csrf_client = Client(enforce_csrf_checks=True)
        strict_csrf_client.force_login(self.approved_with_grant)
        response = strict_csrf_client.post(reverse("tutorials:redeem"), {"token": "x"})
        self.assertEqual(response.status_code, 403)
