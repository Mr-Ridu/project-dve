# Phase 10 — Deploying this project on cPanel (Passenger + MySQL)

This is the runbook for putting the finished site on a cPanel host. It assumes
the standard CloudLinux/cPanel **Setup Python App** feature, which runs the app
through **Phased Passenger** (a WSGI server) behind LiteSpeed/Apache.

It does not assume your host's exact versions. Step 0 is collecting those, and
two of them can stop the deployment.

---

## 0. Facts to collect from the host first

Ask support (or read them in cPanel) **before** uploading anything:

| Fact | Why it matters | Acceptable |
|---|---|---|
| Python versions offered | Django 5.2 needs 3.10+; this project was developed on 3.12 | 3.10 – 3.13 |
| MySQL / MariaDB version | Django 5.2 supports MySQL **8.0.11+** / MariaDB **10.5.2+** | at or above those |
| Passenger "max processes" / `LSAPI_CHILDREN` | Each worker is a Python process (~80–150 MB RSS). Video is streamed by Bunny, not by this app | ≥ 2 workers |
| Upload limit (LiteSpeed/Post `post_max_size`) | Thumbnails are capped at 5 MB by the app; the server must allow at least that | ≥ 8 MB |
| Whether `public_html` is separate from the app directory | Static files are served by the web server from `public_html` | yes |
| AutoSSL available | Secure cookies are on in production; without HTTPS nobody can log in | yes |

If the host only offers Python 3.8/3.9, this deployment stops here — Django 5.2
will not run on it.

---

## 1. Directory layout used below

```
/home/USER/
├── apps/tmt/                  ← application root (NOT web-accessible)
│   ├── manage.py
│   ├── passenger_wsgi.py      ← Passenger entry point (in this repo)
│   ├── config/  accounts/  core/  dashboard/  tutorials/
│   ├── static/                ← source assets (repo)
│   ├── staticfiles/           ← collectstatic target (generated)
│   ├── media/                 ← thumbnails only (video is on Bunny)
│   ├── .env                   ← optional; secrets, chmod 600
│   └── tmp/restart.txt        ← touch to restart the app
├── public_html/
│   ├── static -> /home/USER/apps/tmt/staticfiles   (symlink)
│   └── media/tutorial_thumbs -> .../media/tutorial_thumbs (symlink)
└── virtualenv/apps/tmt/3.12/  ← created by cPanel's Python App
```

Nothing under `apps/tmt` is reachable by URL. `db.sqlite3` is **not** used in
production (see the MySQL guide).

---

## 2. Create the Python application

1. cPanel → **Setup Python App** → *Create Application*.
2. Application root: `apps/tmt` · Application URL: your domain · Python version:
   the highest 3.1x offered (3.12 preferred).
3. `Application startup file`: `passenger_wsgi.py` (cPanel fills this in; the
   file is already in the repository).
4. `Application Entry point`: `application`.
5. Create. cPanel writes `passenger_wsgi.py` **only if it does not exist** — ours
   already does, and it is correct, so do not overwrite it.

The app is created with a virtualenv at
`/home/USER/virtualenv/apps/tmt/<version>`.

---

## 3. Upload the code and install dependencies

```bash
cd ~/apps/tmt
# either clone, or upload a zip of the repo and unzip here
source ~/virtualenv/apps/tmt/3.12/bin/activate
pip install --upgrade pip
pip install -r requirements.txt          # Django 5.2.x
pip install mysqlclient                  # see the MySQL guide if this fails
python -c "import django; print(django.get_version())"
```

Do **not** run `pip install -e .`; there is no packaging step.

---

## 4. Environment variables

Passenger does not read `.env` on its own. `passenger_wsgi.py` in this repo
loads one if you point it at a file, otherwise use cPanel's UI
(**Setup Python App → Environment variables**).

Generate the secret on the server:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

| Variable | Required | Example | Notes |
|---|---|---|---|
| `DJANGO_SETTINGS_MODULE` | yes | `config.settings.prod` | `passenger_wsgi.py` defaults to this |
| `DJANGO_SECRET_KEY` | **yes** | 64-char random | App refuses to start without it |
| `DJANGO_ALLOWED_HOSTS` | **yes** | `example.com,www.example.com` | No scheme, no trailing slash |
| `DB_ENGINE` | yes on MySQL | `mysql` | Anything else = SQLite |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | yes on MySQL | from cPanel | DB user needs ALL PRIVILEGES on that DB |
| `DB_HOST` / `DB_PORT` | no | `localhost` / `3306` | cPanel default is a local socket |
| `DJANGO_SSL_REDIRECT` | no | `1` (default) | `0` only while testing without HTTPS |
| `DJANGO_HSTS_SECONDS` | no | `0` (default) → later `31536000` | Enable only after HTTPS is proven (§9) |
| `DJANGO_CACHE_BACKEND` | no | `database` (prod default) | `locmem` only for a single-worker host |
| `BUNNY_STREAM_LIBRARY_ID` | for video | numeric id | Empty ⇒ playback answers 503 |
| `BUNNY_STREAM_SECURITY_KEY` | for video | Bunny token key | Never commit this |
| `DJANGO_LOG_LEVEL` | no | `INFO` | Passenger captures stderr into the app log |
| `DJANGO_ENV_FILE` | no | `/home/USER/apps/tmt/.env` | Only if you use a file instead of the UI |

`.env` alternative:

```bash
umask 077
cat > ~/apps/tmt/.env <<'EOF'
DJANGO_SECRET_KEY=replace-me
DJANGO_ALLOWED_HOSTS=example.com,www.example.com
DB_ENGINE=mysql
DB_NAME=...
DB_USER=...
DB_PASSWORD=...
EOF
chmod 600 ~/apps/tmt/.env
```

Prefer the cPanel UI: a mis-set permission on `.env` is silent, while a missing
cPanel variable is visible in the UI. Either way, **never** put these values in
the repository or in a support ticket.

---

## 5. Create the database

cPanel → **MySQL Databases**:

1. New database, e.g. `USER_tmt`.
2. New user + strong password.
3. Add user to database with **ALL PRIVILEGES**.
4. Set the database **character set to `utf8mb4`** (collation
   `utf8mb4_unicode_ci`). The app connects with `charset=utf8mb4`; a latin1
   database will mangle names with accents and emoji.
5. Note the full names — cPanel prefixes them with your account (`USER_tmt`).

---

## 6. Migrate, create the cache table, create an admin

```bash
cd ~/apps/tmt
source ~/virtualenv/apps/tmt/3.12/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings.prod   # Passenger sets this too

python manage.py check --deploy          # expect only security.W004 (HSTS)
python manage.py migrate
python manage.py createcachetable        # required: prod uses the database cache
python manage.py createsuperuser
```

`createcachetable` is not a migration; skipping it makes every login fail with
`Table 'USER_tmt.django_cache' doesn't exist`. If the table is missing later,
re-run it — it is idempotent.

`check --deploy` reporting `security.W004` is expected and correct until §9.

---

## 7. Static files and public thumbnails

```bash
python manage.py collectstatic --noinput      # ~880 files into staticfiles/
mkdir -p ~/public_html
ln -s ~/apps/tmt/staticfiles ~/public_html/static
```

If `~/public_html/static` already exists (an old WordPress install), move it out
of the way first — `ln -s` will otherwise create the link *inside* it.

Only the **thumbnail** directory is web-mapped. Video never touches this server:

```bash
mkdir -p ~/public_html/media
ln -s ~/apps/tmt/media/tutorial_thumbs ~/public_html/media/tutorial_thumbs
```

Do **not** symlink the whole `media/` directory. If a private file is ever put
there, Apache/LiteSpeed will serve it without Django ever checking a permission.
The app only writes thumbnails to `media/tutorial_thumbs/`.

Verify:

```bash
curl -I https://example.com/static/css/site-a11y.css
# HTTP/2 200, content-type: text/css
curl -I https://example.com/media/tutorial_thumbs/anything.png   # 404 is correct
```

Django's own `runserver` media route is disabled when `DEBUG=False`
(`config/urls.py`), so a missing symlink shows up as a broken thumbnail, not a
Django error.

---

## 8. Restart and verify

```bash
mkdir -p ~/apps/tmt/tmp
touch ~/apps/tmt/tmp/restart.txt
```

Then, from your own machine:

| Check | Expected |
|---|---|
| `curl -I https://example.com/` | `200`, `set-cookie` only after login |
| `curl -I http://example.com/` | `301` to `https://` |
| `curl -I https://example.com/static/css/site-a11y.css` | `200 text/css` |
| `curl -s https://example.com/robots.txt` | not required; 404 is fine |
| `/accounts/register/` → submit | account created as *pending*, no tutorial access |
| `/accounts/login/` as a normal user, then `/dashboard/` | **403** |
| `/dashboard/` as staff | dashboard loads |
| `/tutorials/` | catalog page (empty until tutorials exist) |
| `/media/` (bare) | **404** — must never list files |
| Playback on a published+granted tutorial | player loads if Bunny env is set; otherwise a 503 with `provider_not_configured` |

The CSRF cookie is `Secure` in production: **logins only work over HTTPS**.
If HTTPS is not live yet, set `DJANGO_SSL_REDIRECT=0` temporarily *and* expect
login to fail until the certificate is in place.

---

## 9. HTTPS and HSTS (in that order)

1. cPanel → **SSL/TLS Status** → run AutoSSL for the domain; confirm
   `https://example.com/` loads without a warning.
2. Only then set `DJANGO_HSTS_SECONDS=31536000` and restart.
3. Re-check `manage.py check --deploy` — it should now report **no issues**.

Do not enable HSTS first. HSTS is remembered by browsers for a year; a broken
certificate afterwards locks users out of the domain.

---

## 10. Cron

Only short, bounded commands — there is no Celery/worker on shared hosting.

```bash
# cPanel → Cron Jobs: daily 03:10
cd /home/USER/apps/tmt && /home/USER/virtualenv/apps/tmt/3.12/bin/python manage.py clearsessions >> /home/USER/apps/tmt/cron.log 2>&1

# cPanel → Cron Jobs: weekly Sunday 03:40 — database backup (see §11)
```

Sessions and play tokens are cleaned by `clearsessions`; the token cache keys
expire on their own (10 minutes, `TOKEN_TTL_SECONDS`).

---

## 11. Backups

```bash
# database
mysqldump --single-transaction --default-character-set=utf8mb4 \
  -u USER_tmt -p USER_tmt > ~/backups/tmt-$(date +%F).sql

# uploaded thumbnails (small)
tar czf ~/backups/media-$(date +%F).tar.gz -C ~/apps/tmt media

# the only irreplaceable file
cp ~/apps/tmt/.env ~/backups/env-$(date +%F).env
```

Keep at least seven daily dumps. `~/backups` must be outside `public_html`.
Restore: `mysql -u USER_tmt -p USER_tmt < file.sql`, then untar media.

---

## 12. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| 500 immediately after upload | `ImproperlyConfigured: DJANGO_SECRET_KEY must be set` | Variable missing from the Passenger environment; restart after adding |
| 500 with `ALLOWED_HOSTS` message | Same, for hosts | Add domain **without** scheme |
| 502/503 from Passenger, app log empty | Wrong Python version or missing dependency in the app's virtualenv | `pip install -r requirements.txt` with the venv activated |
| Every page 403 "CSRF verification failed" | `ALLOWED_HOSTS` wrong, or cookies refused because the site is HTTP while `Secure` is on | Fix hosts; serve HTTPS |
| `Table 'django_cache' doesn't exist` | `createcachetable` skipped | Run it |
| Static CSS/JS 404 under `/static/` | Symlink missing or points at the source `static/` instead of `staticfiles/` | Recreate the link; `ls -l ~/public_html/static` |
| Thumbnails 404 but everything else works | `media/tutorial_thumbs` symlink missing | Recreate it |
| Playback says "Video is not configured yet" | Bunny env vars absent | Add both, restart |
| Login works for one request, then logs out | Cookies require HTTPS but the site is on HTTP | Fix HTTPS first |
| Intermittent `token_invalid` on playback | `locmem` cache with several workers | Leave `DJANGO_CACHE_BACKEND` at its prod default (`database`) |
| Slow first request, then fast | Passenger cold start | Normal; keep the app warm with a cron `curl` if it matters |

App logs: cPanel → **Setup Python App → Logs**, or
`~/apps/tmt/stderr.log` on many hosts.

---

## 13. What this host cannot do (by design)

* **No WebSockets / ASGI** — Passenger is WSGI only. Nothing in the app needs it.
* **No long-running workers** — all background work is cron-driven or absent.
* **No video streaming from this server** — playback is signed Bunny embeds; the
  app only issues short-lived signed URLs (10-minute embed TTL).
* **No DRM** — signed links raise the bar; they cannot stop screen recording.
  That was the recorded Phase 6 decision.

## 14. Verified vs untested

Verified on this machine (Windows dev box, not the host):

* `manage.py check --deploy` with the production env → clean except intentional
  `security.W004`.
* `manage.py collectstatic --noinput --dry-run` → 881 files, no errors.
* `import passenger_wsgi` with production env → `application` is callable and
  settings load with `DEBUG=False`.
* `manage.py dumpdata --natural-foreign --natural-primary -e contenttypes
  -e auth.permission -e sessions` → valid JSON.

**Not testable here:** Passenger itself, cPanel's Python selector, AutoSSL, the
MySQL server, and every host-specific limit in §0. Those are the steps that need
your host's actual answers.
