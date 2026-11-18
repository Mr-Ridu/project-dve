# Handover — DVE / Techno Mate website

_Last updated: end of the arrow-button session._

## Repo

- Project: `D:\Coding Projects\Frontend projects\Machinery custom\Xstrahl Clone` (Django, Tailwind)
- Remote: `https://github.com/Mr-Ridu/project-dve.git`, branch `main`
- Last pushed commit: **`786892f`** — “Add the technology, events and customer pages from the client brief”
- **Uncommitted:** `templates/base.html` — back-to-top button missing `flex` (arrow sat in the top-left corner) + both chevron paths re-centred. Verified in the browser, `manage.py test core` → 90 OK. **Not committed, not pushed.**

## Live server

- Live URL: `https://dve.growingitagency.com/`
- Live is still on the older content (`2f07208` level): new pages, mobile sector-bar fix, tender wording and the arrow fix are **not** live.
- cPanel paths: app `/home/growingi/dve-file`, static `/home/growingi/dve.growingitagency.com/static`, restart file `tmp/restart.txt`.
- Deploy: SFTP (`growingi@growingitagency.com`, key `tmp/ssh/tmt_deploy`, `BatchMode=yes`, `UserKnownHostsFile=tmp/ssh/known_hosts.deploy`), then touch `tmp/restart.txt`.

## Local dev

- `http://127.0.0.1:8791/` — `runserver --noreload`, listener PID **11856** (kill with `taskkill //PID 11856 //F`; plain `kill` does not work on Windows).
- Checks: `.venv/Scripts/python.exe manage.py check` / `... manage.py test core` (90 tests) / `npm run build:css` for Tailwind.

## What is already done

- Pages added: `/our-technology/`, `/events-and-seminars/` (menu label “Events”), `/for-customer/` — with desktop nav, mobile menu and footer links.
- Home: client first banner as hero (`hero-client.webp`), tender copy uses “Tender with Government Department”, mobile sector strip hidden (`hidden lg:block`).
- About: “one point of contact, defined standards” block.
- E-Tender Management: the brief's 10 module names listed (informational page, not an app).
- Social links: only YouTube (`core/context_processors.py`); `templates/partials/social_icons.html` still has unused facebook/whatsapp/x branches.
- Daily Update copy no longer mentions deferred payment.
- Slug rule: `core/tests.py` `REMOVED_SLUGS` contains `events`, `presentations`, `for-patients` — those old URLs must 404.

## Waiting on the client

See `docs/ক্লায়েন্ট-শর্ট-ফর্ম.md` (the short Bengali form to send) and `docs/CLIENT_CONTENT_FORM.md` (the full version, backup only).

Blocking items: real user-spotlight quote, Presentation video, sector order, product descriptions (brief has `AAAA…` placeholders), events dates, form emails, extra social URLs, E-Tender scope.

## Next actions

1. Commit + push `templates/base.html`.
2. Deploy `786892f` + the new commit to cPanel, restart, verify the new pages and the fixed buttons live.
3. Fill in whatever the client returns; defaults are already defined in the short form.
