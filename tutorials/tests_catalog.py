"""Phase 5 security tests: opinionated permission matrix.

Covers the Phase 1 §6 rule end to end: published/unpublished ×
approved/pending/rejected/anonymous × grant/access_all/revoked, slug
tampering, progress-never-authorizes, and the playback endpoint
(method/CSRF/authorization semantics).
"""
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import AuditEvent, User
from tutorials.models import Category, Tutorial, TutorialAccess, TutorialProgress


def make_user(username, *, status, **kw):
    u = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="Sup3r-strong-pass!",
        approval_status=status,
        **kw,
    )
    return u


class CatalogBase(TestCase):
    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(name="Basic operation", slug="basic-operation")
        self.published = Tutorial.objects.create(
            title="Radiant Aura setup",
            slug="radiant-aura-setup",
            description="Getting started.",
            category=self.category,
            estimated_minutes=12,
            is_published=True,
        )
        self.unpublished = Tutorial.objects.create(
            title="Draft internals",
            slug="draft-internals",
            is_published=False,
        )
        self.approved_with_grant = make_user("granted", status=User.ApprovalStatus.APPROVED)
        self.approved_no_grant = make_user("no_grant", status=User.ApprovalStatus.APPROVED)
        self.approved_all = make_user(
            "all_access", status=User.ApprovalStatus.APPROVED, access_all_tutorials=True
        )
        self.pending = make_user("pending", status=User.ApprovalStatus.PENDING)
        self.rejected = make_user("rejected", status=User.ApprovalStatus.REJECTED)

    def login(self, user):
        c = Client()
        c.force_login(user)
        return c


class AccessMatrix(CatalogBase):
    def test_published_detail_for_appropriate_users(self):
        TutorialAccess.objects.create(user=self.approved_with_grant, tutorial=self.published)
        cases = [
            (self.approved_with_grant, 200),
            (self.approved_all, 200),
        ]
        for user, expected in cases:
            with self.subTest(user=user.username, status=expected):
                response = self.login(user).get(reverse("tutorials:detail", args=["radiant-aura-setup"]))
                self.assertEqual(response.status_code, expected)

    def test_published_detail_denied_soft_without_access(self):
        TutorialAccess.objects.create(user=self.approved_with_grant, tutorial=self.published)
        cases = {
            self.approved_no_grant: 403,   # signed in, grantless → explained denial
            self.pending: 403,             # pending → explained denial
            self.rejected: 403,            # rejected → explained denial
        }
        for user, expected in cases.items():
            with self.subTest(user=user.username, status=expected):
                response = self.login(user).get(reverse("tutorials:detail", args=["radiant-aura-setup"]))
                self.assertEqual(response.status_code, expected)
                self.assertContains(response, "Tutorial unavailable", status_code=expected)

    def test_anonymous_detail_redirects_to_login(self):
        response = Client().get(reverse("tutorials:detail", args=["radiant-aura-setup"]))
        self.assertRedirects(response, reverse("accounts:login"))

    def test_unpublished_is_hard_404_for_everyone(self):
        TutorialAccess.objects.create(user=self.approved_with_grant, tutorial=self.unpublished)
        users = [
            None,
            self.approved_with_grant,
            self.approved_all,
            self.pending,
            self.rejected,
        ]
        for user in users:
            with self.subTest(user=user.username if user else "anonymous"):
                client = self.login(user) if user else Client()
                response = client.get(reverse("tutorials:detail", args=["draft-internals"]))
                self.assertEqual(response.status_code, 404)

    def test_slug_tampering_404s(self):
        client = self.login(self.approved_all)
        for bogus in ["radiant-aura-setu", "RADIANT-AURA-SETUP", "radiant-aura-setup-x"]:
            with self.subTest(slug=bogus):
                response = client.get(reverse("tutorials:detail", args=[bogus]))
                self.assertEqual(response.status_code, 404)

    def test_slug_path_traversal_never_reaches_the_view(self):
        """The slug path converter itself rejects / and dots — no traversal."""
        client = self.login(self.approved_all)
        for bogus in ["/../..", "..%2F..%2F", "x/../y"]:
            with self.subTest(bogus=bogus):
                response = client.get(f"/tutorials/{bogus}/")
                self.assertEqual(response.status_code, 404)

    def test_revocation_denies_next_request(self):
        client = self.login(self.approved_with_grant)
        grant = TutorialAccess.objects.create(user=self.approved_with_grant, tutorial=self.published)
        self.assertEqual(client.get(reverse("tutorials:detail", args=["radiant-aura-setup"])).status_code, 200)
        grant.delete()  # revocation = deleting the grant row
        self.assertEqual(client.get(reverse("tutorials:detail", args=["radiant-aura-setup"])).status_code, 403)

    def test_progress_never_widens_access(self):
        TutorialProgress.objects.create(user=self.approved_no_grant, tutorial=self.published, percent=100, completed=True)
        client = self.login(self.approved_no_grant)
        self.assertEqual(client.get(reverse("tutorials:detail", args=["radiant-aura-setup"])).status_code, 403)

    def test_pending_user_may_log_in_but_sees_pending_state(self):
        client = self.login(self.pending)
        response = client.get(reverse("accounts:pending"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not")

    def test_list_only_shows_published(self):
        client = self.login(self.approved_with_grant)
        response = client.get(reverse("tutorials:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Radiant Aura setup")
        self.assertNotContains(response, "Draft internals")


class PlaybackEndpoint(CatalogBase):
    def grant(self, user, tutorial):
        TutorialAccess.objects.create(user=user, tutorial=tutorial)

    def test_get_method_rejected(self):
        self.grant(self.approved_with_grant, self.published)
        response = self.login(self.approved_with_grant).get(
            reverse("tutorials:authorize", args=["radiant-aura-setup"])
        )
        self.assertEqual(response.status_code, 405)

    def test_authorized_post_returns_short_lived_token(self):
        self.grant(self.approved_with_grant, self.published)
        response = self.login(self.approved_with_grant).post(
            reverse("tutorials:authorize", args=["radiant-aura-setup"])
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIn("token", body)
        self.assertEqual(body["expires_in"], 300)
        # token actually stored server-side
        self.assertIsNotNone(cache.get(f"play_token:{body['token']}"))

    def test_all_access_flag_authorizes_too(self):
        response = self.login(self.approved_all).post(
            reverse("tutorials:authorize", args=["radiant-aura-setup"])
        )
        self.assertEqual(response.status_code, 201)

    def test_unauthorized_post_403_json(self):
        response = self.login(self.approved_no_grant).post(
            reverse("tutorials:authorize", args=["radiant-aura-setup"])
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "not_authorized")

    def test_pending_rejected_anonymous_denied(self):
        self.grant(self.pending, self.published)  # grant alone is not enough
        for user in (self.pending, self.rejected):
            with self.subTest(user=user.username):
                response = self.login(user).post(
                    reverse("tutorials:authorize", args=["radiant-aura-setup"])
                )
                self.assertEqual(response.status_code, 403)
        response = Client().post(reverse("tutorials:authorize", args=["radiant-aura-setup"]))
        self.assertEqual(response.status_code, 403)

    def test_revocation_blocks_new_token(self):
        self.grant(self.approved_with_grant, self.published)
        client = self.login(self.approved_with_grant)
        self.assertEqual(
            client.post(reverse("tutorials:authorize", args=["radiant-aura-setup"])).status_code, 201
        )
        TutorialAccess.objects.get(user=self.approved_with_grant).delete()
        self.assertEqual(
            client.post(reverse("tutorials:authorize", args=["radiant-aura-setup"])).status_code, 403
        )

    def test_csrf_enforced_on_authorize(self):
        self.grant(self.approved_with_grant, self.published)
        strict_client = Client(enforce_csrf_checks=True)
        strict_client.force_login(self.approved_with_grant)
        response = strict_client.post(reverse("tutorials:authorize", args=["radiant-aura-setup"]))
        self.assertEqual(response.status_code, 403)

    def test_token_never_leaks_video(self):
        """Provider reference must not travel in the response payload."""
        self.grant(self.approved_with_grant, self.published)
        response = self.login(self.approved_with_grant).post(
            reverse("tutorials:authorize", args=["radiant-aura-setup"])
        )
        body = response.json()
        self.assertNotIn("video_ref", body)
        self.assertEqual(body["provider"], "none")

    def test_published_user_audit_independence(self):
        """Approval predicate points at the User model, cached audit stays inert."""
        events = AuditEvent.objects.count()
        self.login(self.approved_no_grant).get(reverse("tutorials:list"))
        self.assertEqual(AuditEvent.objects.count(), events)  # reads never audit-spam

    def test_anonymous_list_renders_with_sign_in_hint(self):
        """The catalog itself is public-facing; only opening a tutorial redirects."""
        response = Client().get(reverse("tutorials:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in")
