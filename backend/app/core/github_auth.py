import hashlib
import hmac
import logging
import os

logger = logging.getLogger("github_auth")


def verify_webhook_signature(payload_body: bytes, signature_header: str) -> bool:
    """GitHub signs every webhook with HMAC-SHA256 using your webhook secret.
    Recompute it and compare. If they don't match, the request didn't come
    from GitHub and must be rejected."""
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
    if not secret:
        logger.error("GITHUB_WEBHOOK_SECRET is not set; rejecting all webhooks")
        return False    # fail closed
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), payload_body, hashlib.sha256).hexdigest()
    # compare_digest avoids timing attacks; never compare secrets with ==
    return hmac.compare_digest(expected, signature_header)