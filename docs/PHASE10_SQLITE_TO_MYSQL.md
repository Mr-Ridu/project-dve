# Phase 10 — SQLite → MySQL migration runbook

Development uses SQLite (`db.sqlite3`). cPanel production must use MySQL or
MariaDB. Nothing in the application code is SQLite-specific: every schema change
goes through migrations, and the database is chosen purely by environment
variables (`config/settings/base.py`).

This runbook has two uses:

* **A. First production deploy** — create a fresh MySQL database and migrate.
* **B. Moving an existing SQLite deployment** — carry the data across.

Both end with the same verification. Read the "Gotchas" section before starting;
one of them (case-insensitive `LIKE`) changes behaviour you might rely on.

---

## 0. Prerequisites

| Requirement | Check |
|---|---|
| MySQL **8.0.11+** or MariaDB **10.5.2+** | `mysql --version` on the host, or cPanel → MySQL Databases footer |
| Database and user created with ALL PRIVILEGES | cPanel → MySQL Databases |
| Database charset `utf8mb4`, collation `utf8mb4_unicode_ci` | Set at creation; see §1 |
| A MySQL driver installed in the app virtualenv | §2 |
| The app stopped (no writes during the copy) | `touch tmp/restart.txt` after maintenance notice, or put the site behind a maintenance page |

Django 5.2 itself refuses older MySQL/MariaDB versions at connection time, so a
too-old host fails loudly rather than corrupting data.

---

## 1. Create the database (cPanel)

1. **MySQL Databases → Create New Database**: e.g. `USER_tmt`.
2. **Add New User**, strong password, then **Add User To Database → ALL
   PRIVILEGES**.
3. Character set: `utf8mb4`, collation `utf8mb4_unicode_ci`.

If the database was created with latin1 by mistake, drop and recreate it now —
fixing the charset after import means dumping, recreating and importing again.

cPanel prefixes names with your account: user `USER_tmt`, database `USER_tmt`.

---

## 2. Install a MySQL driver

Two options; pick one.

**Preferred — `mysqlclient`** (C extension, fastest, no shim):

```bash
source ~/virtualenv/apps/tmt/3.12/bin/activate
pip install "mysqlclient>=2.2"
```

It needs MySQL client headers. If it fails with `mysql_config not found`, either
ask the host to provide `mysql-devel`, or use the fallback.

**Fallback — `PyMySQL`** (pure Python, works everywhere):

```bash
pip install "PyMySQL>=1.1"
```

PyMySQL needs a two-line shim so Django treats it as `MySQLdb`. Put it at the
**top** of `config/__init__.py`:

```python
import pymysql

pymysql.install_as_MySQLdb()
```

Remove those lines if you later switch to `mysqlclient` — loading both in one
process is a source of confusing errors.

Then pin whichever you installed in `requirements.txt` (replace the commented
lines at the bottom) so the next deploy installs it too.

---

## 3. A. Fresh production database

```bash
cd ~/apps/tmt
source ~/virtualenv/apps/tmt/3.12/bin/activate

export DJANGO_SETTINGS_MODULE=config.settings.prod
export DB_ENGINE=mysql DB_NAME=USER_tmt DB_USER=USER_tmt DB_PASSWORD='...'
export DB_HOST=localhost DB_PORT=3306

python manage.py check --deploy
python manage.py migrate --plan        # read this before running it
python manage.py migrate
python manage.py createcachetable
python manage.py createsuperuser
```

Done — continue at §5 (verification).

---

## 4. B. Moving existing SQLite data

### 4.1 Freeze and back up

```bash
cd ~/apps/tmt
cp -p db.sqlite3 "db.sqlite3.bak-$(date +%F-%H%M)"
python manage.py dumpdata \
  --natural-foreign --natural-primary \
  -e contenttypes -e auth.permission -e sessions \
  --indent 2 -o data-$(date +%F).json
```

* `-e contenttypes -e auth.permission` — those rows are recreated by `migrate`;
  exporting them causes duplicate-key errors.
* `-e sessions` — nobody needs stale logins in a new database.
* **The JSON contains password hashes.** Treat it as a secret: `chmod 600`,
  never commit it, delete it after a successful import.

Sanity-check the export before touching MySQL:

```bash
python - <<'PY'
import json
data = json.load(open("data-2026-10-24.json", encoding="utf-8"))
print(len(data), "objects")
print(sorted({o["model"] for o in data}))
PY
```

Expect the app models: `accounts.user`, `accounts.auditevent`,
`tutorials.category`, `tutorials.tutorial`, `tutorials.tutorialaccess`,
`tutorials.tutorialprogress`, and possibly `auth.group`.

### 4.2 Point the app at MySQL and create the schema

```bash
export DB_ENGINE=mysql DB_NAME=USER_tmt DB_USER=USER_tmt DB_PASSWORD='...'
python manage.py migrate
python manage.py createcachetable
```

Run `migrate` on the **empty** MySQL database only. Do not point the app at it
before this step completes.

### 4.3 Import the data

```bash
python manage.py loaddata data-2026-10-24.json
```

Takes seconds for a library this size. If it fails with a foreign-key error,
the export was made with `-e contenttypes` removed or with a partially edited
file — restore the SQLite copy, re-export, and try again. Do not hand-edit the
JSON.

### 4.4 Verify the copy

Counts must match on both databases. Run this with each connection:

```bash
python - <<'PY'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
django.setup()
from django.apps import apps
for model in apps.get_models():
    label = model._meta.label
    if label.startswith(("admin.", "auth.permission", "contenttypes.")):
        continue
    print(f"{label:32} {model.objects.count()}")
PY
```

Run it once against the SQLite copy (`DB_ENGINE` unset, `db.sqlite3.bak` restored
temporarily) and once against MySQL; every line must match.

Also check the things a row count hides:

```bash
python manage.py shell -c "
from accounts.models import User
from tutorials.models import Tutorial, TutorialAccess
print('approved:', User.objects.filter(approved_at__isnull=False).count())
print('staff:', User.objects.filter(is_staff=True).count())
print('published:', Tutorial.objects.filter(is_published=True).count())
print('grants:', TutorialAccess.objects.count())
print('sample title:', Tutorial.objects.first())
"
```

Accented characters are the usual casualty of a latin1 database — open a tutorial
with a non-ASCII title and confirm it is intact.

### 4.5 Switch over

```bash
touch tmp/restart.txt
```

Keep `db.sqlite3` and the `db.sqlite3.bak-*` copy for at least a week.

### 4.6 Rollback

* **Before any MySQL writes:** remove the `DB_*` variables (or set
  `DB_ENGINE=sqlite`), restore `db.sqlite3`, `touch tmp/restart.txt`.
* **After go-live:** the SQLite copy is stale. Restore service on MySQL from a
  `mysqldump` taken at cut-over, or accept the data written since then is lost.

Never leave both databases writable "just in case" — pick one.

---

## 5. Verification (both paths)

```bash
python manage.py check
python manage.py showmigrations | grep -c "\[ \]"    # must print 0
python manage.py test                                # 130 tests against MySQL
```

The test suite is the strongest check available: it creates and destroys its own
test database, so it never touches live data, and it exercises grants, progress,
audit rows and staff permissions against the real backend.

Then, live:

| Check | Expected |
|---|---|
| Register a user | row appears in `accounts_user`, status pending |
| Staff approves them | `approved_at`/`approved_by` set, audit row written |
| Grant a tutorial | `tutorials_tutorialaccess` row |
| Watch a tutorial for a minute | `tutorials_tutorialprogress.seconds_watched` increases |
| Search for a term with an accent | results render (collation check) |
| Login, log out, log in | sessions work (they live in `django_session`) |

---

## 6. Gotchas specific to this move

| Topic | Detail |
|---|---|
| **Case-insensitive search** | SQLite's `LIKE` is case-insensitive for ASCII; MySQL's depends on collation. With `utf8mb4_unicode_ci` it stays case-insensitive, so `/search/` behaves the same. A `_bin` collation would silently make search case-sensitive |
| **Booleans** | Stored as `tinyint(1)`. Fine — no code casts to `0/1` manually |
| **Datetimes** | `USE_TZ=True`; everything is UTC in both backends. Do not switch `TIME_ZONE` during the move |
| **`TEXT` vs `VARCHAR`** | `Tutorial.description` is `TextField` → `longtext`. No 255-char truncation surprises |
| **Unique keys** | `slug` (220 chars) and the grant/progress unique constraints are within InnoDB's 3072-byte index limit at `utf8mb4` (4 bytes/char ⇒ 880 bytes) |
| **Auto-increment gaps** | Harmless. `loaddata` preserves explicit primary keys, so grants/progress keep pointing at the right rows |
| **`"MySQL server has gone away"`** | Host `wait_timeout` shorter than Passenger's idle time. Ask the host to raise it, or add `CONN_MAX_AGE` only if the host supports persistent connections |
| **`OperationalError: (1044) Access denied`** | The cPanel user was added without ALL PRIVILEGES, or `DB_NAME` is missing the `USER_` prefix |
| **Emoji / 4-byte characters** | Need real `utf8mb4` (MySQL's "utf8" is 3-byte and rejects them). The app connects with `charset=utf8mb4`; the database must match |
| **Uploads are not in the database** | Thumbnails live in `media/tutorial_thumbs/`; copy that directory separately |
| **Cache table** | Not a migration. `createcachetable` on every environment, or every login fails |

---

## 7. What was verified here, and what was not

Verified on this machine (SQLite only, no MySQL server available):

* `manage.py migrate` applies cleanly from zero; no pending migrations
  (`makemigrations --check` → *No changes detected*).
* The documented export command runs and produces valid JSON with the expected
  model labels (`accounts.user` in the current dev database).
* `DJANGO_SETTINGS_MODULE=config.settings.prod DB_ENGINE=mysql ...` selects the
  MySQL backend with `utf8mb4` and reads every `DB_*` variable.
* The test suite (130 tests) passes against SQLite.

**Not verified:** the actual MySQL import, collation behaviour, the driver
build, and InnoDB index limits on your host's MySQL version. Those need a real
MySQL database; step §5's test run is where they get proven, before any user
touches the site.
