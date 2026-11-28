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
# The landing page's presentations band carries only this category. Every other
# category (soft skills, operation, maintenance, ...) stays inside the library.
HOME_PRESENTATION_CATEGORY_SLUG = "presentation"


def home(request):
    """Landing page; the presentations band shows the first four presentation videos.

    Thumbnails are public, but playback stays behind the tutorial access rules
    (can_access is re-checked on the detail and playback endpoints).
    """
    from tutorials.access import annotate_queryset
    from tutorials.models import Tutorial

    tutorials = annotate_queryset(
        Tutorial.objects.filter(
            is_published=True, category__slug=HOME_PRESENTATION_CATEGORY_SLUG
        ).select_related("category"),
        request.user,
    )[:4]
    return render(
        request,
        "core/home.html",
        {"sectors": PRODUCT_SECTORS, "tutorials": tutorials},
    )


def about(request):
    return render(request, "core/about.html")


# Product portfolio — five sectors, each with its own detail page.
# `description` is the two-line teaser used on the home page and the portfolio
# rows; `details` and `scope` carry the full sector copy to /products/<slug>/.
PRODUCT_SECTORS = [
    {
        "slug": "plant-machinery",
        "name": "Industrial Plant & Machinery",
        "tagline": "Built for strength. Built for success.",
        "short": "Processing, handling and line equipment built around your throughput.",
        "description": (
            "Mechanical design, plant layout, maintenance engineering and process operations for "
            "raw-material processing \u2014 from mixing, grinding, granulation and drying to "
            "casting-related technologies."
        ),
        "details": [
            (
                "Our company covers mechanical design plant layout, maintenance engineering and "
                "process operations to provide products and services related to raw material "
                "processing."
            ),
            (
                "We work across mixing technology, grinding technology, granulation technology and "
                "drying technology, together with casting-related technologies \u2014 towards "
                "concrete, plaster, ceramics, refractory, glass, lead acid battery, lithium-ion "
                "battery, carbon, iron and steel."
            ),
        ],
        "image": "images/products/client-plant.webp",
        "alt": "Industrial plant and machinery on site",
        "scope": [
            "Mixing technology",
            "Grinding technology",
            "Granulation technology",
            "Drying technology",
            "Casting-related technologies",
            "Concrete, plaster & ceramics",
            "Refractory & glass",
            "Lead acid & lithium-ion battery",
            "Carbon, iron & steel",
        ],
    },
    {
        "slug": "energy-power",
        "name": "Energy & Power",
        "tagline": "Small steps today, a green tomorrow.",
        "short": "Generation, distribution and balance-of-plant equipment.",
        "description": (
            "Solar power systems, modules, inverters, storage batteries and EV charging stations "
            "\u2014 screened, inspected and supported from consultation through after-sales."
        ),
        "details": [
            (
                "The stable supply of power is an energy element for the infrastructure supporting "
                "our modern society. We specialise in solar power systems, solar modules, solar "
                "inverters, storage batteries and electric vehicle charging stations."
            ),
            (
                "To ensure product quality, we have established strict supplier screening and "
                "product inspection systems, cooperating with well-known domestic vendors with "
                "advanced production equipment and mature quality control systems."
            ),
            (
                "We provide services from product consultation and customisation through order "
                "follow-up to logistics and after-sales support."
            ),
        ],
        "image": "images/products/client-energy.webp",
        "alt": "Energy and power sector",
        "scope": [
            "Solar power systems",
            "Solar modules",
            "Solar inverters",
            "Storage batteries",
            "EV charging stations",
            "Product consultation",
            "Customisation",
            "Order follow-up",
            "Logistics & after-sales",
        ],
    },
    {
        "slug": "robotic-automation",
        "name": "Robotic & Automation",
        "tagline": "Automate the routine. Elevate the human.",
        "short": "Robotic cells and controls integrated with your existing plant.",
        "description": (
            "Comprehensive automation solutions that bridge cutting-edge technology and practical "
            "implementation \u2014 with design and consulting support for efficiency, cost and "
            "customer experience."
        ),
        "details": [
            (
                "Transform your industrial operation with our comprehensive automation solutions. "
                "We bridge the gap between cutting-edge technology and practical implementation, "
                "delivering reliability, efficiency and innovation."
            ),
            (
                "We design solutions and provide consulting services to businesses to improve "
                "operational efficiency, reduce costs and create the best possible customer "
                "experience."
            ),
        ],
        "image": "images/products/client-robotics.webp",
        "alt": "Robotic arm and gear in an automated production cell",
        "scope": [
            "Automation solutions",
            "Solution design",
            "Consulting services",
            "Operational efficiency",
            "Cost reduction",
            "Customer experience",
        ],
    },
    {
        "slug": "steel-metal",
        "name": "Steel & Metal",
        "tagline": "Creating foundations, creating futures \u2014 precision in every detail.",
        "short": "Heavy-duty equipment for melting, rolling and finishing lines.",
        "description": (
            "Tooling and manufacturing expertise for steel and metal \u2014 fiber and tube laser "
            "cutters, optical loading and unloading, laser welders and cleaners, and CNC machines."
        ),
        "details": [
            (
                "Our customer focus stays aligned with steel and metal: tooling and manufacturing "
                "expertise deliver breakthrough solutions that change traditional technologies "
                "\u2014 through fiber laser cutters, tube laser cutters, optical loading and "
                "unloading solutions, laser welder and cleaner, and CNC machines."
            ),
        ],
        "image": "images/products/client-steel.webp",
        "alt": "Steel coils and surface finishes",
        "scope": [
            "Fiber laser cutters",
            "Tube laser cutters",
            "Optical loading & unloading",
            "Laser welder & cleaner",
            "CNC machines",
            "Tooling & manufacturing",
        ],
    },
    {
        "slug": "pharma-biotech",
        "name": "Pharma & Biotech",
        "tagline": "Science in our hands, health in our mission.",
        "short": "Process equipment and cleanroom systems for regulated production.",
        "description": (
            "A one-stop solution for pharmaceutical and biopharmaceutical production, with "
            "integrated engineering and equipment built for quality and compliance."
        ),
        "details": [
            (
                "To become the ultimate one-stop solution for pharmaceutical and biopharmaceutical "
                "production, we bring innovative and comprehensive solutions that drive growth and "
                "excellence. We aim to empower our clients to achieve sustainable success and "
                "enhance the quality of life for people."
            ),
            (
                "Our commitment to quality and innovation provides cutting-edge biopharmaceutical "
                "equipment and integrated pharmaceutical engineering solutions \u2014 "
                "anti-counterfeiting and brand protection solutions; thermal solutions for the "
                "transportation, handling and storage of thermo-sensitive products; leak detection "
                "and visual inspection; and technology for transdermal patches and oral films."
            ),
        ],
        "image": "images/products/client-pharma.webp",
        "alt": "Laboratory instrument for pharmaceutical analysis",
        "scope": [
            "Biopharmaceutical equipment",
            "Integrated pharma engineering",
            "Anti-counterfeiting & brand protection",
            "Thermal solutions",
            "Leak detection & visual inspection",
            "Transdermal patches & oral films",
        ],
    },
]


def products(request):
    return render(request, "core/products.html", {"sectors": PRODUCT_SECTORS})


def product_detail(request, slug):
    """One sector's page; unknown slugs are a 404, not a redirect."""
    sector = next((s for s in PRODUCT_SECTORS if s["slug"] == slug), None)
    if sector is None:
        raise Http404("Not found")
    return render(
        request,
        "core/product_detail.html",
        {"sector": sector, "sectors": PRODUCT_SECTORS},
    )


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
