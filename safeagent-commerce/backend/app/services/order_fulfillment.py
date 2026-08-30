"""
services/order_fulfillment.py — Idempotent order capture + stock fulfillment
=============================================================================
Single entry point for marking orders CAPTURED after verified payment.
Used by webhook handler AND client-side verify-payment — never duplicate stock logic.
"""

from datetime import datetime, timezone
from typing import Literal, Optional

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cart import Cart, CartItem, CartStatus
from app.models.order import Order, OrderStatus
from app.services.audit_service import AuditService

logger = structlog.get_logger(__name__)

CaptureSource = Literal["webhook", "verify"]


async def mark_order_captured(
    db: AsyncSession,
    order: Order,
    *,
    payment_id: Optional[str] = None,
    source: CaptureSource,
    event_type: Optional[str] = None,
) -> bool:
    """
    Idempotently capture an order: CAPTURED + cart PAID + stock decrement once.

    Uses atomic UPDATE ... WHERE status != CAPTURED so only one concurrent caller
    performs stock/cart/audit side effects (same pattern as cart lock in PaymentAgent).

    Returns True if this call performed the capture transition.
    Returns False if the order was already CAPTURED (no stock change).
    """
    captured_at = datetime.now(timezone.utc)
    capture_values: dict = {
        "status": OrderStatus.CAPTURED,
        "captured_at": captured_at,
    }
    if payment_id:
        capture_values["razorpay_payment_id"] = payment_id

    capture_result = await db.execute(
        update(Order)
        .where(Order.id == order.id, Order.status != OrderStatus.CAPTURED)
        .values(**capture_values)
    )
    if capture_result.rowcount != 1:
        logger.info(
            "Order already captured — skipping stock decrement",
            order_id=order.id,
            source=source,
        )
        return False

    order = (await db.execute(select(Order).where(Order.id == order.id))).scalar_one()

    cart = (await db.execute(select(Cart).where(Cart.id == order.cart_id))).scalar_one_or_none()
    if cart:
        cart.status = CartStatus.PAID

    stmt_items = (
        select(CartItem)
        .where(CartItem.cart_id == order.cart_id)
        .options(selectinload(CartItem.product))
    )
    cart_items = (await db.execute(stmt_items)).scalars().all()
    for cart_item in cart_items:
        if cart_item.product:
            cart_item.product.stock_quantity = max(
                0, cart_item.product.stock_quantity - cart_item.quantity
            )

    await db.commit()

    evidence = {
        "source": source,
        "razorpay_order_id": order.razorpay_order_id,
        "razorpay_payment_id": order.razorpay_payment_id,
        "amount_paisa": order.amount_paisa,
    }
    if event_type:
        evidence["event_type"] = event_type

    actor = "webhook_handler" if source == "webhook" else "api"
    action = "payment_captured" if source == "webhook" else "verify_payment"

    await AuditService.log_event(
        db=db,
        actor=actor,
        action=action,
        decision="PASS",
        session_id=order.session_id,
        buyer_id=order.buyer_id,
        target_type="order",
        target_id=str(order.id),
        evidence=evidence,
        message=f"Payment for order #{order.id} captured via {source}.",
    )

    logger.info("Order captured and stock decremented", order_id=order.id, source=source)
    return True
