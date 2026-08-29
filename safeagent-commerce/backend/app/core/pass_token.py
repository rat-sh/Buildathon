"""HMAC signing for in-process ValidatorPassToken objects."""

import hashlib
import hmac

from app.core.config import settings
from app.schemas.validator import ValidatorPassToken


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
    """Verify token signature; rejects missing or tampered tokens."""
    if not token.signature:
        return False
    expected = hmac.new(
        settings.APP_SECRET_KEY.encode("utf-8"),
        _token_payload(token).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(token.signature, expected)
