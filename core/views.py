"""Public page views.

Every page renders from the project's own Django templates (templates/core/*),
built with template inheritance over base.html. The five main pages have their
own templates; every other content page renders through templates/core/page.html
from the text registry in core/site_pages.py — no mirror files are read at
request time.
"""
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.csrf import requires_csrf_token
from django.views.decorators.http import require_http_methods

from .site_pages import PAGES
from .throttle import rate_limit


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


# --- Local form stub --------------------------------------------------------
@rate_limit("forms")
@require_http_methods(["GET", "POST"])
@requires_csrf_token
def form_placeholder(request):
    """Local target for the site's forms.

    Nothing is transmitted anywhere: wiring real delivery is a later phase
    decision.
    """
    return render(request, "core/form_placeholder.html")


# --- Site search ------------------------------------------------------------
@rate_limit("search")
def search(request):
    """Site search: content pages from the registry + published tutorials.

    GET-only and safe by construction: the query text only ever reaches the
    template as escaped output.
    """
    from tutorials.models import Tutorial

    from .search_index import search_text

    query = request.GET.get("s", "").strip()
    page_results = search_text(query)[:20]
    normalized = " ".join(query.split()).lower()
    tutorial_results = []
    if normalized:
        for t in Tutorial.objects.filter(is_published=True):
            hay = f"{t.title} {t.description} {t.slug}".lower()
            if all(term in hay for term in normalized.split()):
                tutorial_results.append(t)
    return render(request, "core/search.html", {
        "query": query,
        "legacy_results": page_results,
        "tutorials": tutorial_results[:10],
        "searched": bool(query),
    })


# --- Registry content pages -------------------------------------------------
def page_detail(request, slug):
    """Render one content page from the registry through core/page.html.

    The URL pattern already restricts slugs to lowercase letters, digits and
    hyphens, so there is no path to anything but this in-memory registry. An
    unknown slug is a 404.
    """
    page = PAGES.get(slug)
    if page is None:
        raise Http404("Not found")
    return render(request, "core/page.html", {"page": page})


# --- 404 --------------------------------------------------------------------
@requires_csrf_token
def page_not_found(request, exception=None):
    return render(request, "404.html", status=404)
