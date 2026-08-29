"""Rate limiting for checkout and cart mutation endpoints."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def rate_limit_key(request: Request) -> str:
    """Prefer AI buyer API key; fall back to client IP."""
    buyer_key = request.headers.get("X-AI-Buyer-Key")
    if buyer_key:
        return f"buyer:{buyer_key[:32]}"
    return get_remote_address(request)


limiter = Limiter(key_func=rate_limit_key)

# Shared limits
CART_MUTATION_LIMIT = "30/minute"
CHECKOUT_LIMIT = "10/minute"
