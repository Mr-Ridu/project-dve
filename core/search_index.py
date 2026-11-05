"""Content-page full-text index.

The searchable text comes from core.site_pages (the content registry). It is
plain data, kept in memory and read-only: titles/text are plain strings,
escaped in the template.

Accuracy contract (tested): matching is case-insensitive; a term matching a
page title or the slug ranks above pure body matches; body matches are shown
with a short surrounding snippet.
"""
from functools import lru_cache

from .site_pages import PAGES

# The main pages are Django templates rather than registry entries, but they
# should still be findable. Tutorials are searched separately by the view.
EXTRA_PAGES = [
    (
        "products",
        "Products and industrial systems",
        "Equipment and systems for industrial plant and machinery, energy and "
        "power, robotic automation, steel and metal, and pharma and biotech. "
        "Installation, spares and technical support.",
    ),
    (
        "about",
        "About Techno Mate Technologies",
        "Who we are, the five industrial sectors we supply, and how we specify, "
        "install and support equipment in Bangladesh.",
    ),
    (
        "services",
        "Service and support",
        "Installation, preventive maintenance, genuine spares and technical "
        "support for the industrial equipment we supply.",
    ),
    (
        "contact",
        "Contact Techno Mate Technologies",
        "Dhaka and Chattogram offices, phone numbers and email for product "
        "enquiries and support.",
    ),
    (
        "tutorials",
        "Tutorial library",
        "Video tutorials covering installation, operation and maintenance of "
        "our industrial equipment.",
    ),
]


@lru_cache(maxsize=1)
def load_index():
    """[(slug, title, text)] for every searchable page, loaded once per process."""
    entries = list(EXTRA_PAGES)
    for slug, page in PAGES.items():
        entries.append((slug, page["title"], " ".join(page["paragraphs"])))
    return entries


def search_text(query: str, limit: int = 20):
    """Search the content pages. Returns [{slug,title,snippet,score}]."""
    query = query.strip()
    if not query:
        return []
    q = query.lower()
    terms = q.split()
    results = []
    for slug, title, text in load_index():
        haystack_title = f"{title} {slug.replace('-', ' ')}".lower()
        positions = [text.lower().find(t) for t in terms]
        body_hits = [p for p in positions if p >= 0]
        title_hit = any(t in haystack_title for t in terms)
        if not title_hit and not body_hits:
            continue
        if body_hits:
            i = body_hits[0]
            start = max(0, i - 60)
            snippet = ("…" if start else "") + text[start:i + 160] + "…"
        else:
            snippet = text[:200] + ("…" if len(text) > 200 else "")
        score = (2 if title_hit else 0) + (1 if len(body_hits) == len(terms) else 0)
        results.append({"slug": slug, "title": title, "snippet": snippet, "score": score})
    # Equal-score ties: a shorter title is the more on-point page (e.g. the
    # "SARRP" landing page over the long SARRP-education-series article).
    results.sort(key=lambda r: (-r["score"], len(r["title"]), r["slug"]))
    return results[:limit]
