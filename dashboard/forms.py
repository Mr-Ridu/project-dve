"""Staff dashboard forms (Phase 7)."""
from django import forms
from django.utils.text import slugify

from tutorials.models import Category, Tutorial
from tutorials.providers import youtube


class TutorialForm(forms.ModelForm):
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
            "YouTube: paste the whole watch/youtu.be link or just the 11-character "
            "video id. Plain URL: the full file URL (local preview only)."
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
            if not ref:
                self.add_error(
                    "video_ref",
                    "Paste the YouTube video id (11 characters) or the video's "
                    "watch/youtu.be link.",
                )
            elif not youtube.video_id(ref):
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
