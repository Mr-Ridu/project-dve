"""Catalog + playback authorization views (Phase 5, extended in Phase 6).

Every protected request re-evaluates can_access() server-side. The playback
endpoint is provider-agnostic: Phase 6 added Bunny Stream as the decided
provider, so stage A mints a short-lived opaque token and stage B (`redeem`)
turns it into signed Bunny playback after a second access re-check.
"""
import secrets
import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .access import annotate_queryset, can_access, can_access_all
from .models import Tutorial
from .providers import bunny
from accounts.models import User as UserModel

TOKEN_TTL_SECONDS = 300  # short-lived by design; expires <= 5 minutes
# Bunny embed-link TTL: embeds cannot be re-signed while playing, so this is
# longer than the authorization token but still short-lived (1 hour).
BUNNY_EMBED_TTL_SECONDS = 3600


def _visible_library(user):
    """Published tutorials only; per-row access flag is cosmetic help."""
    qs = Tutorial.objects.filter(is_published=True).select_related("category")
    return annotate_queryset(qs, user)


def tutorial_list(request):
    library = _visible_library(request.user)  # published + annotated only
    groups = []
    for category in sorted(
        {t.category for t in library if t.category_id},
        key=lambda c: (c.ordering, c.name),
    ):
        groups.append({
            "category": category,
            "items": [t for t in library if t.category_id == category.pk],
        })
    groups.append({
        "category": None,
        "items": [t for t in library if not t.category_id],
    })
    # Drop the empty "Other" bucket when nothing is uncategorised.
    groups = [g for g in groups if g["items"]]
    return render(request, "tutorials/list.html", {
        "groups": groups,
        "can_access_all": can_access_all(request.user),
    })


def tutorial_detail(request, slug):
    # Unpublished is a hard 404 for everyone — no existence leak, no grant
    # override (the Phase 1 predicate requires is_published unconditionally).
    tutorial = get_object_or_404(Tutorial, slug=slug, is_published=True)
    if not can_access(request.user, tutorial):
        return _denied(request)
    progress = None
    if request.user.is_authenticated:
        progress = tutorial.progress_records.filter(user=request.user).first()
    return render(request, "tutorials/detail.html", {
        "tutorial": tutorial,
        "progress": progress,
    })


def _denied(request):
    """Soft denial for signed-in-but-unapproved or grantless users."""
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    return render(request, "tutorials/denied.html", status=403)


@require_http_methods(["POST"])
@csrf_protect
def playback_authorize(request, slug):
    """Provider-agnostic playback authorization (Stage A).

    Returns a short-lived opaque token immediately + the redemption URL the
    Phase 6 provider module will implement (`tutorials:playback_redeem`).
    Revocation takes effect on the very next request: the token is minted
    only after can_access() passes, and redemption re-checks access again.
    """
    tutorial = get_object_or_404(Tutorial, slug=slug, is_published=True)
    if not can_access(request.user, tutorial):
        return JsonResponse(
            {
                "detail": "Play unavailable for this account.",
                "code": "not_authorized",
            },
            status=403,
        )

    token = secrets.token_urlsafe(32)
    cache.set(
        f"play_token:{token}",
        {"user_id": request.user.pk, "tutorial_id": tutorial.pk},
        TOKEN_TTL_SECONDS,
    )
    return JsonResponse(
        {
            "token": token,
            "expires_in": TOKEN_TTL_SECONDS,
            "redeem_url": reverse("tutorials:redeem"),
            "provider": tutorial.video_provider,
        },
        status=201,
    )


@require_http_methods(["POST"])
@csrf_protect
def playback_redeem(request):
    """Stage B: turn an opaque authorize token into signed playback (Phase 6).

    One-time redemption: the token is consumed on first use, re-checks access,
    and only then signs the Bunny embed URL. Bunny config missing → honest
    503, not a silent failure.
    """
    token = request.POST.get("token", "")
    context = cache.get(f"play_token:{token}") if token else None
    if not context:
        return JsonResponse(
            {"detail": "Invalid or expired playback token.", "code": "token_invalid"},
            status=403,
        )

    user = get_object_or_404(UserModel, pk=context["user_id"])
    tutorial = get_object_or_404(Tutorial, pk=context["tutorial_id"], is_published=True)
    if not can_access(user, tutorial):  # second check: revoke between steps wins
        cache.delete(f"play_token:{token}")
        return JsonResponse(
            {"detail": "Play unavailable for this account.", "code": "not_authorized"},
            status=403,
        )
    cache.delete(f"play_token:{token}")  # one-time use

    if tutorial.video_provider == Tutorial.VideoProvider.URL:
        # Dev/preview only — signed URL straight from the stored reference.
        return JsonResponse({"provider": "url", "url": tutorial.video_ref})

    security_key = getattr(settings, "BUNNY_STREAM_SECURITY_KEY", "")
    library_id = getattr(settings, "BUNNY_STREAM_LIBRARY_ID", "")
    if tutorial.video_provider == Tutorial.VideoProvider.NONE or not (security_key and library_id and tutorial.video_ref):
        return JsonResponse(
            {
                "detail": "Video is not configured yet (or Bunny credentials missing).",
                "code": "provider_not_configured",
            },
            status=503,
        )

    expires = int(time.time()) + BUNNY_EMBED_TTL_SECONDS
    return JsonResponse(
        {
            "provider": "bunny",
            "embed_url": bunny.embed_url(library_id, tutorial.video_ref, security_key, expires),
            "embed_expires_in": BUNNY_EMBED_TTL_SECONDS,
        },
        status=200,
    )
