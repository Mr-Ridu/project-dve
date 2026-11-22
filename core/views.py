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

from .forms import NewsletterSignupForm
from .models import NewsletterSubscriber
from .site_pages import PAGES
from .throttle import rate_limit


# --- Core pages -------------------------------------------------------------
def home(request):
    return render(request, "core/home.html", {"sectors": PRODUCT_SECTORS})


def about(request):
    return render(request, "core/about.html")


# Product portfolio — five sectors, rendered as alternating image/text rows
# on the products page (same layout as the reference site).
PRODUCT_SECTORS = [
    {
        "slug": "plant-machinery",
        "name": "Industrial Plant & Machinery",
        "tagline": "Built for strength. Built for success.",
        "short": "Processing, handling and line equipment built around your throughput.",
        "image": "images/products/client-plant.webp",
        "alt": "Industrial plant and machinery on site",
        "description": (
            "Industrial plant and machinery for production facilities, from single machines "
            "to complete lines, with after-sales service and technical expertise. We work "
            "around your layout, utilities and production targets to keep the line running."
        ),
        "scope": ["Single machines", "Complete lines", "Installation", "After-sales service"],
    },
    {
        "slug": "energy-power",
        "name": "Energy & Power",
        "tagline": "Small steps today, a green tomorrow.",
        "short": "Generation, distribution and balance-of-plant equipment.",
        "image": "images/products/client-energy.webp",
        "alt": "Energy and power sector",
        "description": (
            "Systems and equipment for the energy and power sector, backed by maintenance and "
            "spares supply. Our team supports generation and plant equipment with planned "
            "maintenance, breakdown response and genuine parts."
        ),
        "scope": ["Generation equipment", "Maintenance", "Spares supply", "Technical support"],
    },
    {
        "slug": "robotic-automation",
        "name": "Robotic & Automation",
        "tagline": "Automate the routine. Elevate the human.",
        "short": "Robotic cells and controls integrated with your existing plant.",
        "image": "images/products/client-robotics.webp",
        "alt": "Robotic arm and gear in an automated production cell",
        "description": (
            "Robotics and automation technology for modern production lines, integrated with "
            "your existing plant. We specify, install and commission automation cells that fit "
            "your process and your people."
        ),
        "scope": ["Robotic cells", "Line integration", "Controls & safety", "Commissioning"],
    },
    {
        "slug": "steel-metal",
        "name": "Steel & Metal",
        "tagline": "Creating foundations, creating futures \u2014 precision in every detail.",
        "short": "Heavy-duty equipment for melting, rolling and finishing lines.",
        "image": "images/products/client-steel.webp",
        "alt": "Steel coils and surface finishes",
        "description": (
            "Solutions for steel and metal processing operations, supplied and supported "
            "locally. From handling and processing equipment to line upgrades, we help keep "
            "heavy-duty operations productive."
        ),
        "scope": ["Processing equipment", "Handling systems", "Line upgrades", "Local support"],
    },
    {
        "slug": "pharma-biotech",
        "name": "Pharma & Biotech",
        "tagline": "Science in our hands, health in our mission.",
        "short": "Process equipment and cleanroom systems for regulated production.",
        "image": "images/products/client-pharma.webp",
        "alt": "Laboratory instrument for pharmaceutical analysis",
        "description": (
            "Process equipment and systems for pharmaceutical and biotechnology production, "
            "supplied with installation, validation support and spare parts. We help specify "
            "equipment that fits your process, cleanroom class and qualification requirements "
            "\u2014 then support it through its working life."
        ),
        "scope": ["Process equipment", "Cleanroom systems", "Validation support", "Spares & service"],
    },
]


def products(request):
    return render(request, "core/products.html", {"sectors": PRODUCT_SECTORS})


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


# --- Newsletter -------------------------------------------------------------
@rate_limit("forms")
@require_http_methods(["POST"])
def newsletter_subscribe(request):
    """Store a newsletter pop-up sign-up and show the result page.

    A repeated email refreshes that subscriber instead of adding a duplicate,
    so the dashboard list holds one row per address.
    """
    form = NewsletterSignupForm(request.POST)
    if not form.is_valid():
        return render(request, "core/newsletter_result.html", {"ok": False}, status=400)
    data = form.cleaned_data
    NewsletterSubscriber.objects.update_or_create(
        email=data["email"],
        defaults={
            "first_name": data["first_name"].strip(),
            "last_name": (data.get("last_name") or "").strip(),
            "interest": data["interest"],
            "consent": True,
            "ip_address": request.META.get("REMOTE_ADDR") or None,
        },
    )
    return render(request, "core/newsletter_result.html", {"ok": True})


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
