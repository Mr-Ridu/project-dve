"""Staff dashboard forms (Phase 7)."""
from django import forms
from django.utils.text import slugify

from tutorials.models import Category, Tutorial


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["slug"].required = False  # auto-generated from title
            self.fields["slug"].help_text = "Leave blank to generate from the title."

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
