"""Custom user model and audit log.

Approved design (Phase 1, decision 2): extend AbstractUser with the account
approval status and tutorial-access flag. This keeps Django's built-in auth
machinery (forms, views, permissions, admin) while giving the approval
lifecycle a first-class home. Defined before the initial migration, as
AUTH_USER_MODEL cannot change afterwards.

AuditEvent records every approval-domain state change (register, approve,
reject, grant/revoke access flags) with actor and IP so the approval
lifecycle is fully reviewable.
"""
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class ApprovalStatus(models.TextChoices):
        PENDING = "pending", "Pending approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    approval_status = models.CharField(
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        help_text="Accounts start pending; staff approval is required before tutorial access.",
    )
    access_all_tutorials = models.BooleanField(
        default=False,
        help_text="Admin-granted: bypasses per-tutorial grants. Default off — "
        "global approval alone never opens the whole library.",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_accounts",
    )

    def is_approved(self):
        """Server-side access predicate component — never trust client state."""
        return (
            self.is_active
            and self.approval_status == self.ApprovalStatus.APPROVED
        )

    def __str__(self):
        return f"{self.username} ({self.get_approval_status_display()})"


class AuditEvent(models.Model):
    """Immutable audit trail for the approval/access domain.

    Actions follow ``<action>_<subject>`` naming: user_registered,
    user_approved, user_rejected, user_reset_pending, access_flag_set.
    ``actor`` is the staff user performing the change (None for
    self-registration). ``target_user`` is the affected account.
    """

    class Action(models.TextChoices):
        USER_REGISTERED = "user_registered", "User registered"
        USER_APPROVED = "user_approved", "User approved"
        USER_REJECTED = "user_rejected", "User rejected"
        USER_RESET_PENDING = "user_reset_pending", "User reset to pending"
        ACCESS_FLAG_SET = "access_flag_set", "access_all_tutorials changed"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_actions_taken",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events_about",
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    detail = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        actor = self.actor.username if self.actor_id else "system"
        target = self.target_user.username if self.target_user_id else "-"
        return f"{self.timestamp:%Y-%m-%d %H:%M} {actor} {self.action} {target}"
