"""Cache-based rate limiting (same idea as accounts.throttle, shared).

No external dependency: it counts requests in the default Django cache —
LocMem in development, the shared database cache in production (see
config/settings), so the counters are shared across workers there.

Counters are per (action, client IP, identity). The identity is the account id
when the caller is signed in and "anon" otherwise, so one noisy account cannot
lock out everyone else behind the same NAT, while anonymous hammering is
limited per IP.

Limits live in settings.RATE_LIMITS as {scope: (max_requests, window_seconds)}
and are read at request time, so a deployment (or a test) can retune them
without touching the call sites. Abuse-prone views are wrapped with
@rate_limit(...); the response is an honest 429, never a silent drop.

This is a brake, not a security boundary: authorization is still decided by
tutorials.access on every request.
"""
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render

DEFAULT_LIMITS = {
    # scope: (max_requests, window_seconds)
    "auth": (5, 300),
    "playback": (60, 300),
    "progress": (120, 300),
    "forms": (30, 300),
    "search": (60, 300),
    "upload": (30, 900),
}


def limits_for(scope):
    configured = getattr(settings, "RATE_LIMITS", {}).get(scope)
    return configured if configured else DEFAULT_LIMITS[scope]


def _key(scope, ip, identity):
    identity = (identity or "").strip().lower()
    return f"rate-limit:{scope}:{ip}:{identity}"


def too_many(scope, ip, identity):
    limit, _window = limits_for(scope)
    return cache.get(_key(scope, ip, identity), 0) >= limit


def record(scope, ip, identity):
    """Count one request; the window restarts from the last counted request."""
    _limit, window = limits_for(scope)
    key = _key(scope, ip, identity)
    cache.set(key, cache.get(key, 0) + 1, window)


def clear(scope, ip, identity):
    cache.delete(_key(scope, ip, identity))


def _client_ip(request):
    """Direct socket peer only — never a spoofable header."""
    return request.META.get("REMOTE_ADDR") or "unknown"


def _identity(request):
    user = request.user
    if user is not None and user.is_authenticated:
        return f"user:{user.pk}"
    return "anon"


def rate_limit(scope, as_json=False):
    """429 once the scope's limit is exceeded, before the view runs.

    as_json=True answers with the same error shape the playback endpoints use
    ({"detail": ..., "code": "rate_limited"}); otherwise a normal 429 page.
    """

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            ip = _client_ip(request)
            identity = _identity(request)
            if too_many(scope, ip, identity):
                if as_json:
                    return JsonResponse(
                        {
                            "detail": "Too many requests — please slow down and try again shortly.",
                            "code": "rate_limited",
                        },
                        status=429,
                    )
                return render(request, "core/rate_limited.html", status=429)
            record(scope, ip, identity)
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
