"""HMAC signing for in-process ValidatorPassToken objects."""

import hashlib
import hmac
import time

from app.core.config import settings
from app.schemas.validator import ValidatorPassToken

# PASS tokens are short-lived — must reach PaymentAgent within this window
PASS_TOKEN_TTL_SECONDS = 900  # 15 minutes


def _token_payload(token: ValidatorPassToken) -> str:
    return "|".join([
        str(token.cart_id),
        token.idempotency_key,
        str(token.total_paisa),
        token.session_id or "",
        token.buyer_id or "",
        str(token.is_ai_buyer),
        str(token.issued_at_timestamp),
    ])


def sign_pass_token(token: ValidatorPassToken) -> ValidatorPassToken:
    """Attach HMAC-SHA256 signature over token fields using APP_SECRET_KEY."""
    signature = hmac.new(
        settings.APP_SECRET_KEY.encode("utf-8"),
        _token_payload(token).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    token.signature = signature
    return token


def verify_pass_token(token: ValidatorPassToken) -> bool:
    """Verify token signature and expiry; rejects missing, tampered, or stale tokens."""
    if not token.signature:
        return False
    if time.time() - token.issued_at_timestamp > PASS_TOKEN_TTL_SECONDS:
        return False
    expected = hmac.new(
        settings.APP_SECRET_KEY.encode("utf-8"),
        _token_payload(token).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(token.signature, expected)
