"""Post-handover UX tests: admin registrations, navigation, demo content.

These cover the gaps a person hits immediately when they open the project for the
first time: an admin with no tutorial models, no link to the library or the
sign-in page anywhere in the site, a superuser that cannot open a tutorial, and
an empty catalog that looks broken.
"""
import io

from django.contrib import admin
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import AuditEvent, User
from tutorials.models import Category, Tutorial, TutorialAccess, TutorialProgress


class AdminRegistrationTests(TestCase):
    def test_tutorial_models_are_registered(self):
        for model in (Category, Tutorial, TutorialAccess, TutorialProgress):
            self.assertIn(model, admin.site._registry, f"{model.__name__} missing from admin")

    def test_audit_events_are_visible_and_read_only(self):
        self.assertIn(AuditEvent, admin.site._registry)
        model_admin = admin.site._registry[AuditEvent]
        self.assertFalse(model_admin.has_add_permission(request=None))
        self.assertFalse(model_admin.has_change_permission(request=None))

    def test_admin_index_loads_for_superuser(self):
        user = User.objects.create_superuser("admin_probe", "admin@example.invalid", "Zx7!quiet-Harbor-92")
        self.client.force_login(user)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Tutorials", html)
        self.assertIn("Categories", html)


class SuperuserApprovalTests(TestCase):
    def test_new_superuser_is_approved(self):
        user = User.objects.create_superuser("super_probe", "s@example.invalid", "Zx7!quiet-Harbor-92")
        user.refresh_from_db()
        self.assertEqual(user.approval_status, User.ApprovalStatus.APPROVED)
        self.assertIsNotNone(user.approved_at)
        self.assertTrue(user.is_approved())

    def test_ordinary_user_still_starts_pending(self):
        user = User.objects.create_user("plain_probe", "p@example.invalid", "Zx7!quiet-Harbor-92")
        self.assertEqual(user.approval_status, User.ApprovalStatus.PENDING)
        self.assertFalse(user.is_approved())


class UtilityBarTests(TestCase):
    def test_anonymous_sees_library_and_sign_in(self):
        html = self.client.get("/").content.decode()
        self.assertIn("Tutorial library", html)
        self.assertIn(reverse("tutorials:list"), html)
        self.assertIn(reverse("accounts:login"), html)
        self.assertIn(reverse("accounts:register"), html)
        self.assertNotIn("Sign out", html)

    def test_signed_in_user_sees_sign_out_and_username(self):
        user = User.objects.create_user("bar_probe", "b@example.invalid", "Zx7!quiet-Harbor-92")
        self.client.force_login(user)
        html = self.client.get("/").content.decode()
        self.assertIn("bar_probe", html)
        self.assertIn("Sign out", html)
        self.assertIn(reverse("accounts:logout"), html)
        self.assertNotIn("Staff dashboard", html)

    def test_staff_sees_dashboard_link(self):
        staff = User.objects.create_user(
            "bar_staff", "bs@example.invalid", "Zx7!quiet-Harbor-92", is_staff=True
        )
        self.client.force_login(staff)
        html = self.client.get("/").content.decode()
        self.assertIn(reverse("dashboard:overview"), html)

    def test_library_is_reachable_from_the_home_page(self):
        response = self.client.get(reverse("tutorials:list"))
        self.assertEqual(response.status_code, 200)


@override_settings(DEBUG=True)
class SeedDemoTests(TestCase):
    def test_creates_published_tutorial_and_grants_it(self):
        user = User.objects.create_user("seed_probe", "seed@example.invalid", "Zx7!quiet-Harbor-92")
        call_command("seed_demo", username="seed_probe", stdout=io.StringIO())

        tutorial = Tutorial.objects.get(slug="welcome-tour")
        self.assertTrue(tutorial.is_published)
        self.assertEqual(tutorial.video_provider, Tutorial.VideoProvider.URL)
        self.assertTrue(tutorial.video_ref)

        user.refresh_from_db()
        self.assertEqual(user.approval_status, User.ApprovalStatus.APPROVED)
        self.assertTrue(TutorialAccess.objects.filter(user=user, tutorial=tutorial).exists())

        # Idempotent: a second run must not duplicate anything.
        call_command("seed_demo", username="seed_probe", stdout=io.StringIO())
        self.assertEqual(Tutorial.objects.filter(slug="welcome-tour").count(), 1)
        self.assertEqual(TutorialAccess.objects.filter(user=user).count(), 1)

    @override_settings(DEBUG=False)
    def test_refuses_to_run_in_production(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo", stdout=io.StringIO())
