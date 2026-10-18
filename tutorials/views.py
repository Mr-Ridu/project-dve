"""Catalog + playback authorization views (Phase 5).

Every protected request re-evaluates can_access() server-side. The playback
endpoint is provider-agnostic: choosing the real video provider is a Phase 6
decision, so Stage-A issues a short-lived opaque token; the Phase 6 provider
module redeems tokens into whatever playback object that provider needs.
"""
import secrets

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .access import annotate_queryset, can_access, can_access_all
from .models import Tutorial

TOKEN_TTL_SECONDS = 300  # short-lived by design; expires <= 5 minutes


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
            "redeem_url": "tutorials:playback_redeem",  # wired in Phase 6
            "provider": tutorial.video_provider,
        },
        status=201,
    )
