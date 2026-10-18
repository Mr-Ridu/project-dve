"""Public page views (Phase 3).

Five core pages render as real Django templates built from the site's own
design (templates/core/*.html). The remaining mirrored pages are served from
legacy/ through a sanitized catch-all so every original URL keeps working
until each page is converted.
"""
import re
from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import requires_csrf_token
from django.views.decorators.http import require_http_methods

from .sanitize import sanitize

LEGACY_DIR = Path(settings.BASE_DIR) / "legacy"
SAFE_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")


# --- Core pages -------------------------------------------------------------
def home(request):
    return render(request, "core/home.html")


def about(request):
    return render(request, "core/about.html")


def products(request):
    return render(request, "core/products.html")


def services(request):
    return render(request, "core/services.html")


def contact(request):
    return render(request, "core/contact.html")


# --- Stubs (real delivery is configured in a later phase) --------------------
@require_http_methods(["GET", "POST"])
@requires_csrf_token
def form_placeholder(request):
    """Local target for the site's forms.

    The mirrored forms used to POST to third parties (xstrahl.com admin-ajax,
    the original company's Zoho desk). They now land here: nothing is
    transmitted anywhere. Wiring real delivery is a later phase decision.
    """
    return render(request, "core/form_placeholder.html")


def search_stub(request):
    """Search arrives in Phase 8."""
    return render(request, "core/search_stub.html")


# --- Sanitized legacy catch-all --------------------------------------------
def legacy_page(request, slug):
    """Serve a not-yet-converted mirrored page at its original URL.

    Only strict lowercase slugs are accepted (no traversal); the file must be
    a direct child of legacy/; output passes the shared sanitizer so no
    third-party endpoint is ever emitted to a visitor.
    """
    if not SAFE_SLUG_RE.match(slug):
        raise Http404("Not found")
    path = (LEGACY_DIR / f"{slug}.html").resolve()
    if path.parent != LEGACY_DIR.resolve() or not path.is_file():
        raise Http404("Not found")
    html = path.read_text(encoding="utf-8", errors="replace")
    return HttpResponse(sanitize(html), content_type="text/html; charset=utf-8")


# --- 404 --------------------------------------------------------------------
@requires_csrf_token
def page_not_found(request, exception=None):
    return render(request, "404.html", status=404)
