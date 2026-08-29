"""
api/payment_verify.py — POST /api/verify-payment
==================================================
Verifies the Razorpay payment signature returned by the checkout modal.

SAFETY CONTRACT (NON-NEGOTIABLE):
  1. Signature MUST be verified via HMAC-SHA256 before marking order paid.
  2. On signature mismatch → return HTTP 400. Order stays AUTHORIZED.
  3. KEY_SECRET is read from settings — NEVER from the request body.
  4. On success → order is marked CAPTURED and cart marked PAID.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_razorpay_payment_signature
from app.models.cart import Cart, CartStatus
from app.models.order import Order, OrderStatus
from app.services.audit_service import AuditService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["payment"])


class PaymentVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    session_id: str | None = None


@router.post("/verify-payment")
async def verify_payment(
    req: PaymentVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify Razorpay payment signature and mark order as CAPTURED.

    Called by frontend immediately after the Razorpay checkout modal
    reports payment.success with all three verification fields.

    On HMAC mismatch: returns HTTP 400 — order stays un-captured.
    On PASS: marks Order → CAPTURED, Cart → PAID.
    """
    # ── STEP 1: HMAC Signature Verification ──────────────────────────────────
    is_valid = verify_razorpay_payment_signature(
        razorpay_order_id=req.razorpay_order_id,
        razorpay_payment_id=req.razorpay_payment_id,
        razorpay_signature=req.razorpay_signature,
        key_secret=settings.RAZORPAY_KEY_SECRET,
    )

    if not is_valid:
        logger.warning(
            "Payment signature verification FAILED",
            order_id=req.razorpay_order_id,
            payment_id=req.razorpay_payment_id,
        )
        await AuditService.log_event(
            db=db, actor="api", action="verify_payment", decision="BLOCK",
            session_id=req.session_id, reason_code="INVALID_PAYMENT_SIGNATURE",
            target_type="order",
            evidence={"razorpay_order_id": req.razorpay_order_id, "razorpay_payment_id": req.razorpay_payment_id},
            message="Payment signature verification failed — order not captured.",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment signature verification failed. Payment not captured.",
        )

    # ── STEP 2: Find order and mark CAPTURED ─────────────────────────────────
    order = (await db.execute(
        select(Order).where(Order.razorpay_order_id == req.razorpay_order_id)
    )).scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    if order.status != OrderStatus.CAPTURED:
        order.status = OrderStatus.CAPTURED
        order.razorpay_payment_id = req.razorpay_payment_id
        order.captured_at = datetime.now(timezone.utc)

        cart = (await db.execute(select(Cart).where(Cart.id == order.cart_id))).scalar_one_or_none()
        if cart:
            cart.status = CartStatus.PAID

        await db.commit()

        await AuditService.log_event(
            db=db, actor="api", action="verify_payment", decision="PASS",
            session_id=req.session_id or order.session_id,
            target_type="order", target_id=str(order.id),
            evidence={
                "razorpay_order_id": req.razorpay_order_id,
                "razorpay_payment_id": req.razorpay_payment_id,
                "amount_paisa": order.amount_paisa,
            },
            message=f"Payment verified and captured for order #{order.id}.",
        )

    return {
        "status": "captured",
        "order_id": order.id,
        "razorpay_order_id": req.razorpay_order_id,
        "razorpay_payment_id": req.razorpay_payment_id,
        "amount_rupees": order.amount_paisa / 100,
        "message": "Payment verified and captured successfully.",
    }
