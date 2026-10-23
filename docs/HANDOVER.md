# Handover — Xstrahl clone rebuilt on Django

Status: **all ten planned phases are implemented and committed.** The site runs,
is tested, has been audited for accessibility and security, and has a deployment
runbook. What remains is either in your hands (credentials, host facts) or in
the "not verified here" list at the end.

Stack: Django 5.2 LTS · Python 3.12 · SQLite in development, MySQL/MariaDB on
cPanel (Passenger WSGI) · Bunny Stream for protected video · no build step, no
front-end framework, no external runtime services.

---

## 1. Run it

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# .venv/bin/python -m pip install -r requirements.txt     # Linux/macOS

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

* Site: <http://127.0.0.1:8000/>
* Staff dashboard: `/dashboard/` (needs `is_staff`)
* Tutorial library: `/tutorials/`
* Settings: `config/settings/dev.py` by default; production imports
  `config/settings/prod.py` and refuses to start without `DJANGO_SECRET_KEY`
  and `DJANGO_ALLOWED_HOSTS`.

Tests:

```bash
python manage.py test          # 146 tests, ~2 minutes
python manage.py check --deploy  # with the production env; only W004 until HSTS is on
```

---

## 2. Phase status

| Phase | Delivered | Commit |
|---|---|---|
| 1 | Inspection report: stack, 56 pages, link graph, auth model, video options, cPanel limits, security risks | (report committed in Phase 2) |
| 2 | Django scaffold, split settings, env-driven DB, app skeletons, legacy pages preserved | `74d9856`, `418bae3` |
| 3 | `base.html` + header/footer partials, 5 core pages converted, sanitised shell, 51 legacy pages via catch-all | `a107d25` |
| 4 | Custom user model, registration/login/logout, pending→approved lifecycle, throttling, audit log | `9abe5f3` |
| 5 | Tutorial/category models, per-tutorial grants, single access predicate, playback authorization | `d943686` |
| 6 | Bunny Stream decision record, token signing, one-time redemption | `6bdcda3` |
| 7 | Staff dashboard: approvals, user/grant management, tutorial + category CRUD, progress summaries | `c7a0327` |
| — | Navbar cleanup requested mid-project: dead links removed | `fc5917b` |
| 8 | Site search, category pages, watch-progress reporting with per-request cap, player wiring | `35e9df4` |
| 9 | Accessibility, responsive, image and security review + 25 tests | `32da096` |
| 10 | cPanel deployment guide, SQLite→MySQL runbook, Passenger entry point, env wiring fixes | `b3068de` |

---

## 3. What was verified, and how

**Automated suite — 146 tests, green** (`python manage.py test`, exit status
captured, no skipped tests). It covers registration/throttling, the approval
lifecycle, the permission matrix (published × granted × approved), staff-only
enforcement across all 12 dashboard routes, self-approval blocking, CSRF, search
accuracy, progress caps, a11y invariants, upload validation and deployment
wiring.

**Live end-to-end walkthrough — 41/41 checks over real HTTP** against the dev
server (cookies + CSRF, not the test client):

1. Anonymous: home renders, skip link present, pinch-zoom not blocked, search
   returns hits, catalog lists the fixture tutorial.
2. Register a new account → lands on login, row is `pending`.
3. Learner login → redirected to the pending page; `/dashboard/` → **403**;
   tutorial detail → **403**; `GET` on authorize → **405**.
4. Staff login → user list shows the learner → approve (DB shows `approved` +
   approver) → grant (access row created).
5. Learner: detail now **200**; report 30 s of a 120 s video → **25 %**; report
   another 9999 s → clamped to **+60 s → 75 %**; authorize mints a token; redeem
   answers **503 `provider_not_configured`** (no Bunny keys in this environment);
   the same token replayed → **403** (single use).
6. Staff revokes → learner's detail **403**, progress **403**, authorize **403**.
7. CSRF-less POST → **403**; static asset **200**; `/media/` **404**; unknown
   URL → the custom **404** page.
8. Audit trail contains `user_registered`, `user_approved`, `access_granted`,
   `access_revoked`.

**Production checks:** `check --deploy` clean except `security.W004` (HSTS
deliberately off until the certificate is live); `collectstatic` dry-run copies
881 files; `import passenger_wsgi` loads with `DEBUG=False`; the documented
`dumpdata` command produces valid JSON.

**Accessibility / responsive / performance:** measured in a real browser at
375×812 and 1280×900 — see [PHASE9_A11Y_SECURITY_REVIEW.md](PHASE9_A11Y_SECURITY_REVIEW.md).
Mobile overflow went from 66 px (`/`) and 36 px (`/about/`) to zero; `static/`
dropped 166 MB → 133 MB with no markup changes.

---

## 4. What still needs you

| # | Item | Why it matters |
|---|---|---|
| 1 | **Bunny Stream credentials** — `BUNNY_STREAM_LIBRARY_ID`, `BUNNY_STREAM_SECURITY_KEY` | Playback intentionally answers 503 until they exist. Put them in the cPanel environment (or `.env`), never in the repo |
| 2 | **Host facts** — Python version, MySQL version, Passenger worker count, upload limit, AutoSSL availability | Two of them can block deployment (see §0 of the deployment guide) |
| 3 | **One manual keyboard pass** | The preview browser here has no window focus, so `:focus` never matched and the skip link could not be activated. Tab through the header → skip link appears → Enter jumps to `<main>`; Tab shows a purple ring on every control. This is the only a11y fix not proven interactively |
| 4 | **Decide about the 51 legacy pages** | They are served as-is from the mirrored HTML. Their headings start at `h2` in places and their alt text is the original's. Re-authoring them is a content project, not a bug fix |
| 5 | Tablet widths (768–1024 px) | Only 375 and 1280 were measured; a spot check on a real tablet would close the gap |
| 6 | Lighthouse / axe CI | The a11y checks are hand-written invariants, not an automated audit |

Nothing else is outstanding. The uncommitted `logo.png` change predates this
work and was deliberately left alone.

---

## 5. Operational notes

* **Video**: the browser never sees `video_ref`. `/tutorials/<slug>/authorize/`
  mints a 5-minute opaque token after re-checking access; `/tutorials/redeem/`
  consumes it once and returns a signed Bunny embed URL (1 h). Revocation takes
  effect on the next request.
* **Cache**: production defaults to the database cache
  (`manage.py createcachetable`), because the two-step playback handshake breaks
  under the per-worker LocMem default. `DJANGO_CACHE_BACKEND=locmem` overrides it
  for single-worker hosts only.
* **Media**: thumbnails live in `media/tutorial_thumbs/` and are the only files
  that may be web-mapped. Never symlink the whole `media/` directory — Apache
  would serve private files without Django ever checking access.
* **Static**: `collectstatic` → `staticfiles/`; symlink it as
  `public_html/static`. Media is **not** routed by Django when `DEBUG=False`.
* **Images**: `python manage.py optimize_images --dry-run` reports savings;
  without `--dry-run` it rewrites oversized assets in place. It needs Pillow,
  which is intentionally not a runtime dependency.
* **Search**: the legacy corpus is read once per process, capped at ~400 KB of
  body text per page (documented in `core/search_index.py`).
* **Cron**: `clearsessions` daily; nothing else is required. There is no Celery
  or background worker, by design — cPanel cannot run one.

---

## 6. Where things live

```
config/            settings (base / dev / prod), urls, wsgi
accounts/          custom user, approval lifecycle, throttle, audit log
tutorials/         catalog, access predicate, playback, progress, Bunny signing
dashboard/         staff-only views, forms, tests
core/              home/about/products/services/contact, search, legacy catch-all
templates/         base.html, partials/, per-app templates, dashboard/
static/css/site-a11y.css   Phase 9 focus/skip-link/overflow layer
static/images/     optimised mirrored assets
legacy/            original mirrored pages behind the catch-all
passenger_wsgi.py  cPanel entry point (+ optional .env loader)
```

Guides: [deployment](PHASE10_DEPLOYMENT_CPANEL.md) ·
[MySQL migration](PHASE10_SQLITE_TO_MYSQL.md) ·
[a11y & security review](PHASE9_A11Y_SECURITY_REVIEW.md) ·
[inspection report](PHASE1_INSPECTION_REPORT.md) ·
[video decision](PHASE6_VIDEO_HOSTING_OPTIONS.md).
