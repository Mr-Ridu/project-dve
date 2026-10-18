"""Bunny Stream signed playback (Phase 6, decided provider).

User-approved decision: Bunny Stream, signed tokens only (no DRM).

Three signing schemes, exactly per Bunny docs (sources in the docstring,
verified October 2026 against bunny.net/docs):

* Embed tokens protect the Bunny iframe player:
      SHA256_HEX(security_key + video_id + expires_unix_seconds)
      → e.g. https://player.mediadelivery.net/embed/{library}/{video}
        ?token=<hex>&expires=<unix>

* Advanced CDN token (HMAC-SHA256):
      HS256- + BASE64URL(HMAC-SHA256(key, signature_path + expires))
      with +→-, /→_ and "=" padding removed. signature_path is the URL
      path, or the token_path override for directory content. An IP,
      when used, is signed but never appended to the URL.

* Query-string vs path-based embedding: for HLS/DASH the token must be
  embedded in the URL *path* (/bcdn_token=...&expires=...&token_path=...)
  because players resolve relative segment URLs against the manifest's
  path — path-based tokens then automatically cover every segment
  request. Query-string format is for direct file URLs only.

Keys arrive via environment (BUNNY_STREAM_SECURITY_KEY, BUNNY_STREAM_LIBRARY_ID)
and never enter the repository or chat.

Sources: https://bunny.net/docs/stream/token-authentication ,
https://bunny.net/docs/cdn/security/token-authentication/advanced
"""
import hashlib
import hmac
from base64 import urlsafe_b64encode
from urllib.parse import quote, urlencode

HS256_PREFIX = "HS256-"


def embed_token(security_key: str, video_id: str, expires: int) -> str:
    """SHA256_HEX(security_key + video_id + expires) — the documented embed scheme."""
    return hashlib.sha256(f"{security_key}{video_id}{expires}".encode()).hexdigest()


def embed_url(library_id: str, video_id: str, security_key: str, expires: int) -> str:
    query = urlencode({
        "token": embed_token(security_key, video_id, expires),
        "expires": expires,
    })
    return f"https://player.mediadelivery.net/embed/{library_id}/{video_id}?{query}"


def cdn_token(
    security_key: str, signature_path: str, expires: int, user_ip: str | None = None
) -> str:
    """Advanced HLS-CDN token per the advanced-token docs.

    signature_path = the URL path, or the token_path override for directory
    tokens. user_ip, when given, joins the signed message (after expires) but
    is never part of the URL.
    """
    message = signature_path + str(expires)
    if user_ip:
        message += user_ip + "1"  # doc: signed-data order path+expires+ip; flag
    digest = hmac.new(security_key.encode(), message.encode(), hashlib.sha256).digest()
    b64 = (
        urlsafe_b64encode(digest).decode().replace("+", "-").replace("/", "_").rstrip("=")
    )
    return HS256_PREFIX + b64


def signed_direct_url(
    cdn_hostname: str, path: str, security_key: str, expires: int, user_ip: str | None = None
) -> str:
    """Query-string form — direct file URLs only, NOT for HLS manifests."""
    return (
        f"https://{cdn_hostname}{path}"
        f"?token={cdn_token(security_key, path, expires, user_ip)}&expires={expires}"
    )


def signed_hls_directory_url(
    cdn_hostname: str,
    directory_path: str,
    object_path: str,
    security_key: str,
    expires: int,
    user_ip: str | None = None,
) -> str:
    """Path-based directory token — the required form for HLS/DASH playback.

    directory_path must end with "/" and covers the manifest plus every
    segment beneath it. object_path is the manifest URL after the host; the
    player's relative segment requests inherit authentication from the path.
    """
    if not directory_path.endswith("/"):
        directory_path += "/"
    token = cdn_token(security_key, directory_path, expires, user_ip)
    return (
        f"https://{cdn_hostname}/bcdn_token={token}&expires={expires}"
        f"&token_path={quote(directory_path, safe='')}{object_path}"
    )
