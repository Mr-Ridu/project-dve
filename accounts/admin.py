"""Django admin registration for the custom user model.

Phase 7 adds the custom staff dashboard; the standard admin remains available
to superusers for low-level management and is never exposed to ordinary users.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


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
