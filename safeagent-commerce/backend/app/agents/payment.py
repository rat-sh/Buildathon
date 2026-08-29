"""
agents/payment.py — Payment Execution Agent
===========================================
SAFETY CONTRACT (NON-NEGOTIABLE):
  1. ONLY component allowed to interact with Razorpay.
  2. STRICT REQUIREMENT: Must receive a valid ValidatorPassToken issued by ValidatorAgent.
     Without a valid ValidatorPassToken, execute_payment() IMMEDIATELY RAISES ValueError.
  3. Enforces MAX_PAYMENT_RETRIES (2 max attempts per order).
  4. Locks the cart to CartStatus.LOCKED before order creation.
  5. Every payment attempt logs an immutable AuditEvent.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.limits import MAX_PAYMENT_RETRIES
from app.models.cart import Cart, CartStatus
from app.models.order import Order, OrderStatus
from app.schemas.validator import ValidatorPassToken
from app.services.audit_service import AuditService
from app.services.razorpay_service import RazorpayService

logger = structlog.get_logger(__name__)


class PaymentAgent:
    """
    Payment Agent responsible for creating Razorpay Orders and recording
    order state in DB after Validator verification.
    """

    def __init__(self, razorpay_service: Optional[RazorpayService] = None):
        self.razorpay_service = razorpay_service or RazorpayService()

    async def execute_payment(
        self,
        db: AsyncSession,
        pass_token: ValidatorPassToken,
    ) -> Dict[str, Any]:
        """
        Execute payment order creation for a validated cart.

        SAFETY CHECK: pass_token MUST be a valid ValidatorPassToken instance.

        Args:
            db: Async database session
            pass_token: Token granted by ValidatorAgent on PASS

        Returns:
            Dictionary containing order metadata and Razorpay checkout options
        """
        # ── SAFETY GATE ENFORCEMENT ───────────────────────────────────────────
        if not isinstance(pass_token, ValidatorPassToken):
            logger.critical(
                "SECURITY VIOLATION: PaymentAgent invoked without valid ValidatorPassToken!",
                received_type=type(pass_token).__name__,
            )
            raise ValueError(
                "SECURITY ERROR: Payment Agent requires a valid ValidatorPassToken. "
                "No payment can be initiated without Validator PASS."
            )

        logger.info(
            "PaymentAgent executing order creation",
            cart_id=pass_token.cart_id,
            idempotency_key=pass_token.idempotency_key,
            total_paisa=pass_token.total_paisa,
        )

        # ── Atomic cart lock (OPEN → LOCKED); second concurrent caller gets rowcount 0 ─
        lock_result = await db.execute(
            update(Cart)
            .where(Cart.id == pass_token.cart_id, Cart.status == CartStatus.OPEN)
            .values(status=CartStatus.LOCKED)
        )
        if lock_result.rowcount != 1:
            cart = (await db.execute(select(Cart).where(Cart.id == pass_token.cart_id))).scalar_one_or_none()
            status_val = cart.status.value if cart else "missing"
            raise RuntimeError(
                f"Cart {pass_token.cart_id} is not open for payment (status={status_val})."
            )

        cart = (await db.execute(select(Cart).where(Cart.id == pass_token.cart_id))).scalar_one()

        # ── Check Existing Attempt Count for this Cart ────────────────────────
        stmt_orders = select(Order).where(Order.cart_id == pass_token.cart_id)
        existing_orders = (await db.execute(stmt_orders)).scalars().all()
        attempt_count = len(existing_orders) + 1

        if attempt_count > MAX_PAYMENT_RETRIES:
            logger.warning(
                "PaymentAgent BLOCK: Max payment retries exceeded",
                cart_id=pass_token.cart_id,
                attempt_count=attempt_count,
                max_retries=MAX_PAYMENT_RETRIES,
            )
            cart.status = CartStatus.FAILED
            await db.commit()

            await AuditService.log_event(
                db=db,
                actor="payment_agent",
                action="execute_payment",
                decision="BLOCK",
                session_id=pass_token.session_id,
                buyer_id=pass_token.buyer_id,
                reason_code="MAX_RETRIES_EXCEEDED",
                target_type="cart",
                target_id=str(pass_token.cart_id),
                evidence={
                    "attempt_count": attempt_count,
                    "max_retries": MAX_PAYMENT_RETRIES,
                },
                message=f"Payment attempts ({attempt_count}) exceeded maximum retry limit of {MAX_PAYMENT_RETRIES}.",
            )
            raise RuntimeError(
                f"Maximum payment retries ({MAX_PAYMENT_RETRIES}) reached for this cart. Order failed."
            )

        # ── Create Razorpay Order ──────────────────────────────────────────────
        try:
            rzp_response = self.razorpay_service.create_order(
                amount_paisa=pass_token.total_paisa,
                idempotency_key=pass_token.idempotency_key,
                currency="INR",
                notes={
                    "cart_id": pass_token.cart_id,
                    "session_id": pass_token.session_id or "",
                    "buyer_id": pass_token.buyer_id or "",
                    "is_ai_buyer": str(pass_token.is_ai_buyer),
                    "attempt": attempt_count,
                },
            )

            rzp_order_id = rzp_response.get("id")

            # ── Record Order in DB ────────────────────────────────────────────
            order = Order(
                cart_id=pass_token.cart_id,
                razorpay_order_id=rzp_order_id,
                idempotency_key=pass_token.idempotency_key,
                amount_paisa=pass_token.total_paisa,
                currency="INR",
                status=OrderStatus.CREATED,
                attempt_count=attempt_count,
                session_id=pass_token.session_id,
                buyer_id=pass_token.buyer_id,
            )

            db.add(order)
            await db.commit()
            await db.refresh(order)

            # ── Audit Log Event ───────────────────────────────────────────────
            await AuditService.log_event(
                db=db,
                actor="payment_agent",
                action="create_order",
                decision="PASS",
                session_id=pass_token.session_id,
                buyer_id=pass_token.buyer_id,
                target_type="order",
                target_id=str(order.id),
                evidence={
                    "order_id": order.id,
                    "razorpay_order_id": rzp_order_id,
                    "idempotency_key": pass_token.idempotency_key,
                    "amount_paisa": pass_token.total_paisa,
                    "attempt_count": attempt_count,
                },
                message=f"Razorpay order '{rzp_order_id}' created for ₹{pass_token.total_paisa / 100:.2f}.",
            )

            return {
                "order_id": order.id,
                "razorpay_order_id": rzp_order_id,
                "razorpay_key_id": settings.RAZORPAY_KEY_ID,
                "amount_paisa": pass_token.total_paisa,
                "amount_rupees": pass_token.total_paisa / 100,
                "currency": "INR",
                "attempt_count": attempt_count,
                "status": "created",
            }

        except Exception as e:
            logger.error("PaymentAgent failed order execution", error=str(e))
            await AuditService.log_event(
                db=db,
                actor="payment_agent",
                action="create_order",
                decision="ERROR",
                session_id=pass_token.session_id,
                buyer_id=pass_token.buyer_id,
                target_type="cart",
                target_id=str(pass_token.cart_id),
                evidence={"error": str(e), "attempt_count": attempt_count},
                message=f"Payment execution failed: {str(e)}",
            )
            raise
