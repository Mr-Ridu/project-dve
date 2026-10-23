# Phase 9 — Accessibility, responsive, performance and security review

Phase 9 of the plan (`docs/PHASE1_INSPECTION_REPORT.md` §11) is the quality gate:
full test suite, accessibility checks (alt/headings/labels/focus), responsive
checks, image optimisation, and the security checklist from §12 item 7.

Everything below was **measured**, not assumed. Where a check could not be run,
that is stated explicitly rather than counted as a pass.

---

## 1. Method

* **Markup/ARIA audit** — every converted page fetched through the Django test
  client and parsed with `html.parser`; the invariants are now tests in
  `core/tests_phase9.py` (`AccessibilityInvariants`).
* **Rendered layout audit** — a real Chromium session against the dev server at
  a 375x812 mobile viewport and a 1280x900 desktop viewport; horizontal overflow
  measured as `documentElement.scrollWidth` versus `clientWidth`, with the
  offending elements listed by their right edge.
* **Security review** — `manage.py check --deploy` with the production settings
  module, plus subprocess tests that prove the production profile fails closed
  (`ProductionSettingsTests`) and upload validation tests
  (`UploadValidationTests`).

Reproduce:

```bash
python manage.py test                 # full suite, includes Phase 9
python manage.py test core.tests_phase9
DJANGO_SECRET_KEY=x*50 DJANGO_ALLOWED_HOSTS=example.com \
  DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py check --deploy
python manage.py optimize_images --dry-run
```

---

## 2. Accessibility — issues found and fixed

| # | Issue | Standard | Fix | Verified |
|---|---|---|---|---|
| 1 | `viewport` set `maximum-scale=1.0, user-scalable=0`, blocking pinch-zoom | WCAG 1.4.4 | Removed both directives from `templates/base.html` | Test asserts the meta tag, and every page's rendered meta, contains neither |
| 2 | Divi's reset sets `:focus{outline:0}` with no replacement — keyboard focus was invisible site-wide | WCAG 2.4.7 | `static/css/site-a11y.css` restores a 3px `#8a4d9f` ring on all interactive elements, loaded after the theme; pointer users keep the original look via `:focus:not(:focus-visible)` | CSS present and loaded last (asserted); interactive ring **not** measurable — see §6 |
| 3 | No skip link (the "skiplinks" markup only existed inside the stripped WordPress JS config) | WCAG 2.4.1 | Server-rendered `<a class="skip-to-content" href="#site-main">` as the first element in `<body>`, revealed on focus | Asserted on all 9 audited pages |
| 4 | No `main` landmark; content block sat directly in the page container | WCAG 1.3.1 / 2.4.1 | Content block wrapped in `<main id="site-main" tabindex="-1">` (also the skip-link focus target) | Asserted |
| 5 | `/products/` had **no `h1`** — its headings were all `h2` slide titles | WCAG 1.3.1 | Screen-reader-only `<h1>Product Information</h1>`; no visual change | Test asserts exactly one `h1` per page |
| 6 | Header search input had no accessible name (`placeholder` only), appearing on every page | WCAG 4.1.2 / 3.3.2 | `aria-label="Search the site"` on all three header search fields | Asserted |
| 7 | `/products/` filter selects (4) unlabelled | WCAG 4.1.2 | `aria-label` on each (`Filter by resource type/area/product/condition`) | Asserted (no unlabelled controls on any audited page) |
| 8 | Site search field used placeholder as its only label | WCAG 3.3.2 | Visually hidden `<label for="site-search">` | Asserted |
| 9 | Dashboard user filter input + status select unlabelled | WCAG 4.1.2 | Visually hidden labels, `for`/`id` pairs | Asserted |
| 10 | Dashboard table headers had no `scope` | WCAG 1.3.1 | `scope="col"` on all `<th>` | Asserted |
| 11 | Footer logo link contained only an image with `alt=""` — the link had no accessible name | WCAG 2.4.4 / 4.1.2 | `alt="Techno Mate Technologies logo"` | Asserted (no image lacks `alt`) |
| 12 | Video iframe was created by JS with no accessible name | WCAG 4.1.2 | `iframe.title = "Tutorial video: " + document.title` | Asserted in the template source |
| 13 | Fixed header could cover an anchored target after a skip link | WCAG 2.4.1 (usability) | `scroll-margin-top: 90px` on anchor targets | Visual/CSS only |

Notes on what was deliberately **not** changed:

* Icon images and staff photos keep `alt=""` where adjacent text already names
  them — they are decorative in context, and forcing alt text would make screen
  readers repeat the same label twice.
* The legacy WordPress `wpa` skip-link configuration blob is still in the page
  source (it is inert data, not markup). The real skip link does the work.

---

## 3. Responsive — measured overflow

Measured at **375x812** (client width 358px with the scrollbar), before and after:

| Page | Before | After | Cause |
|---|---|---|---|
| `/` | `scrollWidth 424` vs `358` (66px over) | `358` | Secondary mobile menu: the third column's `.sub-menu` was absolutely positioned at its item's x-offset (239px) with a 185px panel, running 49px past the viewport. Panels are now static/stacked, and the list's negative margin is removed |
| `/about/` | `scrollWidth 394` vs `358` (36px over) | `358` | A `.et_pb_text` module computed 344px inside a 272px column. Mobile rule caps `.et_pb_column`/`.et_pb_module`/`.et_pb_text_inner` at `max-width: 100%` |
| `/products/` | `358` | `358` | — |
| `/contact/` | `358` | `358` | — |
| `/` at 1280x900 | `1263` vs `1263` | `1263` | — (desktop unchanged) |
| `/about/` at 1280x900 | `1263` vs `1263` | `1263` | — (desktop unchanged) |

The theme's own `@media (max-width:472px){body{overflow-x:hidden}}` was masking
the overflow rather than fixing it — content was being *clipped*. It is left in
place (harmless now) but the page no longer needs it.

Dashboard tables wider than a phone now scroll inside their own box
(`main table { display:block; overflow-x:auto }`) at the mobile breakpoint only,
so desktop table layout is untouched.

**Not verified:** tablet widths (768–1024) were not probed; only 375 and 1280.

---

## 4. Image optimisation

`static/` was 166 MB, with a single 18.7 MB PNG (5242x3823) and 440 further
images, most far larger than their rendered size. The new management command
`core/management/commands/optimize_images.py` re-encodes oversized files **in
place** (so no template reference changes) with `--dry-run` support:

* downscale to a 1920px longest side, preserving aspect ratio
* PNG `optimize=True, compress_level=9`; JPEG `quality=82, progressive`
* skip files that would save <10% and are not being resized

Result of the run (`--max-dimension 1920`, `--min-gain 0.10`):

| Metric | Before | After |
|---|---|---|
| `du -sh static` | 166 MB | **133 MB** |
| Images ≥150 KB eligible | 126 scanned | 71 rewritten |
| Bytes saved | — | **34.46 MB** |
| `6330-Xstrahl_14545FAV-1.png` (home hero) | 18.71 MB | **2.53 MB** at 1920x1400 |
| `techno-mate-logo.png` (438x438, rendered ~50px) | 0.77 MB | **0.14 MB** |

Validation after the rewrite: all **436** PNG/JPEG files opened and decoded
successfully (`Image.verify()` + `load()`), zero broken files; `/`, `/about/` and
`/products/` loaded in the browser with **no broken images** (`naturalWidth > 0`
for 20 and 40 images respectively).

**Not done:** conversion to WebP/AVIF with `<picture>` fallbacks. That changes
markup for every legacy asset and was out of scope for this pass; the in-place
re-encode already removes half the static bytes without touching HTML.

---

## 5. Security checklist (report §12 item 7)

`manage.py check --deploy` with production settings reports **one** issue:
`security.W004` (HSTS not set). That is intentional — HSTS stays at `0` until
the certificate is confirmed live on the host (`config/settings/prod.py`).
Everything else in the checklist is green:

| Item | Status | Evidence |
|---|---|---|
| `SECRET_KEY` from env; refuses to boot without it | ✅ | `prod.py` raises `ImproperlyConfigured`; test asserts non-zero exit and the message |
| `ALLOWED_HOSTS` from env; refuses to boot without it | ✅ | Same pattern; tested |
| `DEBUG=False` in production | ✅ | Asserted via subprocess settings probe |
| HTTPS redirect + secure/HttpOnly/SameSite cookies | ✅ | `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `HTTPONLY`, `SameSite=Lax` — asserted |
| `X_FRAME_OPTIONS=DENY`, `nosniff`, referrer policy | ✅ | Asserted |
| CSRF on every state change | ✅ | Phase 4/7 suites; Phase 9 adds nothing to weaken it |
| Auth throttling | ✅ | `accounts/throttle.py`, tested in `accounts/tests_auth.py` |
| Upload type/size limits | ✅ **new** | `tutorials/validators.py` allow-lists png/jpg/jpeg/webp/gif and caps at 5 MB, attached to the model field (form + admin enforce it); transport caps `FILE_UPLOAD_MAX_MEMORY_SIZE=5 MB`, `DATA_UPLOAD_MAX_MEMORY_SIZE=10 MB` in `base.py`; five tests cover rejection/acceptance |
| Audit log for approvals and permission changes | ✅ | Phase 4/7 suites |
| No secrets in the repository | ✅ | Scanned `*.py`/`*.html`/`*.json` for literal keys/passwords: only test fixtures |
| No private media under the docroot | ✅ | `MEDIA_URL` is only routed when `DEBUG`; a test asserts no `media/` route exists under production settings |

---

## 6. What could not be verified (honest limitations)

1. **Interactive focus behaviour.** The preview browser runs without window
   focus (`document.hasFocus() === false`), so `:focus` never matches and the
   skip link cannot be keyboard-activated in this environment. The CSS rules and
   markup are asserted by tests; the *visual* ring and the Tab→Enter skip
   sequence need one manual pass in a normal browser.
2. **Screen-reader announcement.** No NVDA/VoiceOver run was possible. The
   landmark, heading and label structure is tested structurally, not aurally.
3. **Tablet breakpoints (768–1024px)** were not measured, only 375 and 1280.
4. **Legacy pages (51 catch-all pages)** are audited only for the shell
   (skip link, `lang`, images with `alt`, labels); their inner content is the
   original mirrored markup and was not re-authored. They have no `h1` fixes
   applied because their headings come from the imported page body — those
   pages keep the original WordPress heading structure, which is inconsistent
   (several start at `h2`).
5. **No automated axe/Lighthouse run.** The checks above are hand-written
   invariants; a Lighthouse CI pass remains a good later addition.

---

## 7. Files changed in this phase

| File | Change |
|---|---|
| `static/css/site-a11y.css` | New: focus visibility, skip link, overflow guards, mobile menu stacking |
| `templates/base.html` | Zoomable viewport, skip link, `<main>` landmark, a11y stylesheet |
| `templates/core/products.html` | Hidden `h1`, four labelled filter selects |
| `templates/core/search.html` | Labelled search field, fluid width |
| `templates/partials/header.html` | Named search inputs (3) |
| `templates/partials/footer.html` | Named logo link |
| `templates/tutorials/detail.html` | Titled video iframe |
| `templates/dashboard/user_list.html` | Labelled filters, scoped headers |
| `templates/dashboard/{category_list,tutorial_list,user_detail}.html` | `scope="col"` |
| `tutorials/validators.py` | New: extension allow-list + 5 MB cap |
| `tutorials/models.py` + migration `0002` | Validators attached to `Tutorial.thumbnail` |
| `config/settings/base.py` | Upload transport limits |
| `core/management/commands/optimize_images.py` | New: repeatable optimisation pass |
| `static/images/**` (71 files) | Re-encoded/downscaled in place |
| `core/tests_phase9.py` | New: 25 tests |
