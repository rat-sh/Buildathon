"""Cart ownership checks — prevent IDOR on session/buyer-scoped carts."""

from typing import Optional

from fastapi import HTTPException, status

from app.models.cart import Cart


def assert_cart_owned_by_session(cart: Cart, session_id: Optional[str]) -> None:
    """Human chat flow: cart.session_id must match the request session."""
    if not session_id or cart.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cart access denied: session does not own this cart.",
        )


def assert_cart_owned_by_buyer(cart: Cart, buyer_id: Optional[str]) -> None:
    """AI buyer flow: cart.buyer_id must match the authenticated buyer."""
    if not buyer_id or cart.buyer_id != buyer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cart access denied: buyer does not own this cart.",
        )
