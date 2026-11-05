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
from django.utils import timezone
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from core.throttle import rate_limit
from .access import annotate_queryset, can_access, can_access_all
from .models import Category, Tutorial, TutorialProgress
from .providers import bunny, youtube
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


@rate_limit("playback", as_json=True)
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


@rate_limit("playback", as_json=True)
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

    if tutorial.video_provider == Tutorial.VideoProvider.YOUTUBE:
        # Unlisted video: the reference must yield a real video id, otherwise the
        # player would sit on a dead iframe with no explanation.
        vid = youtube.video_id(tutorial.video_ref)
        if not vid:
            return JsonResponse(
                {
                    "detail": (
                        "This tutorial's YouTube reference is not a video id or a "
                        "YouTube video URL. Use the 11-character id from the URL."
                    ),
                    "code": "provider_not_configured",
                },
                status=503,
            )
        return JsonResponse({"provider": "youtube", "embed_url": youtube.embed_url(vid)})

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


# --- Phase 8: progress reporting + category page ----------------------------

MAX_SECONDS_PER_REPORT = 60  # per-request cap; a 1000s lie moves reality by 60
COMPLETE_AT_PERCENT = 90  # industry-standard completion threshold


@rate_limit("progress", as_json=True)
@require_http_methods(["POST"])
@csrf_protect
def progress_report(request, slug):
    """Accept client-side watch heartbeats (POST {seconds}).

    Access first, numbers second: unauthorized/revoked users reporting get a
    403 regardless of payload. seconds is clamped to [0, 60]; the payload
    never accelerates beyond real wall-clock playback limits.
    """
    tutorial = get_object_or_404(Tutorial, slug=slug, is_published=True)
    if not can_access(request.user, tutorial):
        return JsonResponse({"detail": "No access."}, status=403)

    raw = request.POST.get("seconds", "")
    try:
        seconds = int(raw) if raw else 0
    except (TypeError, ValueError):
        return JsonResponse({"detail": "seconds must be an integer."}, status=400)
    if seconds < 0:
        return JsonResponse({"detail": "seconds must be >= 0."}, status=400)
    seconds = min(seconds, MAX_SECONDS_PER_REPORT)

    progress, _ = TutorialProgress.objects.get_or_create(user=request.user, tutorial=tutorial)
    progress.seconds_watched += seconds
    progress.last_seen_at = timezone.now()
    duration = tutorial.duration_seconds
    if duration:
        percent = min(100, round(progress.seconds_watched / duration * 100))
    else:
        percent = progress.percent
    progress.percent = max(progress.percent, percent) if duration else progress.percent
    just_completed = False
    if duration and progress.percent >= COMPLETE_AT_PERCENT and not progress.completed:
        progress.completed = True
        progress.completed_at = timezone.now()
        just_completed = True
    progress.save()
    return JsonResponse(
        {
            "percent": progress.percent,
            "seconds_watched": progress.seconds_watched,
            "completed": progress.completed,
            "just_completed": just_completed,
        },
        status=200,
    )


def category_detail(request, slug):
    """Published tutorials in one category, access-flag decorated.

    The category itself is public data; contents are going through exactly
    the same predicate as the main catalog (cosmetic annotations only).
    """
    category = get_object_or_404(Category, slug=slug)
    library = _visible_library(request.user).filter(category=category)
    return render(request, "tutorials/category.html", {
        "category": category,
        "tutorials": library,
        "can_access_all": can_access_all(request.user),
    })
