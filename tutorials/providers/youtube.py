"""YouTube unlisted playback (budget option, no third-party bill).

What this does and does not protect
-----------------------------------
An *unlisted* YouTube video is not private. The 11-character video id is the
only secret: anyone who obtains it can open the same video on youtube.com, and
the id is visible in the iframe URL, in the browser's dev tools and in any
"copy video address" from YouTube's own player menu. No page we write can
change that — the player is third-party content in a cross-origin frame.

So this provider gives you:

* the video never appears in a public search or channel listing (unlisted);
* our own access rule still gates the page and the playback token, so a member
  can only *reach* the player through /tutorials/<slug>/authorize/;
* no YouTube cookies are set until the viewer presses play, because the embed
  uses the privacy-enhanced youtube-nocookie.com domain.

It does not stop a viewer who is determined enough to copy the id. If the
content must not be redistributable, self-host (Bunny/R2) so a signed,
expiring URL is the only way in.

Sources: https://support.google.com/youtube/answer/157177 (unlisted videos),
https://developers.google.com/youtube/player_parameters (rel, modestbranding,
iv_load_policy, playsinline), https://support.google.com/youtube/answer/171780
(privacy-enhanced mode).
"""
import re
from urllib.parse import parse_qs, urlencode, urlparse

# YouTube ids are exactly 11 characters of this alphabet.
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

_YT_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
    "youtu.be",
}

# /embed/<id>, /shorts/<id>, /live/<id>, /v/<id>
_PATH_ID_PREFIXES = {"embed", "shorts", "live", "v"}

PRIVACY_HOST = "www.youtube-nocookie.com"


def video_id(ref):
    """Return the 11-char id from a bare id or any common YouTube URL.

    Accepts: ``dQw4w9WgXcQ``, ``https://youtu.be/dQw4w9WgXcQ?si=...``,
    ``https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s``,
    ``https://www.youtube.com/embed/dQw4w9WgXcQ``, ``/shorts/...``, ``/live/...``.
    Returns None for anything else (a playlist link, a channel, garbage), so the
    redeem view can answer 503 instead of handing the browser a broken source.
    """
    ref = (ref or "").strip()
    if not ref:
        return None
    if _ID_RE.match(ref):
        return ref

    parsed = urlparse(ref if "//" in ref else f"https://{ref}")
    host = (parsed.netloc or "").lower().split("@")[-1]
    if host not in _YT_HOSTS:
        return None

    parts = [p for p in parsed.path.split("/") if p]
    if host == "youtu.be":
        candidate = parts[0] if parts else ""
        return candidate if _ID_RE.match(candidate) else None

    if parts and parts[0] in _PATH_ID_PREFIXES and len(parts) > 1:
        return parts[1] if _ID_RE.match(parts[1]) else None

    candidate = (parse_qs(parsed.query).get("v") or [""])[0]
    return candidate if _ID_RE.match(candidate) else None


def embed_url(video_id_value, *, start=0):
    """Privacy-enhanced embed URL.

    rel=0 keeps the end screen to the same channel, modestbranding=1 trims the
    YouTube chrome, iv_load_policy=3 removes annotations, playsinline keeps iOS
    from hijacking playback into full screen.
    """
    params = {
        "rel": "0",
        "modestbranding": "1",
        "iv_load_policy": "3",
        "playsinline": "1",
    }
    if start:
        params["start"] = str(int(start))
    return f"https://{PRIVACY_HOST}/embed/{video_id_value}?{urlencode(params)}"
