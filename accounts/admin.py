"""Django admin registration for the custom user model.

Phase 7 adds the custom staff dashboard; the standard admin remains available
to superusers for low-level management and is never exposed to ordinary users.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import AuditEvent, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = DjangoUserAdmin.list_display + (
        "approval_status",
        "access_all_tutorials",
        "is_active",
    )
    list_filter = DjangoUserAdmin.list_filter + ("approval_status", "access_all_tutorials")
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Approval & tutorial access",
            {"fields": ("approval_status", "access_all_tutorials", "approved_at", "approved_by")},
        ),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        (
            "Approval & tutorial access",
            {"fields": ("approval_status", "access_all_tutorials")},
        ),
    )


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """Read-only view of the approval/access audit trail."""

    list_display = ("timestamp", "action", "actor", "target_user", "ip_address")
    list_filter = ("action", "timestamp")
    search_fields = ("actor__username", "target_user__username", "detail")
    date_hierarchy = "timestamp"
    readonly_fields = (
        "actor",
        "target_user",
        "action",
        "detail",
        "ip_address",
        "timestamp",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
