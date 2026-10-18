"""Account views (Phase 4).

Lifecycle: register -> account created pending -> user may log in and sees
an explicit "awaiting approval" state -> staff approves/rejects (audited).
Every authorization decision is server-side; redirects are validated.
"""
import logging

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from accounts.models import AuditEvent
from accounts.throttle import clear, record_failure, too_many_attempts
from .forms import LoginForm, RegistrationForm

logger = logging.getLogger("accounts")


def _client_ip(request):
    """Direct socket peer only — never a spoofable header."""
    xff = request.META.get("REMOTE_ADDR", "")
    return xff or None


def _safe_redirect(request, fallback):
    """Validate ?next= against the current host; open redirects die here."""
    candidate = request.POST.get("next") or request.GET.get("next")
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return fallback


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        messages.info(request, "You already have an account.")
        return redirect("core:home")

    ip = _client_ip(request)
    if too_many_attempts("register", ip, request.method == "POST" and request.POST.get("username", "")):
        messages.error(request, "Too many attempts. Please try again in a few minutes.")
        return render(request, "accounts/register.html", {"form": RegistrationForm()}, status=429)

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            AuditEvent.objects.create(
                actor=None,
                target_user=user,
                action=AuditEvent.Action.USER_REGISTERED,
                ip_address=ip,
            )
            messages.success(
                request,
                "Account created. You can sign in now, but tutorial access stays "
                "locked until an administrator approves your account.",
            )
            logger.info("registration pending approval: %s", user.username)
            return redirect("accounts:login")
    else:
        form = RegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    ip = _client_ip(request)
    if request.method == "POST":
        username = request.POST.get("username", "")
        if too_many_attempts("login", ip, username):
            messages.error(request, "Too many attempts. Please try again in a few minutes.")
            return render(
                request, "accounts/login.html",
                {"form": LoginForm(request), "next": request.POST.get("next", "")},
                status=429,
            )

    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            if not user.is_active:
                return render(request, "accounts/login.html",
                              {"form": form, "next": request.POST.get("next", "")})
            auth_login(request, user)
            next_url = _safe_redirect(request, "core:home")
            clear("login", ip, username)  # successes clear the counter
            if not user.is_approved():
                messages.warning(
                    request,
                    "Your account has not been approved for tutorial access yet. "
                    "Contact the site team if you believe this is an error.",
                )
                return redirect("accounts:pending")
            return redirect(next_url)
        record_failure("login", ip, username)
    return render(request, "accounts/login.html", {"form": form, "next": request.GET.get("next", "")})


@require_http_methods(["POST"])
def logout_view(request):
    """POST-only logout (Django 5 best practice; CSRF-protected by the form)."""
    auth_logout(request)
    messages.info(request, "You have been signed out.")
    return redirect("core:home")


@require_http_methods(["GET"])
def pending(request):
    """Explains the awaiting-approval state to signed-in but unapproved users."""
    return render(request, "accounts/pending.html")
