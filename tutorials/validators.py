"""Upload validation for staff-managed assets (Phase 9 security checklist).

The thumbnail field is staff-only, but a hijacked staff session must not be able
to upload an executable or fill the disk. The extension allow-list and the size
cap are attached to the model field, so the dashboard form and the admin both
apply them.
"""
from django.core.exceptions import ValidationError

MAX_THUMBNAIL_BYTES = 5 * 1024 * 1024  # 5 MB
THUMBNAIL_EXTENSIONS = ["png", "jpg", "jpeg", "webp", "gif"]

# Dashboard video upload: the file passes through this server on its way to
# Bunny Stream, so it gets an extension allow-list and a generous size cap
# before any bytes leave the browser's temp file.
MAX_VIDEO_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
VIDEO_EXTENSIONS = ["mp4", "mov", "m4v"]


def validate_video_extension(value):
    ext = (getattr(value, "name", "").rsplit(".", 1)[-1] or "").lower()
    if ext not in VIDEO_EXTENSIONS:
        raise ValidationError(
            "Video must be one of: %(exts)s.",
            params={"exts": ", ".join(VIDEO_EXTENSIONS)},
        )


def validate_video_size(value):
    size = getattr(value, "size", 0)
    if size > MAX_VIDEO_BYTES:
        raise ValidationError(
            "Video must be %(limit)s GB or smaller.",
            params={"limit": MAX_VIDEO_BYTES // (1024 ** 3)},
        )


def validate_thumbnail_size(value):
    size = getattr(value, "size", 0)
    if size > MAX_THUMBNAIL_BYTES:
        raise ValidationError(
            "Thumbnail must be %(limit)s MB or smaller.",
            params={"limit": MAX_THUMBNAIL_BYTES // (1024 * 1024)},
        )
