"""Phase 6 tests: Bunny signing math + the redemption flow.

Signing is verified against the documented algorithms (sha256 hex for embeds,
HMAC-SHA256 for CDN), computed independently in the test, not by comparing to
our own implementation — plus end-to-end redemption tests through views.
"""
import hashlib
import hmac as hmac_mod
from base64 import urlsafe_b64encode

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .tests_catalog import CatalogBase
from tutorials.models import Tutorial, TutorialAccess

SECURITY_KEY = "test-security-key"
LIBRARY_ID = "759"


def expected_embed_token(key, video_id, expires):
    return hashlib.sha256(f"{key}{video_id}{expires}".encode()).hexdigest()


class BunnySigning(TestCase):
    def test_embed_token_matches_documented_formula(self):
        from tutorials.providers import bunny

        token = bunny.embed_token(SECURITY_KEY, "32d140e2-4f4e", 1623440202)
        self.assertEqual(token, expected_embed_token(SECURITY_KEY, "32d140e2-4f4e", 1623440202))
        # Independent re-computation with the doc's concatenation order.
        self.assertEqual(
            token,
            hashlib.sha256(SECURITY_KEY.encode() + b"32d140e2-4f4e" + b"1623440202").hexdigest(),
        )

    def test_embed_url_shape(self):
        from tutorials.providers import bunny

        url = bunny.embed_url(LIBRARY_ID, "vid-1", SECURITY_KEY, 1623440202)
        self.assertTrue(url.startswith(f"https://player.mediadelivery.net/embed/{LIBRARY_ID}/vid-1?token="))
        self.assertIn("expires=1623440202", url)
        self.assertIn(expected_embed_token(SECURITY_KEY, "vid-1", 1623440202), url)

    def test_cdn_token_is_documented_hmac(self):
        from tutorials.providers import bunny

        path = "/videos/stream1/"
        expires = 1598024587
        token = bunny.cdn_token(SECURITY_KEY, path, expires)
        self.assertTrue(token.startswith("HS256-"))
        digest = hmac_mod.new(
            SECURITY_KEY.encode(), b"/videos/stream1/1598024587", hashlib.sha256
        ).digest()
        expected = (
            urlsafe_b64encode(digest).decode().replace("+", "-").replace("/", "_").rstrip("=")
        )
        self.assertEqual(token[6:], expected)

    def test_hls_directory_url_embeds_token_in_path(self):
        from tutorials.providers import bunny

        url = bunny.signed_hls_directory_url(
            "myzone.b-cdn.net", "/videos/stream1/", "/videos/stream1/playlist.m3u8", SECURITY_KEY, 1598024587
        )
        self.assertTrue("/bcdn_token=HS256-" in url)
        self.assertIn("expires=1598024587", url)
        self.assertIn("token_path=%2Fvideos%2Fstream1%2F", url)
        self.assertTrue(url.endswith("/videos/stream1/playlist.m3u8"))

    def test_user_ip_signed_but_not_appended(self):
        from tutorials.providers import bunny

        token_with_ip = bunny.cdn_token(SECURITY_KEY, "/videos/", 1000, user_ip="203.0.113.42")
        token_without = bunny.cdn_token(SECURITY_KEY, "/videos/", 1000)
        self.assertNotEqual(token_with_ip, token_without)


class ProviderChoices(TestCase):
    """The dashboard can only offer providers the model actually declares."""

    def test_bunny_is_a_selectable_provider(self):
        self.assertIn("bunny", dict(Tutorial.VideoProvider.choices))

    def test_youtube_is_a_selectable_provider(self):
        self.assertIn("youtube", dict(Tutorial.VideoProvider.choices))

    def test_video_ref_help_text_points_at_the_guid(self):
        field = Tutorial._meta.get_field("video_ref")
        self.assertIn("GUID", field.help_text)


class BunnyUploadClient(TestCase):
    """Dashboard upload calls the documented HTTP API shapes, key never in URLs."""

    def _run(self, fake_call, *, title="Talk", name="talk.mp4", data=b"mp4-bytes"):
        from unittest import mock

        from django.core.files.uploadedfile import SimpleUploadedFile
        from tutorials.providers import bunny_upload

        with override_settings(BUNNY_STREAM_API_KEY="mgmt-key", BUNNY_STREAM_LIBRARY_ID="759"):
            with mock.patch.object(bunny_upload, "_call", side_effect=fake_call):
                guid = bunny_upload.upload_file(
                    SimpleUploadedFile(name, data), title=title
                )
        return guid

    def test_upload_creates_video_then_puts_bytes(self):
        calls = []

        def fake_call(method, url, **kw):
            calls.append((method, url, kw))
            return (201, b'{"guid": "guid-1"}') if method == "POST" else (200, b"")

        self.assertEqual(self._run(fake_call), "guid-1")
        method, url, kw = calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://video.bunnycdn.com/library/759/videos")
        method, url, kw = calls[1]
        self.assertEqual(method, "PUT")
        self.assertEqual(url, "https://video.bunnycdn.com/library/759/videos/guid-1")
        self.assertEqual(kw["content_length"], len(b"mp4-bytes"))
        for _, url, _ in calls:  # credentials travel in headers, never in URLs
            self.assertNotIn("mgmt-key", url)

    def test_failed_byte_upload_deletes_the_orphan(self):
        from tutorials.providers.bunny_upload import UploadError

        calls = []

        def fake_call(method, url, **kw):
            calls.append(method)
            if method == "POST":
                return (201, b'{"guid": "guid-1"}')
            if method == "PUT":
                raise UploadError("Bunny Stream upload failed (HTTP 500).")
            return (200, b"")

        with self.assertRaises(UploadError):
            self._run(fake_call)
        self.assertEqual(calls, ["POST", "PUT", "DELETE"])

    def test_unconfigured_raises_an_actionable_error(self):
        from unittest import mock

        from django.core.files.uploadedfile import SimpleUploadedFile
        from tutorials.providers import bunny_upload

        with override_settings(BUNNY_STREAM_API_KEY=""):
            with mock.patch.object(bunny_upload, "_call") as call:
                with self.assertRaises(bunny_upload.UploadError) as ctx:
                    bunny_upload.upload_file(SimpleUploadedFile("t.mp4", b"x"), title="T")
        call.assert_not_called()  # fails before any network traffic
        self.assertIn("BUNNY_STREAM_API_KEY", str(ctx.exception))


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

    def test_bunny_config_missing_returns_503(self):
        from tutorials.models import Tutorial as T

        T.objects.filter(slug="radiant-aura-setup").update(video_provider="bunny", video_ref="vid-uuid")
        TutorialAccess.objects.create(user=self.approved_with_grant, tutorial=self.published)
        client = self.login(self.approved_with_grant)
        token = self._authorize(client).json()["token"]
        with override_settings(BUNNY_STREAM_SECURITY_KEY="", BUNNY_STREAM_LIBRARY_ID=""):
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

    @override_settings(
        BUNNY_STREAM_SECURITY_KEY="real-key",
        BUNNY_STREAM_LIBRARY_ID="759",
    )
    def test_bunny_provider_redeems_to_signed_embed(self):
        from tutorials.models import Tutorial as T

        T.objects.filter(slug="radiant-aura-setup").update(video_provider="bunny", video_ref="vid-uuid")
        TutorialAccess.objects.create(user=self.approved_with_grant, tutorial=self.published)
        client = self.login(self.approved_with_grant)
        token = self._authorize(client).json()["token"]
        response = self._redeem(client, token)
        self.assertEqual(response.status_code, 200)
        url = response.json()["embed_url"]
        self.assertTrue(url.startswith("https://player.mediadelivery.net/embed/759/vid-uuid?token="))
        self.assertNotIn("real-key", url)  # key never crosses the wire
