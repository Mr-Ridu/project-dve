# Video upload guide

How a recording becomes a playable tutorial. Written for staff who publish
content, not for developers — the code side is in
[PHASE6_VIDEO_HOSTING_OPTIONS.md](PHASE6_VIDEO_HOSTING_OPTIONS.md) and
[HANDOVER.md](HANDOVER.md).

> **The video file never touches this server.** Django stores only the title,
> length and the provider's *video id*. Encoding, storage and delivery all
> happen on Bunny Stream. That keeps the cPanel account well inside its disk
> quota and means a 2 GB recording is no different to the site than a 20 MB one.

---

## 1. Before you start

| You need | Where it comes from |
|---|---|
| A Bunny Stream library | bunny.net → Stream → add a library |
| The **library ID** | Stream → your library → the number in the URL / settings |
| The **management API key** | Stream → your library → API (only for uploads from the dashboard) |
| The library's **token key** | Stream → your library → Security (only for signing playback) |
| A staff account on the site | An existing staff member approves you |

The site reads three environment variables and nothing else:

```bash
BUNNY_STREAM_LIBRARY_ID=12345
BUNNY_STREAM_SECURITY_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
BUNNY_STREAM_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Two different keys, easy to mix up:

| Variable | Bunny screen | Used for |
|---|---|---|
| `BUNNY_STREAM_SECURITY_KEY` | Stream → Security → *Token authentication key* | signing playback links (watching) |
| `BUNNY_STREAM_API_KEY` | Stream → API → *API key* | uploading videos from the site (creating) |

Missing `BUNNY_STREAM_API_KEY` does not stop playback — it only disables the
**Video file** upload box, which then says exactly what to set.

- **Production (cPanel):** Setup Python App → Environment variables, then
  restart the app. Details in
  [PHASE10_DEPLOYMENT_CPANEL.md](PHASE10_DEPLOYMENT_CPANEL.md) §4.
- **Local development:** put them in the gitignored `.env` at the project
  root — `config/settings/dev.py` loads it before Django starts, and a real
  environment variable still wins over the file. Restart `runserver` after
  editing it (`.env` is not watched by the auto-reloader).

  ```dotenv
  BUNNY_STREAM_LIBRARY_ID=789677
  BUNNY_STREAM_SECURITY_KEY=xxxxxxxx
  BUNNY_STREAM_API_KEY=xxxxxxxx
  ```

  Exporting them in the shell works too, but then they must be set again in
  every new terminal.

Never paste these keys into a tutorial field, a template, a commit or a chat
message. The playback code reads them from settings only, and the key is never
sent to the browser (a test asserts this).

If the keys are missing, playback answers **503 `provider_not_configured`** —
honest failure rather than an unsigned link.

---

## 2. Upload the file to Bunny Stream

### Option A — from this site's dashboard (recommended)

This is the whole job for day-to-day publishing — bunny.net is never opened:

1. Sign in as staff → **Dashboard → Tutorials → + New tutorial** (or *Edit* an
   existing one).
2. Fill in title/description as usual, then under **Video file** choose the
   MP4/MOV and press **Save**.
3. The file travels through the site to Bunny Stream, and the form fills
   **Video provider = Bunny Stream** and **Video reference = <GUID>** for you.
4. Done. Publish the tutorial and grant access (§4).

Notes worth knowing:

- Upload happens **before** anything is saved: if Bunny rejects the file or the
  network drops, the tutorial stays exactly as it was and the form explains why.
- A **fresh file upload replaces** the previous video reference. Leaving the
  box empty keeps whatever video is already attached.
- If the upload fails halfway, the half-created Bunny video is deleted again —
  nothing accumulates in the library.
- The file passes through the shared host on its way to Bunny, so keep videos
  **under ~2 GB** and prefer a stable connection. Bunny encodes it afterwards;
  a still-processing video plays as a black frame, so wait a few minutes.
- The accepted extensions are `mp4`, `mov`, `m4v`.

### Option B — bunny.net dashboard (manual, still works)

1. bunny.net → **Stream** → your library → **Upload**.
2. Drag the MP4/MOV in. The library encodes it automatically; wait for the
   status to become **Finished** (not *Processing* — a video still encoding
   plays as a black frame).
3. Open the video and copy its **Video ID** (a GUID such as
   `32d140e2-4f4e-4a1e-9f0a-1b2c3d4e5f60`). This is the value the site needs —
   **not** the player URL.
4. Paste it into the tutorial's **Video reference** field with
   **Video provider = Bunny Stream**.

### Option C — HTTP API (repeatable uploads)

Two calls: create the video object, then upload the bytes. The upload is
authenticated per library, so the API key must belong to *that* library.

```bash
# 1. create the video object — the response contains the video id
curl --request POST \
  --url https://video.bunnycdn.com/library/$LIBRARY_ID/videos \
  --header "AccessKey: $STREAM_API_KEY" \
  --header 'accept: application/json' \
  --header 'content-type: application/json' \
  --data '{"title":"Xstrahl 100 — setup walkthrough"}'

# 2. upload the file to that video id
curl --request PUT \
  --url https://video.bunnycdn.com/library/$LIBRARY_ID/videos/$VIDEO_ID \
  --header "AccessKey: $STREAM_API_KEY" \
  --header 'accept: application/json' \
  --data-binary '@walkthrough.mp4'
```

- Files over 2 GB, or uploads on a flaky connection, should use Bunny's
  **TUS resumable upload** endpoint instead — the plain PUT has no resume and
  a dropped connection restarts the whole file.
- A `401` here means a wrong or non-Stream key, not a site problem.

> `$STREAM_API_KEY` in these two commands is Bunny's **upload** key. It is not
> `BUNNY_STREAM_SECURITY_KEY`, which is only used to *sign playback* and never
> leaves the server.

---

## 3. Create the tutorial record

Sign in as staff → **Staff dashboard → Tutorials → + New tutorial**
(`/dashboard/tutorials/new/`). With Option A the video is already attached by
the time you get here; the other options need the reference filled in by hand.

| Field | What to put |
|---|---|
| **Title** | Shown in the library and on the player page |
| **Slug** | Leave blank to generate it from the title |
| **Description** | One or two sentences; shows above the player |
| **Thumbnail** | Optional image (extension and size are validated) |
| **Category** | Groups the tutorial in the public library; manage them under **Categories** |
| **Duration (seconds)** | **Required for progress tracking** — see §6. Enter the real length, e.g. `754` for 12:34 |
| **Estimated minutes** | Cosmetic label for the catalog card |
| **Video provider** | **Bunny Stream (signed playback)** — or **YouTube (unlisted)** on a tight budget, see §3a |
| **Video reference** | Bunny: the **video GUID** from step 2 — never a URL. YouTube: the 11-character video id (a watch/youtu.be link is accepted too) |
| **Published** | Off while you check it; on when it is ready |
| **Ordering** | Lower numbers show first inside a category |

Save. The tutorial is edited from the same screen later.

### 3a. YouTube (unlisted) instead of Bunny

Set **Video provider = YouTube (unlisted)** and paste the video id —
`uJr2Ywp4Zx4`, not the whole URL (a URL works, but the id is what is stored).
The player embeds `https://www.youtube-nocookie.com/embed/<id>` with
`rel=0`, so no YouTube cookies are set before play and the end screen stays on
the same channel.

On the YouTube side the video **must** be:

- **Unlisted** — never Public;
- **Embedding allowed** (Visibility → *Allow embedding*);
- not age-restricted and not a Premiere/live-only stream.

What this costs you in protection — read before choosing it:

- The video id is the only secret. It is visible in the iframe URL, in dev
tools, and in YouTube's own right-click menu (*Copy video URL*). **No page we
write can remove that menu**: the player is cross-origin third-party content,
so the browser gives us no access to it. Blocking right-click works for videos
we host ourselves, not inside a YouTube iframe.
- Anyone who has the id can watch the video on youtube.com without signing in.
- YouTube may show "up next" suggestions, even with `rel=0`, on some layouts.

Choose YouTube when the content is training material whose leak is annoying
rather than damaging. Use Bunny (signed, expiring links) when it must not be
shareable.

**Dev/preview shortcut:** setting the provider to *Plain URL* makes the player
use the URL in the reference field directly. That URL reaches the browser
unsigned, so it is for local previews only — never for a published tutorial on
the live site. Prefer a short-lived test file (an MP4 or an HLS manifest).

---

## 4. Give people access

Publishing makes a tutorial *visible*; it does not make it *playable*. Access
is checked on every request (`tutorials/access.py`).

Two ways, both on **Dashboard → Users → (account)**:

- **Per tutorial:** *Grant* next to a tutorial in the per-tutorial access table.
  *Revoke* removes it.
- **Whole library:** *Toggle all-library access* sets the bypass flag — every
  published tutorial opens for that account.

The same grant works from the **tutorial's** side, which is the faster route
when you have just published a new video: **Dashboard → Tutorials → Access**
next to the row (`/dashboard/tutorials/<id>/access/`). That page lists every
account (searchable) with one Grant/Revoke button per person, and keeps you on
the page after each click.

> Grants can be prepared for a draft too, but nothing plays until the tutorial
> is published, the account is approved, and a video is attached.

Accounts also need to be **approved** before any grant is usable; the pending
queue is on the dashboard overview.

Revocation takes effect on the next play attempt. A player that is already
streaming keeps working until its signed link expires (1 hour).

---

## 5. Check it plays

1. Sign in as a user who has access (or use a test account with a grant).
2. Open `/tutorials/<slug>/`. You should see the poster area and a
   **Play tutorial** button.
3. Press play. Behind the button, two calls happen:
   - `POST /tutorials/<slug>/authorize/` → `201` with a one-time token valid
     for **5 minutes**
   - `POST /tutorials/redeem/` → `200` with a signed embed URL valid for
     **1 hour**
4. The video appears. If a spinner sits forever, open the browser console: a
   `403`/`503` from either call points at the table in §7.

---

## 6. Progress and completion

The player reports watch time in heartbeats; the server decides what that
means.

- Percent = `seconds_watched ÷ duration_seconds`. **If duration is 0 the
  percentage never moves** — this is the usual cause of "progress stuck".
- A single report can add at most **60 seconds**, so a tampered payload cannot
  skip a video.
- **90 %** watched marks the tutorial complete, and a completion date is
  stored.
- Progress is never used as proof of authorization — revoking a grant closes
  the video no matter how much was watched.

Progress per account is visible on **Dashboard → Users → (account) → Progress**.

---

## 7. When it does not work

| Symptom | Cause | Fix |
|---|---|---|
| `503 provider_not_configured` | Bunny env vars missing, or the tutorial has no video reference | Set the two variables and restart; check the GUID is filled in |
| `403 token_invalid` | The 5-minute authorization token expired, or was already used (they are one-time) | Reload the page and press play again |
| `403 not_authorized` | Access was revoked between pressing play and redemption, or the account has no grant | Re-grant on the user page |
| `The video for this tutorial is not available yet.` | Provider is *No video yet* | Set the provider and GUID |
| Video plays, progress stays at 0 % | `duration_seconds` is 0 | Edit the tutorial and enter the real length |
| Black player, audio only | Bunny is still encoding | Wait for **Finished** |
| `503` on every tutorial, keys look correct | Keys set in the wrong app / not restarted | Re-check cPanel environment, restart the app |

---

## 8. Publishing checklist

- [ ] Bunny library shows the video as **Finished**
- [ ] Tutorial has a title, category and **duration in seconds**
- [ ] Video attached: uploaded from the form (Option A), or provider is
      **Bunny Stream** with the **GUID** pasted in the reference (no `https://`)
- [ ] Tested with a granted, approved account — video actually plays
- [ ] Thumbnail uploaded, or a deliberate decision to ship without one
- [ ] `is_published` ticked
- [ ] Access granted to the right people (per tutorial or all-library)

---

## 9. Limits worth knowing

- **No DRM.** The signed embed is a bearer link: anyone who copies it can watch
  until it expires (1 hour). Screen recording cannot be blocked by any HTML
  player. Bunny Enterprise DRM exists at extra cost — see
  [PHASE6_VIDEO_HOSTING_OPTIONS.md](PHASE6_VIDEO_HOSTING_OPTIONS.md).
- **YouTube unlisted is not private** (see §3a): the id is copyable, and the
  right-click menu inside the player belongs to YouTube, not to us.
- **Self-hosted `Plain URL` videos** get the strongest client-side guards we
  can apply (`nodownload`, no picture-in-picture, no right-click/drag on the
  player), but the URL itself is still unsigned.
- **One sign-in per play.** Opening the same tutorial in a second tab requests
  a fresh token; that is normal.
- **Deleting a tutorial deletes its grants and progress**, but not the video in
  Bunny — remove that in the Bunny dashboard.

---

## Sources

- Bunny Stream HTTP upload: https://bunny.net/docs/stream/http-api
- Bunny Stream API reference (upload video):
  https://bunny.net/docs/api-reference/stream/manage-videos/upload-video
- TUS resumable uploads: https://bunny.net/docs/stream/tus-resumable-uploads
- Playback token authentication: https://bunny.net/docs/stream/token-authentication
