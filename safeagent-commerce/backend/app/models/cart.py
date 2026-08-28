"""
models/cart.py — Shopping cart + cart items
============================================
Safety contracts:
  - explicitly_accepted: Validator checks this for add-on items
    The Suggestion Agent sets it to False. Only a human/AI explicit
    accept action (via API endpoint) can flip it to True.
    The Suggestion Agent is FORBIDDEN from setting this to True itself.
  - Cart has a session_id (human) or buyer_id (AI) for ownership
  - Cart is locked once a Validator PASS is issued (status = 'locked')
  - No payment can proceed on an 'open' cart — must be 'locked' first
"""

from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CartStatus(str, PyEnum):
    """
    Cart lifecycle states.
    - open: items being added/removed
    - locked: Validator PASS issued, awaiting payment — no item changes allowed
    - paid: payment captured successfully
    - abandoned: timed out or explicitly cancelled
    - failed: payment failed after max retries
    """
    OPEN = "open"
    LOCKED = "locked"       # Validator PASS issued
    PAID = "paid"           # Payment captured
    ABANDONED = "abandoned"
    FAILED = "failed"       # Max retries exhausted


class Cart(Base):
    """
    A shopping cart belonging to either a human session or an AI buyer.
    Tracks status through its lifecycle.
    """

    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Ownership — one of these will be set ─────────────────────────────────
    session_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    buyer_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    # ── Status ────────────────────────────────────────────────────────────────
    status: Mapped[CartStatus] = mapped_column(
        Enum(CartStatus), default=CartStatus.OPEN, nullable=False
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    items: Mapped[list["CartItem"]] = relationship(
        "CartItem", back_populates="cart", cascade="all, delete-orphan"
    )
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="cart")

    @property
    def total_paisa(self) -> int:
        """Sum of all line totals. Used by Validator for limit checks."""
        return sum(item.line_total_paisa for item in self.items)

    def __repr__(self) -> str:
        return f"<Cart id={self.id} status={self.status} items={len(self.items)}>"


class CartItem(Base):
    """
    A single product line in a cart.

    CRITICAL SAFETY FIELD: explicitly_accepted
    ------------------------------------------
    For items added via the Suggestion Agent (is_suggestion=True):
      - Default is False — NOT accepted
      - Only flipped to True by an explicit API call from the human or
        a verified AI buyer policy
      - The Validator BLOCKS any cart where is_suggestion=True AND
        explicitly_accepted=False (reason: ADDON_NOT_ACCEPTED)
      - The Suggestion Agent code is FORBIDDEN from setting this to True
    """

    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cart_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # ── Price snapshot — taken at time of add-to-cart ─────────────────────────
    # This is the price the customer was SHOWN. Validator checks this ≤ catalog price.
    # Stored in paisa (integer). If catalog price drops, this is safe.
    # If catalog price rises, Validator will BLOCK (PRICE_MISMATCH).
    charged_price_paisa: Mapped[int] = mapped_column(Integer, nullable=False)

    # ── Suggestion / upsell tracking ─────────────────────────────────────────
    # Was this item added by the Suggestion Agent?
    is_suggestion: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # SAFETY: Validator checks this is True for all suggestion items.
    # ONLY set to True via an explicit /cart/accept-suggestion endpoint.
    # The Suggestion Agent MUST NOT set this to True itself.
    explicitly_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────────
    cart: Mapped["Cart"] = relationship("Cart", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="cart_items")

    @property
    def line_total_paisa(self) -> int:
        """Total cost for this line item in paisa."""
        return self.charged_price_paisa * self.quantity

    def __repr__(self) -> str:
        return (
            f"<CartItem product_id={self.product_id} qty={self.quantity} "
            f"price={self.charged_price_paisa} accepted={self.explicitly_accepted}>"
        )
