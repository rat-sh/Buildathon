"""
models/order.py — Razorpay order state machine
===============================================
State machine:
  CREATED → AUTHORIZED → CAPTURED
                       → FAILED
  CREATED → FAILED (if payment never attempted)

Safety contracts:
  - Order is ONLY created by Payment Agent (never by agents or LLMs)
  - Order stores the Razorpay order_id for webhook reconciliation
  - idempotency_key is unique — Validator checks this before Payment Agent runs
  - attempt_count is hard-capped at MAX_RETRIES (limits.py constant)
  - Webhook HMAC signature must be verified before status can move to CAPTURED
"""

from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OrderStatus(str, PyEnum):
    """
    Order lifecycle — mirrors Razorpay order states with additions.

    CREATED     : Razorpay order created, awaiting payment
    AUTHORIZED  : Payment authorized (pre-capture state)
    CAPTURED    : Payment captured — final success state
    FAILED      : Payment failed or max retries exhausted
    REFUNDED    : Payment refunded (out of scope for buildathon but modeled)
    """
    CREATED = "created"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"


class Order(Base):
    """
    An order created by the Payment Agent after Validator PASS.

    SAFETY: This table is written to ONLY by:
      1. Payment Agent (on create)
      2. Webhook handler (on status update, after HMAC verify)

    No other code path may write to this table.
    """

    __tablename__ = "orders"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Foreign keys ──────────────────────────────────────────────────────────
    cart_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("carts.id"), nullable=False, index=True
    )

    # ── Razorpay identifiers ──────────────────────────────────────────────────
    razorpay_order_id: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True, index=True
    )
    razorpay_payment_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    razorpay_signature: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )

    # ── Idempotency — Validator checks uniqueness before Payment Agent runs ───
    # SAFETY: If this key exists in DB, Validator returns DUPLICATE_IDEMPOTENCY_KEY
    idempotency_key: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )

    # ── Amount — always in paisa (integer) ───────────────────────────────────
    amount_paisa: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    # ── State machine ─────────────────────────────────────────────────────────
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.CREATED, nullable=False
    )

    # ── Retry tracking — hard cap enforced by Payment Agent ──────────────────
    # SAFETY: Payment Agent refuses to attempt if attempt_count >= MAX_RETRIES
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ── Ownership ─────────────────────────────────────────────────────────────
    # Identifies whether this is a human or AI buyer order
    session_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    buyer_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # ── Failure tracking ──────────────────────────────────────────────────────
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
    captured_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    cart: Mapped["Cart"] = relationship("Cart", back_populates="orders")

    # ── Table-level constraints ───────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_order_idempotency_key"),
    )

    def __repr__(self) -> str:
        return (
            f"<Order id={self.id} rzp={self.razorpay_order_id} "
            f"status={self.status} attempts={self.attempt_count}>"
        )
