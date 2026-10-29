"""Time-limited signatures for media links used by installed mobile clients."""

import hashlib
import hmac
import time
from urllib.parse import quote, urlencode

from flask import current_app, request


MEDIA_TTL_SECONDS = 30 * 24 * 60 * 60
EXPIRY_BUCKET_SECONDS = 60 * 60
MEDIA_ROUTES = {
    "photo": "/api/photos/{filename}",
    "chat": "/api/chat/images/{filename}",
}


def _signature(scope, filename, expires):
    secret = current_app.config["SECRET_KEY"]
    message = f"{scope}:{filename}:{expires}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def signed_media_url(scope, filename, absolute=True):
    route = MEDIA_ROUTES[scope]
    expires = (
        int(time.time()) + MEDIA_TTL_SECONDS
    ) // EXPIRY_BUCKET_SECONDS * EXPIRY_BUCKET_SECONDS
    query = urlencode(
        {
            "expires": expires,
            "sig": _signature(scope, filename, expires),
        }
    )
    path = route.format(filename=quote(filename, safe="")) + f"?{query}"
    if absolute:
        base_url = current_app.config.get("PUBLIC_BASE_URL")
        return (base_url or request.host_url.rstrip("/")) + path
    return path


def valid_media_signature(scope, filename):
    expires = request.args.get("expires", type=int)
    signature = request.args.get("sig", "")
    if not expires or expires < int(time.time()) or not signature:
        return False
    expected = _signature(scope, filename, expires)
    return hmac.compare_digest(signature, expected)
