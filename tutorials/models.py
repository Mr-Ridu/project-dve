"""Tutorial catalog and access-control models (Phase 5).

Design approved in Phase 1 §6. The access rule lives in one place —
tutorials.access.can_access() — and is re-evaluated on *every* protected
request; progress state is never treated as proof of authorization.
"""
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models

from .validators import THUMBNAIL_EXTENSIONS, validate_thumbnail_size


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordering", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Tutorial(models.Model):
    class VideoProvider(models.TextChoices):
        NONE = "none", "No video yet"
        URL = "url", "Plain URL (dev/preview only)"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    # FileField (not ImageField) keeps the dependency list Pillow-free; the
    # Phase 9 optimization pass works offline on the uploaded file.
    # Staff-only uploads still get an extension allow-list and a size cap.
    thumbnail = models.FileField(
        upload_to="tutorial_thumbs/",
        blank=True,
        validators=[FileExtensionValidator(THUMBNAIL_EXTENSIONS), validate_thumbnail_size],
    )
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="tutorials"
    )
    duration_seconds = models.PositiveIntegerField(default=0)
    estimated_minutes = models.PositiveIntegerField(default=0)
    video_provider = models.CharField(
        max_length=20, choices=VideoProvider.choices, default=VideoProvider.NONE
    )
    # Opaque reference for the chosen provider (asset id, external URL, ...).
    # Never exposed to the client directly — playback goes through the
    # authorization endpoint only.
    video_ref = models.CharField(max_length=500, blank=True)
    is_published = models.BooleanField(
        default=False, help_text="Unpublished tutorials are 404 for everyone, grants included."
    )
    ordering = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordering", "title"]

    def __str__(self):
        return self.title


class TutorialAccess(models.Model):
    """Explicit per-user grant. Revocation = deleting the row."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tutorial_grants"
    )
    tutorial = models.ForeignKey(
        Tutorial, on_delete=models.CASCADE, related_name="grants"
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="grants_given",
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "tutorial"], name="unique_user_tutorial_grant")
        ]

    def __str__(self):
        return f"{self.user} → {self.tutorial}"


class TutorialProgress(models.Model):
    """Watch state. Stored but *never* used in any access decision."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tutorial_progress"
    )
    tutorial = models.ForeignKey(
        Tutorial, on_delete=models.CASCADE, related_name="progress_records"
    )
    seconds_watched = models.PositiveIntegerField(default=0)
    percent = models.PositiveSmallIntegerField(default=0)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "tutorial"], name="unique_user_tutorial_progress")
        ]

    def __str__(self):
        return f"{self.user} @ {self.percent}% of {self.tutorial}"
