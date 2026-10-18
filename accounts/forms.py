"""Authentication forms (Phase 4).

Built on Django's forms — no custom auth machinery. Registration collects
only the fields the approval workflow needs; every new account is created
pending (views enforce this, forms validate input).
"""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm


class LoginForm(AuthenticationForm):
    """Stock AuthenticationForm with friendlier markup hooks."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"autofocus": True})


class RegistrationForm(UserCreationForm):
    """Public sign-up. Created users are pending until staff approve."""

    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)

    class Meta:
        model = get_user_model()
        fields = ("username", "first_name", "last_name", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.approval_status = "pending"  # lifecycle invariant, set on every save
        if commit:
            user.save()
        return user
