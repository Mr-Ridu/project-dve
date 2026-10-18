"""Cache-based throttling for auth endpoints.

No external dependency (report §5: django-axes optional; cache approach
chosen). Counts failed attempts per (IP, username) pair. Uses the default
Django cache; on a default LocMem backends this is per-process, which is
adequate for a single-process shared-host deployment and safe to swap for
Redis/Memcached later without code changes.
"""
from django.core.cache import cache

MAX_EVENTS = 5
WINDOW_SECONDS = 300  # 5 minutes


def _key(scope, ip, username):
    username = (username or "").strip().lower()
    return f"auth-throttle:{scope}:{ip}:{username}"


def too_many_attempts(scope, ip, username):
    return cache.get(_key(scope, ip, username), 0) >= MAX_EVENTS


def record_failure(scope, ip, username):
    key = _key(scope, ip, username)
    count = cache.get(key, 0)
    # Half the window again after the last failure; counter expiry resets the
    # window once it lapses.
    cache.set(key, count + 1, WINDOW_SECONDS)


def clear(scope, ip, username):
    cache.delete(_key(scope, ip, username))
