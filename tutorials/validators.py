"""Upload validation for staff-managed assets (Phase 9 security checklist).

The thumbnail field is staff-only, but a hijacked staff session must not be able
to upload an executable or fill the disk. The extension allow-list and the size
cap are attached to the model field, so the dashboard form and the admin both
apply them.
"""
from django.core.exceptions import ValidationError

MAX_THUMBNAIL_BYTES = 5 * 1024 * 1024  # 5 MB
THUMBNAIL_EXTENSIONS = ["png", "jpg", "jpeg", "webp", "gif"]


def validate_thumbnail_size(value):
    size = getattr(value, "size", 0)
    if size > MAX_THUMBNAIL_BYTES:
        raise ValidationError(
            "Thumbnail must be %(limit)s MB or smaller.",
            params={"limit": MAX_THUMBNAIL_BYTES // (1024 * 1024)},
        )
