"""Legacy-page full-text index (Phase 8).

The 51 mirrored pages are static files; we keep the searchable text in memory
and refresh it at most once per process (module-level cache). Everything is
read-only and safe: titles/text are plain strings, escaped in the template.

Accuracy contract (tested): matching is case-insensitive; a term matching a
page <title> or the slug ranks above pure body matches; body matches are
pretty-printed with a short surrounding snippet, tags stripped.
"""
import re
from functools import lru_cache
from html import unescape

from django.conf import settings

from .sanitize import sanitize

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
MAX_TEXT_CHARS = 400_000  # per page; body text beyond this is ignored


def _strip(raw_html: str) -> str:
    """Sanitized (third-party-free) page → visible text only."""
    html = sanitize(raw_html)
    html = re.sub(r"<(script|style|noscript)\b.*?</\1>", " ", html, flags=re.I | re.S)
    text = unescape(TAG_RE.sub(" ", html))
    return WS_RE.sub(" ", text).strip()[:MAX_TEXT_CHARS]


@lru_cache(maxsize=1)
def load_index():
    """[(slug, title, text)] for every legacy page, loaded once per process."""
    legacy_dir = settings.BASE_DIR / "legacy"
    entries = []
    for path in sorted(legacy_dir.glob("*.html")):
        slug = path.stem
        if not re.match(r"^[a-z0-9][a-z0-9-]{0,99}$", slug):
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        title_match = re.search(r"<title>(.*?)</title>", raw, re.I | re.S)
        title = unescape(WS_RE.sub(" ", title_match.group(1))).strip() if title_match else slug
        entries.append((slug, title, _strip(raw)))
    return entries


def search_text(query: str, limit: int = 20):
    """Search the legacy corpus. Returns [{slug,title,url,snippet,kind}]."""
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
