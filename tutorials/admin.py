"""Django admin registration for the tutorial catalog.

Without this file the admin showed only the accounts app, so there was no way to
create a tutorial or grant access from `/admin/` — the staff dashboard worked,
but the admin looked empty. Both are supported; the dashboard stays the primary
UI for staff, the admin is the low-level fallback for superusers.
"""
from django.contrib import admin
from django.db.models import Count

from .models import Category, Tutorial, TutorialAccess, TutorialProgress


class TutorialAccessInline(admin.TabularInline):
    model = TutorialAccess
    fk_name = "tutorial"
    extra = 0
    autocomplete_fields = ("user",)
    raw_id_fields = ("granted_by",)


class TutorialProgressInline(admin.TabularInline):
    model = TutorialProgress
    fk_name = "tutorial"
    extra = 0
    can_delete = False
    fields = ("user", "seconds_watched", "percent", "completed", "last_seen_at")
    readonly_fields = ("user", "seconds_watched", "percent", "completed", "last_seen_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "ordering", "tutorial_count")
    list_editable = ("ordering",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_tutorial_count=Count("tutorials"))

    @admin.display(description="Tutorials", ordering="_tutorial_count")
    def tutorial_count(self, obj):
        return obj._tutorial_count


@admin.register(Tutorial)
class TutorialAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "video_provider",
        "is_published",
        "duration_seconds",
        "grant_count",
    )
    list_filter = ("is_published", "video_provider", "category")
    list_editable = ("is_published",)
    search_fields = ("title", "slug", "description", "video_ref")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("title", "slug", "category", "description")}),
        ("Media", {"fields": ("thumbnail", "duration_seconds", "estimated_minutes")}),
        (
            "Playback",
            {
                "fields": ("video_provider", "video_ref"),
                "description": "video_ref is the Bunny video GUID, the YouTube video "
                "id (or link) for an unlisted video, or a plain URL in development. "
                "It is never exposed except through /tutorials/<slug>/authorize/ + "
                "redeem, which re-check access first.",
            },
        ),
        ("Publishing", {"fields": ("is_published", "ordering", "created_at", "updated_at")}),
    )
    inlines = (TutorialAccessInline, TutorialProgressInline)
    actions = ("publish", "unpublish")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_grant_count=Count("grants"))

    @admin.display(description="Grants", ordering="_grant_count")
    def grant_count(self, obj):
        return obj._grant_count

    @admin.action(description="Publish selected tutorials")
    def publish(self, request, queryset):
        updated = queryset.update(is_published=True)
        self.message_user(request, f"{updated} tutorial(s) published.")

    @admin.action(description="Unpublish selected tutorials")
    def unpublish(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(request, f"{updated} tutorial(s) unpublished.")


@admin.register(TutorialAccess)
class TutorialAccessAdmin(admin.ModelAdmin):
    list_display = ("user", "tutorial", "granted_by", "granted_at")
    list_filter = ("tutorial",)
    search_fields = ("user__username", "user__email", "tutorial__title")
    autocomplete_fields = ("user", "tutorial")
    raw_id_fields = ("granted_by",)


@admin.register(TutorialProgress)
class TutorialProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "tutorial", "percent", "completed", "seconds_watched", "last_seen_at")
    list_filter = ("completed", "tutorial")
    search_fields = ("user__username", "tutorial__title")
    autocomplete_fields = ("user", "tutorial")
    readonly_fields = (
        "user",
        "tutorial",
        "seconds_watched",
        "percent",
        "completed",
        "completed_at",
        "last_seen_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False
