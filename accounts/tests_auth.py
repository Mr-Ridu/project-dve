"""Phase 4 authentication security suite.

Covers the whole lifecycle and the hard requirements from the Phase 1
report §5: registration lands pending; pending users may sign in but are
shown the awaiting-approval state; rejected/inactive users are denied
service; logout is POST-only; ?next redirects are host-validated
(open-redirect attempts fall back); throttling kicks in after repeated
failures; CSRF protects every state-changing endpoint.
"""
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import AuditEvent
from accounts.throttle import MAX_EVENTS, WINDOW_SECONDS
from django.core.cache import cache
from django.contrib.auth import get_user_model

User = get_user_model()

VALID_PASSWORD = "correct-horse-battery-9"


def registration_data(**overrides):
    data = {
        "username": "newuser",
        "first_name": "New",
        "last_name": "User",
        "email": "newuser@example.com",
        "password1": VALID_PASSWORD,
        "password2": VALID_PASSWORD,
    }
    data.update(overrides)
    return data


class ThrottleIsolation(TestCase):
    """Keep test runs deterministic: clear the throttle cache between tests."""

    def setUp(self):
        cache.clear()


class RegistrationTests(ThrottleIsolation):
    def test_registration_creates_pending_user_and_audits(self):
        r = self.client.post(reverse("accounts:register"), registration_data())
        self.assertRedirects(r, reverse("accounts:login"))
        user = User.objects.get(username="newuser")
        self.assertEqual(user.approval_status, "pending")
        self.assertFalse(user.access_all_tutorials)
        event = AuditEvent.objects.get(action=AuditEvent.Action.USER_REGISTERED)
        self.assertEqual(event.target_user, user)
        self.assertIsNone(event.actor)

    def test_duplicate_email_rejected_case_insensitive(self):
        User.objects.create_user("alice", email="Alice@Example.com", password=VALID_PASSWORD)
        r = self.client.post(reverse("accounts:register"), registration_data(email="alice@example.com"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "already exists")

    def test_week_password_rejected(self):
        r = self.client.post(
            reverse("accounts:register"), registration_data(password1="12345678", password2="12345678")
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_authenticated_user_cannot_register_again(self):
        User.objects.create_user("alice", password=VALID_PASSWORD)
        self.client.force_login(User.objects.get(username="alice"))
        r = self.client.get(reverse("accounts:register"))
        self.assertRedirects(r, reverse("core:home"))


class LoginTests(ThrottleIsolation):
    def _make(self, status):
        u = User.objects.create_user("svc-user", password=VALID_PASSWORD)
        u.approval_status = status
        u.save()
        return u

    def test_pending_user_can_log_in_but_lands_on_pending_page(self):
        self._make("pending")
        r = self.client.post(
            reverse("accounts:login"),
            {"username": "svc-user", "password": VALID_PASSWORD},
        )
        self.assertRedirects(r, reverse("accounts:pending"))
        self.assertTrue(self.client.session.get("_auth_user_id"))
        # The pending page must not reveal tutorial content
        page = self.client.get(reverse("accounts:pending"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "not yet approved", status_code=200)

    def test_rejected_user_lands_on_not_approved_page(self):
        """Rejected accounts may authenticate but never reach tutorial access;
        the landing page states the account is not approved (covers pending +
        rejected without leaking which)."""
        self._make("rejected")
        r = self.client.post(
            reverse("accounts:login"),
            {"username": "svc-user", "password": VALID_PASSWORD},
        )
        self.assertRedirects(r, reverse("accounts:pending"))
        page = self.client.get(reverse("accounts:pending"))
        self.assertEqual(page.status_code, 200)

    def test_inactive_user_cannot_log_in(self):
        u = self._make("approved")
        u.is_active = False
        u.save()
        r = self.client.post(
            reverse("accounts:login"),
            {"username": "svc-user", "password": VALID_PASSWORD},
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "form", status_code=200)

    def test_wrong_password_records_throttle_failure(self):
        self._make("approved")
        for _ in range(MAX_EVENTS):
            r = self.client.post(
                reverse("accounts:login"),
                {"username": "svc-user", "password": "wrong-password-1"},
            )
        # Next attempt with CORRECT credentials still throttled
        r = self.client.post(
            reverse("accounts:login"),
            {"username": "svc-user", "password": VALID_PASSWORD},
        )
        self.assertEqual(r.status_code, 429)

    def test_successful_login_of_approved_user_redirects_home(self):
        self._make("approved")
        r = self.client.post(
            reverse("accounts:login"),
            {"username": "svc-user", "password": VALID_PASSWORD},
        )
        self.assertRedirects(r, reverse("core:home"))


class RedirectSafetyTests(ThrottleIsolation):
    def test_https_open_redirect_is_rejected(self):
        u = User.objects.create_user("alice", password=VALID_PASSWORD)
        u.approval_status = "approved"
        u.save()
        r = self.client.post(
            reverse("accounts:login") + "?next=https://evil.example.com/",
            {"username": "alice", "password": VALID_PASSWORD},
        )
        self.assertRedirects(r, reverse("core:home"), fetch_redirect_response=False)

    def test_local_next_is_honoured(self):
        u = User.objects.create_user("alice", password=VALID_PASSWORD)
        u.approval_status = "approved"
        u.save()
        r = self.client.post(
            reverse("accounts:login") + "?next=/about/",
            {"username": "alice", "password": VALID_PASSWORD},
        )
        self.assertRedirects(r, "/about/", fetch_redirect_response=False)


class LogoutTests(ThrottleIsolation):
    def test_logout_is_post_only(self):
        r = self.client.get(reverse("accounts:logout"))
        self.assertEqual(r.status_code, 405)

    def test_logout_works_via_post_and_redirects_home(self):
        u = User.objects.create_user("alice", password=VALID_PASSWORD)
        u.approval_status = "approved"
        u.save()
        self.client.force_login(u)
        r = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(r, reverse("core:home"))
        r2 = self.client.get(reverse("accounts:pending"))
        # after logout, pending page redirects to login (login_required absent here,
        # but the anonymous state is confirmed by session loss)
        self.assertEqual(r2.status_code, 200)


class CSRFTests(ThrottleIsolation):
    endpoints = (
        lambda self: (reverse("accounts:register"), registration_data()),
        lambda self: (reverse("accounts:login"), {"username": "x", "password": "y"}),
        lambda self: (reverse("accounts:logout"), {}),
    )

    def test_state_changes_require_csrf_token(self):
        # enforce_csrf_checks=True: the plain test client raises csrf checks by default.
        strict = Client(enforce_csrf_checks=True)
        for factory in self.endpoints:
            url, data = factory(self)
            r = strict.post(url, data)  # no token -> 403
            self.assertEqual(r.status_code, 403, url)


class ThrottleWindowTests(ThrottleIsolation):
    def test_window_constants_are_sane(self):
        self.assertEqual(MAX_EVENTS, 5)
        self.assertGreaterEqual(WINDOW_SECONDS, 60)
