"""
models/product.py — Product catalog model
==========================================
Safety contracts:
  - price is stored in PAISA (integer) to avoid floating-point errors
  - is_active flag must be True for any product to enter a cart
  - stock is decremented only by the inventory service (not agents)
  - Validator checks both is_active and stock before allowing payment
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Product(Base):
    """
    Represents a product in the merchant catalog.

    Price is stored in paisa (100 paisa = ₹1) to ensure exact integer
    arithmetic. Never store prices as floats — floating point errors can
    cause price mismatch validator failures or worse, undercharging.
    """

    __tablename__ = "products"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Catalog attributes ────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    # ── Pricing — stored in PAISA (integer), never float ─────────────────────
    # SAFETY: Validator checks charged_price_paisa <= price_paisa
    price_paisa: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    # ── Inventory ─────────────────────────────────────────────────────────────
    # SAFETY: Validator checks quantity_requested <= stock_quantity
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ── Status — MUST be True for Validator to allow purchase ─────────────────
    # SAFETY: Validator rejects ITEM_INACTIVE if is_active = False
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Additional attributes (JSON as text for SQLite compat) ────────────────
    # Store things like size, color, weight etc.
    attributes_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Affinity data for Suggestion Agent ───────────────────────────────────
    # Comma-separated product IDs that are frequently bought together
    # The Suggestion Agent READS this — it never writes to it
    affinity_product_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
    cart_items: Mapped[list["CartItem"]] = relationship(
        "CartItem", back_populates="product"
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id} sku={self.sku} price_paisa={self.price_paisa}>"

    @property
    def price_rupees(self) -> float:
        """Human-readable price in rupees. Never use for calculations."""
        return self.price_paisa / 100
