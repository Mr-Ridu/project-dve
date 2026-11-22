"""Forms for the public site."""
from django import forms

from .models import NewsletterSubscriber


class NewsletterSignupForm(forms.Form):
    """Validates the "Get Our Latest News" pop-up (server-side, not just HTML)."""

    first_name = forms.CharField(max_length=80)
    last_name = forms.CharField(max_length=80, required=False)
    email = forms.EmailField(max_length=254)
    interest = forms.ChoiceField(choices=NewsletterSubscriber.Interest.choices)
    consent = forms.BooleanField()

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()
