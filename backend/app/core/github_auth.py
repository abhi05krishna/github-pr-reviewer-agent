import hashlib
import hmac
import os

WEBHOOK_SECRET = os.environ["GITHUB_WEBHOOK_SECRET"].encode()

def verify_webhook_signature(payload_body: bytes, signature_header: str) -> bool:
    """GitHub signs every webhook with HMAC-SHA256 using your webhook secret.
    Recompute it ourselves and compare - if they don't match, the request
    didn't genuinely come from GitHub, so we must reject it."""
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(WEBHOOK_SECRET, payload_body, hashlib.sha256).hexdigest()
    # hmac.compare_digest prevents timing attacks - never use `==` for secret comparison
    return hmac.compare_digest(expected, signature_header)