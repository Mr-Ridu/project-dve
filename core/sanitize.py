"""Server-side sanitization for all HTML served to visitors.

Strips the former owner's trackers and third-party endpoints and repoints
outbound form submissions to a local stub (Phase 3 security items 1-3 in
docs/PHASE1_INSPECTION_REPORT.md). Used by the legacy catch-all view, by the
template generator and by tests — one place, one policy.

Design notes:
- <script> blocks are judged individually and never removed across block
  boundaries, so a tracker removal can never swallow neighbouring scripts.
- Comment rules match a single complete comment, so they also work on
  tokenised head fragments where the opening/closing pair is split apart.
"""
import re

STUB = "/forms/placeholder/"

# --- whole-comment removal (safe at any granularity) ------------------------
_COMMENT = [
    (re.compile(r"<!--\s*(?:End\s+)?Meta Pixel[^>]*-->", re.I), ""),
    (re.compile(r"<!--\s*Google tag\b[^>]*-->", re.I), ""),
    (re.compile(r"<!--\s*FB domain verification[^>]*-->", re.I), ""),
]

# --- element removal --------------------------------------------------------
_LINK_DROP = re.compile(
    r"<link\b[^>]*href=[\"'][^\"']*(?:use\.typekit\.net|googletagmanager|desk\.zoho\.com)[^\"']*[\"'][^>]*>",
    re.I,
)
_META_DROP = re.compile(r"<meta\b[^>]*facebook-domain-verification[^>]*>", re.I)
_SRC_DROP = re.compile(
    r"<script\b[^>]*src=[\"'][^\"']*(?:app\.jazz\.co|bat\.bing|uet-tag\.js|facebook_signal\.js)[^\"']*[\"'][^>]*>\s*</script>",
    re.S | re.I,
)

# --- per-block script filtering --------------------------------------------
_SCRIPT_BLOCK = re.compile(r"<script\b[^>]*>.*?</script>", re.S | re.I)
_BAD_SCRIPT = re.compile(
    r"admin-ajax\.php|app\.jazz\.co|bat\.bing|uet-tag\.js|facebook_signal"
    r"|FacebookSignal|runPixelCode|desk\.zoho\.com|googletagmanager|gtag\(|Meta Pixel",
    re.I,
)


def _script_filter(match):
    """Drop script blocks that reference trackers or third-party endpoints."""
    return "" if _BAD_SCRIPT.search(match.group(0)) else match.group(0)


# --- form retargeting -------------------------------------------------------
_FORM_TAG = re.compile(r'''<form\b(?:[^>"']|"[^"]*"|'[^']*')*>''', re.I)
_ACTION = re.compile(r"\baction=[\"']([^\"']*)[\"']", re.I)


def _retarget_form(match, for_template):
    """Point action-less or externally-posting forms at the local stub.

    Raw legacy HTML cannot carry Django CSRF tokens, so its forms submit by
    GET to the stub. Django templates get a real POST target plus
    {% csrf_token %} so state-changing requests are CSRF-protected.
    """
    tag = match.group(0)
    action = _ACTION.search(tag)
    external = bool(action) and action.group(1).startswith(("http://", "https://", "//"))
    if action and not external:
        return tag  # already local (e.g. the search form) — leave untouched
    if for_template:
        new_tag = _ACTION.sub("", tag) if action else tag
        new_tag = new_tag.replace("<form", '<form action="{% url \'core:form-placeholder\' %}"', 1)
        if not re.search(r"\bmethod=", new_tag, re.I):
            new_tag = new_tag.replace("<form", '<form method="post"', 1)
        return new_tag + "\n{% csrf_token %}"
    new_tag = _ACTION.sub(f'action="{STUB}"', tag) if action else tag.replace("<form", f'<form action="{STUB}"', 1)
    new_tag = re.sub(r"\bmethod=[\"']post[\"']", 'method="get"', new_tag, flags=re.I)
    if not re.search(r"\bmethod=", new_tag, re.I):
        new_tag = new_tag.replace("<form", '<form method="get"', 1)
    return new_tag



# --- legacy-only neutralizers -----------------------------------------------
# HTTrack saved some gradient layers as .html and some SVG font fallbacks as absolute
# legacy-host URLs. They are inert (browser 404s them) but must never leave the wire.
_KXCDN_LAYER = re.compile(r"url\([^)]*(?:xstrahl-9f3e\.kxcdn\.com|xstrahl\.com)/[^)]*\),?")
_ETMODULES_SVG = re.compile(
    r",?url\(//xstrahl\.com/wp-content/themes/Divi/core/admin/fonts/modules/"
    r"(?:all|social)/modules\.svg#ETmodules\) format\(\"svg\"\)"
)

# --- URL-level fixes (belt and braces for anything outside scripts) ---------
_URL_FIXES = [
    (re.compile(r"https?://desk\.zoho\.com[^\"'\s<]*"), STUB),
    (re.compile(r"https:\\\\/\\\\/xstrahl\.com\\\\/wp-admin\\\\/admin-ajax\.php"), STUB),
    (re.compile(r"https://xstrahl\.com/wp-admin/admin-ajax\.php"), STUB),
]


def sanitize(html, for_template=False):
    """Return HTML with third-party endpoints and trackers removed.

    for_template=True additionally rewrites forms for use inside a Django
    template (adds {% csrf_token %}); raw legacy HTML must use False.
    """
    for pat, rep in _COMMENT:
        html = pat.sub(rep, html)
    html = _SCRIPT_BLOCK.sub(_script_filter, html)
    html = _SRC_DROP.sub("", html)
    html = _LINK_DROP.sub("", html)
    html = _META_DROP.sub("", html)
    html = _ETMODULES_SVG.sub("", html)
    html = _KXCDN_LAYER.sub("", html)
    for pat, rep in _URL_FIXES:
        html = pat.sub(rep, html)
    html = _FORM_TAG.sub(lambda m: _retarget_form(m, for_template), html)
    return html
