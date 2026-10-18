# Phase 1 — Inspection Report & Architecture Plan

**Project:** Django Medical Equipment Portfolio & Secure Training Tutorial Website
**Source material:** static HTTrack mirror of xstrahl.com, rebranded "Techno Mate Technologies"
**Date:** 2026-10-18 · **Status:** inspection complete — **no project files were modified** (this document is the only addition)

> Conventions used below: **[VERIFIED]** = measured/observed directly in this workspace. **[ASSUMED]** = not yet verified, needs your confirmation. **[EXTERNAL]** = from published documentation read during this phase (sources listed at the end).

---

## 1. Existing project structure

```
Xstrahl Clone/                     (workspace root = future Django project root)
├── .freebuff/          1 KB   workspace metadata — exclude from deployment  [VERIFIED]
├── templates/          19 MB  56 flat HTML pages (the whole site, one file per page)  [VERIFIED]
└── static/            166 MB  all shared assets  [VERIFIED]
    ├── css/          135 files,  3.0 MB
    ├── js/            44 files,  3.0 MB
    ├── fonts/        118 files,  8.2 MB
    ├── images/       441 files, 112.9 MB
    ├── documents/     15 files, 43.8 MB (PDFs linked from pages)
    └── (videos/ removed — was empty)
```

- **No Django project exists.** No `manage.py`, no `*.py`, no `requirements.txt` anywhere in the project. [VERIFIED]
- Pre-rebrand backups of earlier work live in the system temp folder **outside** the project (templates backup, removed-assets backup). [VERIFIED]

**Development environment** [VERIFIED]

| Item | Value |
|---|---|
| Default Python | 3.14.0 (`python`) |
| Also installed | Python 3.12 (64-bit, via `py -V:3.12`) |
| Django | 5.2.17 installed and importable |
| pip | 25.2 |

Recommendation: build in a **Python 3.12 virtualenv with Django 5.2 LTS** — 3.12 is what shared hosts commonly offer, and Django 5.2 is the LTS line supporting Python 3.10–3.14. [EXTERNAL: Django 5.2 release notes]

---

## 2. Template and asset inventory

### 2.1 The 56 pages [VERIFIED]

**Core public pages (your required five — all exist):** `index` (Home), `about`, `product-information` (Products), `service-support` (Services), `contact-us` (Contact).

**Product/technology pages:** `xstrahl-100`, `xstrahl-150`, `xstrahl-200`, `xstrahl-300`, `radiant`, `sarrp`, `sarrp-beamline`, `sarrp-flash`, `sarrp-flash` research pages, `smart-rad-overview`, `xenx`, `cabinet-irradiators`, `image-guided-irradiators`, `clinical-systems`, `cix-flash`, `cix2`, `cix3`.

**Condition/education pages:** `benign-conditions`, `benign-hyperproliferative-diseases`, `non-melanoma-skin-cancer-nmsc`, `skin-cancer`, `palliative-applications`, `palliative-care`, `history-of-x-rays`, `for-patients`, `vet`, `radiation-research`, `sarrp-education-and-training-series`, `nmsc-webcast`, `characterization-and-biological-validation-of-photon-flash`, `introducing-the-sarrp-education-series-…`, `xstrahl-marks-30-years-…`.

**Resource/news:** `blog`, `news`, `case-studies`, `publications`, `presentations`, `research-reviews`, `user-spotlights`, `events`, `careers`, `category-type-pres`, `search`, `404`.

**Legal:** `privacy-policy`, `cookie-policy`, `legal-notices`, `impressum`, `agb`, `terms-conditions`, `accessibility-statement`.

### 2.2 Front-end stack [VERIFIED]

- **Divi (WordPress theme) markup** — `et_pb_*` modules on 56/56 pages. This is a WordPress→HTML mirror, not a hand-written site.
- **jQuery** on 56/56 pages, plus: MediaElement.js (video player), Magnific Popup, EasyPieChart, Salvattore (grid), FitVids, Formidable Forms JS (`frm.min.js`), DiviArea (popups), Divi motion-effects/sticky-elements, GTranslate widget, WP Accessibility, `ruleJS.lib.full.js` (0.7 MB spreadsheet lib).
- **No Bootstrap. No Tailwind** (the string "tailwind" appears nowhere; earlier class-pattern hits were Divi false positives). Styling is Divi's own CSS + WordPress plugin CSS.

### 2.3 Code volume and duplication [VERIFIED]

| Signal | Measurement |
|---|---|
| Page size | avg **327 KB/page**, largest 372 KB |
| Inline `<style>` | **466 blocks, 12.4 MB total** (per-page Divi dynamic CSS embedded inline) |
| Inline `<script>` | **1,983 blocks, 1.4 MB**; 283 distinct bodies, 8 of which repeat on all 56 pages |
| Header/footer regions | byte-unique per page (per-page injected CSS/JS differs), but **structurally identical** — the nav, industry strip, mobile menus, footer columns, newsletter popup and back-to-top are the same components repeated 56× |
| Near-duplicate assets | 14 basenames with HTTrack `-2` copies; 52 per-page `et-divi-dynamic-*` cache stylesheets |
| Fonts | 118 files ≈ 51 families (Sofia Pro, Objektiv Mk1, Montserrat, Playfair, PT Sans, FontAwesome, Divi modules…) |
| Images | 441 files; **largest single PNG is 18.7 MB**; several 3–4 MB PNGs |
| Documents | 15 linked PDFs, 43.8 MB (largest 14.6 MB) |

**Conversion implication:** the header/footer/mobile-menu/newsletter-popup shells will be extracted into Django partials; the 12.4 MB of inline page CSS will be lifted into static stylesheets per page-group (this is the main performance lever).

### 2.4 Links, hardcoded paths, broken references [VERIFIED]

- **6,853 internal links** → 55 distinct targets resolve to existing pages; **116 distinct targets are missing** (never mirrored: mostly blog/news posts like `/rt-101/`, `/aad-2026-news/`, category pages, plus HTTrack pagination artifacts like `../index4086.html`). Top miss is linked 67×.
- **External hosts referenced: 1,037 × `xstrahl.com`** (hotlinked images, fonts, CSS, links), `www.elegantthemes.com` 112, `www.youtube.com` 67 (public embeds), `player.vimeo.com` 4, `use.typekit.net` 1 (Adobe Fonts CSS), **`app.jazz.co` — third-party chat widget loaded as an external `<script>`**, `desk.zoho.com` (support form), `bat.bing.com` (tracking pixel), plus license-comment URLs (yoast, gnu.org, daneden.me, opensource.org, get.adobe.com — harmless).
- **All internal asset paths are root-absolute `/static/…`** — straightforward to convert to `{% static %}`. [VERIFIED]
- **Forms** [VERIFIED]: 58 search forms `action='/'` (non-functional), 124 forms with no action (Formidable JS posts to `xstrahl.com/wp-admin/admin-ajax.php`), **9 blog-search forms posting to `https://xstrahl.com/blog/`**, **1 support form posting to `https://desk.zoho.com/support/WebToCase` (the original company's Zoho desk)**.

### 2.5 Accessibility signals [VERIFIED]

81 `<img>` tags without `alt`; 10 pages with **no `<h1>`**; 3 pages with multiple `<h1>`s. Mobile overflow (~44 px) exists on some pages from a hidden sub-menu. Good news: the site is already responsive (breakpoints verified during earlier work) and keyboard focus styling exists in the Divi CSS but is inconsistent.

---

## 3. Recommended Django app structure

Adapting your sketch to this repository (existing `templates/` and `static/` names are reused, not duplicated):

```
Xstrahl Clone/
├── manage.py
├── requirements.txt            # Django==5.2.*, mysqlclient/PyMySQL, gunicorn, whitenoise (optional)
├── config/                     # settings/{base,dev,prod}.py, urls.py, wsgi.py
├── core/                       # public pages: home, about, products, services, contact + legacy catch-all
├── accounts/                   # custom user model, registration, approval, login, audit log
├── tutorials/                  # categories, tutorials, access grants, progress, playback authorization
├── dashboard/                  # staff dashboard views (reuses Django admin where sufficient)
├── templates/                  # Django templates (base.html + partials + app templates)
│   ├── base.html
│   ├── partials/               # header, nav+mega-menu, industry strip, mobile menus, footer, newsletter popup
│   ├── core/  accounts/  tutorials/  dashboard/
├── static/                     # EXISTING assets — unchanged, referenced via {% static %}
├── media/                      # public uploads only (thumbnails) — NEVER private video
├── legacy/                     # the 56 original mirrored pages, kept as read-only design reference
└── docs/                       # this report
```

- The existing 56 mirrored pages move to `legacy/` at the start of Phase 3 (a rename — **requires your approval**, nothing is deleted).
- A `core.views.legacy_page` catch-all keeps the 51 non-core pages working at their original URLs until you choose to convert or retire them. [ASSUMED — needs approval]

## 4. Proposed URL structure

| URL | Name | Source template |
|---|---|---|
| `/` | `core:home` | `index.html` |
| `/about/` | `core:about` | `about.html` |
| `/products/` | `core:products` | `product-information.html` |
| `/products/<slug>/` | `core:product_detail` | `xstrahl-100` … `xenx` etc. |
| `/services/` | `core:services` | `service-support.html` |
| `/contact/` | `core:contact` | `contact-us.html` |
| `/events/`, `/resources/…` | `core:legacy_page` (catch-all) | remaining 51 pages, original slugs preserved |
| `/accounts/register/` `/login/` `/logout/` `/pending/` | `accounts:*` | new |
| `/tutorials/` | `tutorials:catalog` | new |
| `/tutorials/<slug>/` | `tutorials:detail` | new |
| `/tutorials/<slug>/playback/` | `tutorials:playback` | new — issues short-lived signed playback URL |
| `/progress/<slug>/` | `tutorials:progress` | new (POST, AJAX) |
| `/dashboard/…` | `dashboard:*` | new (staff-only) |
| `/admin/` | — | Django admin |

All internal links converted to `{% url %}`; original slugs preserved wherever a page already exists.

## 5. Authentication and permission architecture

**Decision point — two viable designs:**

- **Option A (recommended): custom user model** `accounts.User(AbstractUser)` with `approval_status ∈ {pending, approved, rejected}`, `approved_by/at`, `access_all_tutorials` flag. Standard Django guidance for a greenfield project; must be defined **before the first migration**. Still entirely built-in `django.contrib.auth` machinery (forms, views, permissions, admin) — not a custom auth system.
- **Option B: stock `auth.User` + `accounts.Profile`** (OneToOne with the same fields). Zero migration-order risk, slightly clunkier checks.

**Lifecycle (either option):** register → account created `pending` → user **may log in** but sees a clear "awaiting approval" state and no tutorial access → staff reviews in dashboard → approve/reject (audit-logged) → approved + active users get tutorial access **only per the permission rules below**. Staff-only approval controls; no self-service approval path anywhere.

**Security mechanics:** CSRF on all state changes; logout POST-only (Django 5.x default); password validators; `next` redirects validated with `url_has_allowed_host_and_scheme`; cache-based login/register throttling (or `django-axes` if you accept the dependency); every authorization decision made server-side in a single shared predicate — never in templates, buttons, or query params.

## 6. Tutorial permission model

```
Category(name, slug, ordering)
Tutorial(title, slug, description, thumbnail, category FK, duration_seconds,
         video_provider, video_ref, is_published, ordering, estimated_minutes,
         created_at, updated_at)
TutorialAccess(user FK, tutorial FK, granted_by, granted_at)  unique(user, tutorial)
TutorialProgress(user FK, tutorial FK, seconds_watched, percent,
                 completed, completed_at, last_seen_at)      unique(user, tutorial)
AuditEvent(actor, action, target_type, target_id, timestamp, ip)
```

**Access predicate** — `can_access(user, tutorial)`, enforced on **every** protected request (page view *and* playback token):

> authenticated **and** `is_active` **and** `approval_status == approved` **and** `tutorial.is_published` **and** (`user.access_all_tutorials` **or** a `TutorialAccess` row exists)

- Global approval does **not** grant everything unless an admin sets `access_all_tutorials` on that user (explicit admin action, default off).
- Revocation = deleting the grant row; the very next request is denied because checks happen per-request.
- Slug/ID tampering is useless: the predicate is evaluated against the resolved object.
- Listing pages *hide* what you can't open, but hiding is cosmetic — the backend re-checks always.
- Progress/watched state is never treated as proof of authorization.

## 7. Database strategy (SQLite → MySQL)

- Dev: SQLite. Prod: MySQL 8.0.11+ or MariaDB 10.5+ (Django 5.2 supported backends) [EXTERNAL: Django DB docs].
- Config entirely env-driven (`DB_ENGINE/DB_NAME/DB_USER/DB_PASSWORD/DB_HOST/DB_PORT`); no SQLite-specific features in app code (`JSONField` is fine on both; avoid SQLite-only lookups); schema only through migrations.
- **Migration procedure (documented fully in Phase 10):** freeze code → backup SQLite file → `migrate` on MySQL (utf8mb4 / `utf8mb4_unicode_ci`) → `dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.permission -e sessions` → `loaddata` → verify counts + smoke tests → switch env → rollback plan = keep the SQLite file and the old env value.
- Never switch production DB config automatically.

## 8. Video hosting & protected playback — options (decision deferred to Phase 6)

**Honest baseline:** no HTML player can prevent screen recording or re-photographing a screen. Signed URLs are *bearer links* — anyone holding one can view until it expires. DRM raises the bar (supported devices only) but is not absolute. HLS requires protecting **every** manifest and segment, not just the master playlist.

### Option A — Private object storage + short-lived signed URLs
| | |
|---|---|
| Services | AWS S3+CloudFront (signed URLs/cookies), Backblaze B2 ($6.95/TB/mo, free egress ≤3× stored), Cloudflare R2 ($0.015/GB-mo, free egress, presigned 1s–7 days), Wasabi ($7.99/TB/mo, 1 TB minimum) |
| Security | Good — private bucket + short expiry; no DRM |
| Adaptive streaming | Only if HLS is packaged manually (all files must be signed/cookie-protected) |
| cPanel fit | Excellent — Django only signs URLs |
| Complexity | Medium · Cost: very low at this scale |

### Option B — Managed video platforms with signed playback
| | Pricing (current public) | Notes |
|---|---|---|
| **Cloudflare Stream** | $5 per 1,000 min stored + $1 per 1,000 min delivered (≈$10/mo for a 20 h library) | HLS/DASH, signed tokens (1 h default expiry), no DRM |
| **Bunny Stream** | $0.01/GB storage + $0.005/GB delivery, $1/mo minimum | Embed + CDN tokens cover playlists/segments; DRM add-on $99/mo |
| **Mux** | $0.0024/stored min (≤720p) + $0.0008/delivered min, 100k free delivery min/mo | Signed playback JWTs; DRM $100/mo |
| **VdoCipher** | Paid tiers not verifiable from the public page (trial: 5 GB / 4 videos) | DRM + dynamic watermark — strongest copy-deterrence for medical training content |
| **Vimeo** | Tier pages dynamic, unverified | Domain-privacy ≠ per-user auth; DRM is Enterprise-only |

### Option C — Protected delivery from the cPanel host itself
Django `FileResponse` streaming works but **ties up a Passenger/LiteSpeed worker per viewer** (typical shared limits ≈1 CPU, 1 GB RAM, ~20 entry processes) [EXTERNAL: CloudLinux limits], needs manual Range support for seeking, no adaptive streaming. `mod_xsendfile`/X-Accel-Redirect is **not verified as available** on shared cPanel [EXTERNAL: cPanel docs don't promise it]. Verdict: prototype-only; don't build the product on it.

**Shortlist I'll bring to you with full detail at Phase 6:** Bunny Stream or Cloudflare Stream (managed + signed, ~$1–10/mo) for the practical path; R2/B2 + presigned URLs for lowest cost; VdoCipher if watermarking/DRM is required for medical training material. **No provider will be chosen or purchased without your explicit approval.**

## 9. cPanel deployment — compatibility & limitations [EXTERNAL, provider-dependent]

| Area | Finding |
|---|---|
| Runtime | cPanel "Setup Python App" = **Passenger WSGI** (`passenger_wsgi.py`). **ASGI/WebSockets unsupported** on shared hosting (e.g. Namecheap states this explicitly) |
| Python | Host-selected (Namecheap currently 3.11–3.13); **confirm your host's list before Phase 2 freezes versions** |
| Static | `collectstatic` → web-served directory (e.g. `public_html/static`), or WhiteNoise. WhiteNoise must **not** serve private media |
| Private media | If a media dir is web-mapped, **Apache/LiteSpeed serves it directly — Django auth never runs**. Private files must live outside the document root behind an auth-aware route, or at the video provider |
| Secrets/env | cPanel app env-vars UI (needs `ea-apache24-mod_env`) or an app-loaded `.env` outside the docroot; `SECRET_KEY` from env, `DEBUG=False`, `ALLOWED_HOSTS` set |
| DB | MySQL 8.0.11+/MariaDB 10.5+ via cPanel Database Wizard; versions vary by host |
| Background work | cPanel **cron** for bounded management commands. **No Celery/long-running workers** in practice |
| HTTPS | AutoSSL/Let's Encrypt typically available; secure cookies required |
| Limits | CloudLinux LVE reference: 1 CPU, 1 GB RAM, ~20 entry processes, ~100 processes; LiteSpeed `LSAPI_CHILDREN` default 6 — long streams starve the app |

**Deployment guides (production settings, env vars, WSGI, collectstatic, migrations, superuser, backups, logs) are a Phase 10 deliverable.** Before committing, obtain from your host in writing: Python versions, MySQL version, body-size/upload limits, Passenger process/memory limits, cron restrictions, and whether `mod_xsendfile` exists.

## 10. Security risks found (current state → planned mitigation)

| # | Risk [VERIFIED unless noted] | Mitigation |
|---|---|---|
| 1 | **Contact/support forms post to third parties** — `xstrahl.com/admin-ajax.php` (124 forms), `xstrahl.com/blog/` (9), **Zoho WebToCase of the original company** (1). Submissions leak to strangers | Remove/repoint in Phase 3; Django forms with CSRF, no third-party endpoints |
| 2 | **1,037 live references to xstrahl.com** (images/fonts/CSS) + external `<script>` from `app.jazz.co` + Adobe typekit CSS — availability, privacy and supply-chain exposure | Mirror/replace in Phase 3; no third-party scripts in production |
| 3 | Bing tracking pixel (`bat.bing.com`) from the original site | Remove in Phase 3 |
| 4 | Search is non-functional (`/?s=…`); 116 dead internal links; 6 missing assets (404s) | Django search view in Phase 8; dead links pruned/mapped in Phase 3 |
| 5 | 81 images w/o alt; 10 pages w/o h1; 3 with multiple h1; ~44px mobile overflow | Accessibility pass in Phase 9 |
| 6 | Performance: 12.4 MB inline CSS, 18.7 MB PNG, 327 KB/page | Extract CSS to static files (Phase 3), image optimization (Phase 9) |
| 7 | Django production hygiene [ASSUMED to implement] | Env-based `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, HTTPS + secure/`SameSite` cookies, CSRF, throttling on auth endpoints, upload type/size limits, audit log for approvals & permission changes, no secrets/private media in version control or docroot |

I will not claim "production-secure" merely because the site runs; a Phase 9 security checklist run is planned.

## 11. Implementation plan (phased, each phase ends runnable + tested)

| Phase | Content | Key tests |
|---|---|---|
| **2** | venv (Py 3.12) + Django 5.2 LTS, `config/` with split settings, env-driven DB, app scaffolds, `requirements.txt`, move mirrored pages → `legacy/` *(approval needed)*, git checkpoint | `manage.py check`, migrations apply, empty test suite green |
| **3** | `base.html` + partials (nav/mega-menu, industry strip, mobile menus, footer, newsletter popup); Home, About, Products, Services, Contact converted with `{% static %}`/`{% url %}`; legacy catch-all for remaining 51; strip third-party forms/scripts/pixels | 200s for 56 URLs, templates render, static resolves, no external requests |
| **4** | Custom user model + registration/login/logout + approval lifecycle + throttling + audit log | Full auth security suite (registration→pending, anonymous/pending/rejected denied, safe redirects, CSRF) |
| **5** | Tutorial models + catalog + per-tutorial grants + playback-authorization endpoint (provider-agnostic) | Permission matrix: published/unpublished × granted/revoked × approved/pending/rejected; slug-tamper attempts denied |
| **6** | **STOP: video hosting presentation + your approval**, then provider integration | Signed URL issuance only after all checks; revocation blocks new tokens |
| **7** | Staff dashboard: user mgmt, approvals, tutorial CRUD, grants, progress summaries | Ordinary users blocked from every dashboard action; no self-approval paths |
| **8** | Search, categories, watched/progress/completion | Filtering/search accuracy; progress never widens access |
| **9** | Full test suite, a11y checks (alt/headings/labels/focus), responsive checks, security review | Everything green or reported honestly |
| **10** | cPanel deployment guide + SQLite→MySQL migration guide | Docs reviewed; no real credentials anywhere |

Dependency note: **Phase 6 sits between 5 and 7** exactly as your brief specifies — the playback endpoint in Phase 5 is provider-agnostic so no rework is needed when you choose.

## 12. Verified facts vs assumptions — summary

**Verified:** full tree and sizes; 56 pages and their names; stack (Divi/jQuery, no Bootstrap/Tailwind); code volumes; link graph incl. 116 dead targets; external dependencies incl. third-party form endpoints and scripts; a11y counts; no Django/Python code present; Python 3.14 + 3.12 installed; Django 5.2.17 importable.

**Assumptions needing your input:** which cPanel host (their Python/MySQL/LiteSpeed specifics); Option A vs B for the user model; whether pending users may log in (proposed: yes, with a clear pending state); whether the 51 legacy pages may be served via catch-all until converted; video budget/preference (deferred to Phase 6).

## 13. Sources

cPanel/CloudLinux/Django docs (Python WSGI setup, Application Manager, Python Selector, LVE limits, DB wizard, cron, AutoSSL, Django 5.2/6.0 release notes, DB & static-file & deployment-checklist docs, WhiteNoise), provider docs (Namecheap software list, LiteSpeed CloudLinux setup), video provider pricing/security docs (CloudFront signed URLs/cookies, B2, R2 presigned URLs, Wasabi terms, Cloudflare Stream, Bunny Stream, Mux, VdoCipher, Vimeo privacy/DRM), mod_xsendfile, Celery worker docs. Full URLs are recorded in the session research log.
