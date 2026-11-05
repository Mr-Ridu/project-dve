"""Server-side upload to Bunny Stream, so staff never open bunny.net.

Two HTTP API calls per video (Bunny Stream HTTP API, verified October 2026
against bunny.net/docs/stream/http-api):

    1. POST /library/{library_id}/videos           -> creates the video object
    2. PUT  /library/{library_id}/videos/{guid}    -> streams the file bytes

The file passes through this server only; nothing is stored here. If the byte
upload fails after the video object was created, the orphan is deleted again —
a half-uploaded video in the Bunny library is worse than no video.

Credentials: BUNNY_STREAM_API_KEY is the Stream **management** key from
bunny.net -> Stream -> your library -> API. It is a different value from
BUNNY_STREAM_SECURITY_KEY (the token-authentication key that signs playback),
and neither one ever reaches the browser or the audit log.

Source: https://bunny.net/docs/stream/http-api
"""
import json
import urllib.error
import urllib.request

from django.conf import settings

API_BASE = "https://video.bunnycdn.com"
CREATE_TIMEOUT = 60
UPLOAD_TIMEOUT = 3600  # a large file can take a while on a home connection
DELETE_TIMEOUT = 60


class UploadError(Exception):
    """A failure safe to show to staff: never contains credentials or bodies."""


def _config():
    """Read credentials; raise a self-explanatory error when unset."""
    api_key = (getattr(settings, "BUNNY_STREAM_API_KEY", "") or "").strip()
    library_id = (getattr(settings, "BUNNY_STREAM_LIBRARY_ID", "") or "").strip()
    missing = [
        name
        for name, value in (
            ("BUNNY_STREAM_API_KEY", api_key),
            ("BUNNY_STREAM_LIBRARY_ID", library_id),
        )
        if not value
    ]
    if missing:
        raise UploadError(
            "Video upload is not configured yet: "
            + " and ".join(missing)
            + " missing (set them in the app environment and restart)."
        )
    return api_key, library_id


def _explain(http_error):
    """Translate HTTP status codes into operator language — no bodies, no keys."""
    code = http_error.code
    if code in (401, 403):
        return (
            "Bunny rejected the API key (HTTP %s). Check BUNNY_STREAM_API_KEY: it is "
            "the Stream *management* key from bunny.net -> Stream -> your library -> "
            "API, not the token-authentication key." % code
        )
    if code == 404:
        return "Bunny library not found (HTTP 404). Check BUNNY_STREAM_LIBRARY_ID."
    if code == 413:
        return "Bunny refused the file: it is larger than this account allows."
    return "Bunny Stream upload failed (HTTP %s). Nothing was saved — try again." % code


def _call(
    method, url, *, api_key, body=None, content_type=None, content_length=None, timeout=60
):
    """One authenticated request; raises UploadError on any failure."""
    headers = {"AccessKey": api_key, "accept": "application/json"}
    if content_type:
        headers["content-type"] = content_type
    if content_length is not None:
        # Explicit length keeps http.client streaming the body in blocks instead
        # of falling back to chunked transfer, which Bunny does not accept.
        headers["Content-length"] = str(content_length)
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        raise UploadError(_explain(exc)) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UploadError(
            "Could not reach Bunny Stream (network problem). Nothing was saved — "
            "check the connection and try again."
        ) from exc


def create_video(title, api_key, library_id):
    """Create the empty video object; return its GUID."""
    status, body = _call(
        "POST",
        f"{API_BASE}/library/{library_id}/videos",
        api_key=api_key,
        body=json.dumps({"title": (title or "Untitled")[:200]}).encode("utf-8"),
        content_type="application/json",
        timeout=CREATE_TIMEOUT,
    )
    try:
        guid = (json.loads(body or b"{}").get("guid") or "").strip()
    except ValueError as exc:
        raise UploadError("Bunny returned an unreadable response; nothing was saved.") from exc
    if status not in (200, 201) or not guid:
        raise UploadError("Bunny created no video id; nothing was saved.")
    return guid


def delete_video(guid, api_key, library_id):
    """Best-effort cleanup for an orphan created before a failed upload."""
    try:
        _call(
            "DELETE",
            f"{API_BASE}/library/{library_id}/videos/{guid}",
            api_key=api_key,
            timeout=DELETE_TIMEOUT,
        )
    except UploadError:
        pass  # never mask the original error with a cleanup failure


def upload_file(uploaded_file, *, title):
    """Create the Bunny video, stream the bytes, return the video GUID.

    `uploaded_file` is a Django UploadedFile (or anything with read/seek/size);
    it is streamed, never read into memory whole.
    """
    api_key, library_id = _config()
    guid = create_video(title, api_key, library_id)

    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    size = getattr(uploaded_file, "size", None)

    try:
        _call(
            "PUT",
            f"{API_BASE}/library/{library_id}/videos/{guid}",
            api_key=api_key,
            body=uploaded_file,
            content_type="application/octet-stream",
            content_length=size,
            timeout=UPLOAD_TIMEOUT,
        )
    except UploadError:
        delete_video(guid, api_key, library_id)  # no half-uploaded orphans
        raise
    return guid
