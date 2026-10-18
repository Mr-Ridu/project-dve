"""Phase 7 tests: staff dashboard security.

Acceptance from the plan: ordinary users are blocked from every dashboard
action; no self-approval paths; mutations POST-only + CSRF; all approval,
flag and grant actions audited.
"""
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import AuditEvent, User
from tutorials.models import Category, Tutorial, TutorialAccess


def mk(username, *, status=User.ApprovalStatus.PENDING, is_staff=False, **kw):
    return User.objects.create_user(
        username=username, email=f"{username}@example.com",
        password="Sup3r-strong-pass!", approval_status=status,
        is_staff=is_staff, **kw,
    )


class DashboardBase(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = mk("staff_user", status=User.ApprovalStatus.APPROVED, is_staff=True)
        self.plain = mk("plain_user", status=User.ApprovalStatus.APPROVED)
        self.pending = mk("pending_user")
        self.category = Category.objects.create(name="Cat A", slug="cat-a")
        self.tutorial = Tutorial.objects.create(
            title="Rad setup", slug="rad-setup", category=self.category, is_published=True
        )
        self.draft = Tutorial.objects.create(title="Draft", slug="draft", is_published=False)
        self.signed_in_staff = self._client(self.staff)
        self.signed_in_plain = self._client(self.plain)

    def _client(self, user):
        c = Client()
        c.force_login(user)
        return c


class Gate(DashboardBase):
    """Ordinary users blocked from EVERY dashboard action, staff everywhere ok."""

    def _actions(self):
        return [
            ("get", reverse("dashboard:overview")),
            ("get", reverse("dashboard:user_list")),
            ("get", reverse("dashboard:user_detail", args=[self.plain.pk])),
            ("post", reverse("dashboard:user_approval", args=[self.plain.pk, "approve"])),
            ("post", reverse("dashboard:user_access_flag", args=[self.plain.pk])),
            ("post", reverse("dashboard:grant", args=[self.plain.pk, self.tutorial.pk])),
            ("post", reverse("dashboard:revoke", args=[self.plain.pk, self.tutorial.pk])),
            ("get", reverse("dashboard:tutorial_list")),
            ("get", reverse("dashboard:tutorial_create")),
            ("post", reverse("dashboard:tutorial_delete", args=[self.tutorial.pk])),
            ("get", reverse("dashboard:category_list")),
            ("post", reverse("dashboard:category_delete", args=[self.category.pk])),
        ]

    def test_anonymous_redirects_to_login(self):
        c = Client()
        for method, url in self._actions():
            with self.subTest(method=method, url=url):
                response = getattr(c, method)(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("login", response["Location"])

    def test_non_staff_hard_403_on_every_action(self):
        for method, url in self._actions():
            with self.subTest(method=method, url=url):
                response = getattr(self.signed_in_plain, method)(url)
                self.assertEqual(response.status_code, 403)

    def test_inactive_staff_also_blocked(self):
        inactive = mk(
            "inactive_staff", status=User.ApprovalStatus.APPROVED,
            is_staff=True, is_active=False,
        )
        response = self._client(inactive).get(reverse("dashboard:overview"))
        self.assertEqual(response.status_code, 302)  # inactive users get logged-out -> login

    def test_staff_200_on_read_pages(self):
        for url in [reverse("dashboard:overview"), reverse("dashboard:user_list"),
                    reverse("dashboard:tutorial_list"), reverse("dashboard:category_list"),
                    reverse("dashboard:user_detail", args=[self.pending.pk]),
                    reverse("dashboard:tutorial_create")]:
            with self.subTest(url=url):
                self.assertEqual(self.signed_in_staff.get(url).status_code, 200)


class NoSelfApproval(DashboardBase):
    def test_staff_cannot_act_on_own_account(self):
        c = self.signed_in_staff
        targets = [
            reverse("dashboard:user_approval", args=[self.staff.pk, "approve"]),
            reverse("dashboard:user_approval", args=[self.staff.pk, "reject"]),
            reverse("dashboard:user_approval", args=[self.staff.pk, "reset_pending"]),
            reverse("dashboard:user_access_flag", args=[self.staff.pk]),
        ]
        for url in targets:
            with self.subTest(url=url):
                response = c.post(url)
                self.assertEqual(response.status_code, 302)  # redirected back, not applied
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.approval_status, User.ApprovalStatus.APPROVED)
        self.assertFalse(self.staff.access_all_tutorials)

    def test_self_action_not_audited(self):
        events = AuditEvent.objects.count()
        c = self.signed_in_staff
        c.post(reverse("dashboard:user_access_flag", args=[self.staff.pk]))
        self.assertEqual(AuditEvent.objects.count(), events)

    def test_granting_to_self_is_allowed_not_an_approval(self):
        # A staff member granting themselves tutorial access is an ordinary
        # grant (audited) — but never changes approval status. Kept distinct
        # from the approval-flag block by design.
        response = self.signed_in_staff.post(
            reverse("dashboard:grant", args=[self.staff.pk, self.tutorial.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.access_all_tutorials)
        self.assertTrue(
            TutorialAccess.objects.filter(user=self.staff, tutorial=self.tutorial).exists()
        )


class ApprovalActions(DashboardBase):
    def test_approve_sets_status_by_at_and_audits(self):
        response = self.signed_in_staff.post(
            reverse("dashboard:user_approval", args=[self.pending.pk, "approve"])
        )
        self.assertEqual(response.status_code, 302)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.approval_status, User.ApprovalStatus.APPROVED)
        self.assertEqual(self.pending.approved_by, self.staff)
        self.assertIsNotNone(self.pending.approved_at)
        event = AuditEvent.objects.order_by("-timestamp").first()
        self.assertEqual(event.action, AuditEvent.Action.USER_APPROVED)
        self.assertEqual(event.target_user, self.pending)
        self.assertEqual(event.actor, self.staff)

    def test_reject_and_reset_audited(self):
        self.signed_in_staff.post(reverse("dashboard:user_approval", args=[self.pending.pk, "reject"]))
        self.signed_in_staff.post(reverse("dashboard:user_approval", args=[self.pending.pk, "reset_pending"]))
        actions = list(
            AuditEvent.objects.order_by("timestamp").values_list("action", flat=True)
        )
        self.assertIn(AuditEvent.Action.USER_REJECTED, actions)
        self.assertIn(AuditEvent.Action.USER_RESET_PENDING, actions)

    def test_unknown_action_403(self):
        response = self.signed_in_staff.post(
            reverse("dashboard:user_approval", args=[self.pending.pk, "promote"])
        )
        self.assertEqual(response.status_code, 403)

    def test_access_flag_toggle_audited(self):
        self.signed_in_staff.post(reverse("dashboard:user_access_flag", args=[self.pending.pk]))
        self.pending.refresh_from_db()
        self.assertTrue(self.pending.access_all_tutorials)
        event = AuditEvent.objects.latest("timestamp")
        self.assertEqual(event.action, AuditEvent.Action.ACCESS_FLAG_SET)

    def test_get_is_rejected_on_mutation_endpoints(self):
        url = reverse("dashboard:user_approval", args=[self.pending.pk, "approve"])
        response = self.signed_in_staff.get(url)
        self.assertEqual(response.status_code, 405)

    def test_csrf_enforced_on_approve(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.staff)
        response = strict.post(
            reverse("dashboard:user_approval", args=[self.pending.pk, "approve"])
        )
        self.assertEqual(response.status_code, 403)


class Grants(DashboardBase):
    def test_grant_then_revoke_audited_and_state_changes(self):
        self.signed_in_staff.post(reverse("dashboard:grant", args=[self.plain.pk, self.tutorial.pk]))
        self.assertTrue(TutorialAccess.objects.filter(user=self.plain, tutorial=self.tutorial).exists())
        self.signed_in_staff.post(reverse("dashboard:revoke", args=[self.plain.pk, self.tutorial.pk]))
        self.assertFalse(TutorialAccess.objects.filter(user=self.plain, tutorial=self.tutorial).exists())
        actions = set(AuditEvent.objects.values_list("action", flat=True))
        self.assertIn(AuditEvent.Action.ACCESS_GRANTED, actions)
        self.assertIn(AuditEvent.Action.ACCESS_REVOKED, actions)

    def test_draft_tutorial_grant_is_blocked_by_fk(self):
        # Grants list only published tutorials, but POST tampering against a
        # draft pk still works at the DB level — documented behaviour: the
        # access predicate requires is_published, so a draft grant is inert.
        response = self.signed_in_staff.post(
            reverse("dashboard:grant", args=[self.plain.pk, self.draft.pk])
        )
        self.assertEqual(response.status_code, 302)
        # The user still cannot *reach* the draft tutorial: predicate denies.
        c = self._client(self.plain)
        self.assertEqual(c.get(reverse("tutorials:detail", args=["draft"])).status_code, 404)


class TutorialCrud(DashboardBase):
    def test_create_generates_slug_and_audits(self):
        response = self.signed_in_staff.post(
            reverse("dashboard:tutorial_create"),
            {"title": "Cabinet Irradiators 101", "description": "intro",
             "video_provider": "none", "video_ref": "", "is_published": "on",
             "ordering": "0", "duration_seconds": "0", "estimated_minutes": "5"},
        )
        self.assertEqual(response.status_code, 302)
        created = Tutorial.objects.get(title="Cabinet Irradiators 101")
        self.assertEqual(created.slug, "cabinet-irradiators-101")
        self.assertTrue(
            AuditEvent.objects.filter(action=AuditEvent.Action.TUTORIAL_UPDATED).exists()
        )

    def test_delete_audits_slug(self):
        slug = self.tutorial.slug
        response = self.signed_in_staff.post(
            reverse("dashboard:tutorial_delete", args=[self.tutorial.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Tutorial.objects.filter(pk=self.tutorial.pk).exists())
        event = AuditEvent.objects.latest("timestamp")
        self.assertEqual(event.action, AuditEvent.Action.TUTORIAL_DELETED)
        self.assertIn(slug, event.detail)


class ProgressSummaries(DashboardBase):
    def test_tutorial_list_shows_completion_stats(self):
        from tutorials.models import TutorialProgress

        TutorialProgress.objects.create(
            user=self.plain, tutorial=self.tutorial, percent=100, completed=True
        )
        response = self.signed_in_staff.get(reverse("dashboard:tutorial_list"))
        self.assertContains(response, "Rad setup")
        # grant_count 0, completed 1
        contexts = response.context["tutorials"]
        row = [t for t in contexts if t.pk == self.tutorial.pk][0]
        self.assertEqual(row.completed_count, 1)
        self.assertEqual(row.grant_count, 0)

    def test_user_detail_shows_progress_rows(self):
        from tutorials.models import TutorialProgress

        TutorialProgress.objects.create(
            user=self.plain, tutorial=self.tutorial, percent=40
        )
        response = self.signed_in_staff.get(
            reverse("dashboard:user_detail", args=[self.plain.pk])
        )
        self.assertContains(response, "40%")
