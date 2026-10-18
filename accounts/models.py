"""Custom user model.

Approved design (Phase 1, decision 2): extend AbstractUser with the account
approval status and tutorial-access flag. This keeps Django's built-in auth
machinery (forms, views, permissions, admin) while giving the approval
lifecycle a first-class home. Defined before the initial migration, as
AUTH_USER_MODEL cannot change afterwards.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


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
