"""Staff dashboard forms (Phase 7)."""
from django import forms
from django.utils.text import slugify

from tutorials.models import Category, Tutorial
from tutorials.providers import youtube
from tutorials.validators import validate_video_extension, validate_video_size


class TutorialForm(forms.ModelForm):
    # Not a model field: the file goes straight to Bunny Stream (see
    # tutorials/providers/bunny_upload.py) and never touches disk here. The
    # view uploads it and fills video_provider/video_ref from the result.
    video_file = forms.FileField(
        required=False,
        validators=[validate_video_extension, validate_video_size],
        label="Video file",
        help_text=(
            "Upload an MP4/MOV from this computer. It is sent straight to Bunny "
            "Stream and fills Video provider + Video reference automatically — "
            "no bunny.net visit needed. Leave empty to keep the current video."
        ),
    )

    class Meta:
        model = Tutorial
        fields = [
            "title",
            "slug",
            "description",
            "thumbnail",
            "category",
            "duration_seconds",
            "estimated_minutes",
            "video_provider",
            "video_ref",
            "is_published",
            "ordering",
        ]

    # Declared fields render after model fields unless we order them ourselves;
    # the upload sits next to the provider fields where it belongs.
    FIELD_ORDER = [
        "title",
        "slug",
        "description",
        "thumbnail",
        "category",
        "duration_seconds",
        "estimated_minutes",
        "video_file",
        "video_provider",
        "video_ref",
        "is_published",
        "ordering",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields = {
            name: self.fields[name] for name in self.FIELD_ORDER if name in self.fields
        }
        self.fields["video_ref"].help_text = (
            "Leave empty when you upload a Video file above — the upload fills this "
            "with the Bunny GUID automatically. Only needed for manual entry: "
            "Bunny Stream = the video GUID (32d140e2-…), YouTube = the 11-character "
            "video id or a watch/youtu.be link, Plain URL = the full file URL "
            "(local preview only)."
        )
        if not self.instance.pk:
            self.fields["slug"].required = False  # auto-generated from title
            self.fields["slug"].help_text = "Leave blank to generate from the title."

    def clean(self):
        cleaned = super().clean()
        # Catch a bad YouTube reference here, where the staff member can see the
        # message, instead of letting the player answer 503 at play time.
        if cleaned.get("video_provider") == Tutorial.VideoProvider.YOUTUBE:
            ref = (cleaned.get("video_ref") or "").strip()
            video_file = cleaned.get("video_file")
            if not ref and not video_file:
                self.add_error(
                    "video_ref",
                    "Paste the YouTube video id (11 characters) or the video's "
                    "watch/youtu.be link.",
                )
            elif ref and not youtube.video_id(ref):
                self.add_error(
                    "video_ref",
                    "That is not a YouTube video id or video link. Use the 11 "
                    "characters after v= in the link, or paste the whole "
                    "https://youtu.be/… link.",
                )
        return cleaned

    def save(self, commit=True):
        if not self.instance.pk and not self.cleaned_data.get("slug"):
            base = slugify(self.cleaned_data.get("title", ""))[:200] or "tutorial"
            slug, n = base, 1
            while Tutorial.objects.filter(slug=slug).exists():
                n += 1
                slug = f"{base}-{n}"
            self.instance.slug = slug
        return super().save(commit=commit)


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug", "ordering"]
