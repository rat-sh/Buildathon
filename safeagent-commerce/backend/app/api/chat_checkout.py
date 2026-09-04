"""
api/chat_checkout.py — POST /chat/checkout
==========================================
CRITICAL SAFETY: Validator gate is mandatory and cannot be bypassed.

Flow (non-negotiable):
  1. ValidatorAgent.validate_cart() — deterministic rule engine
  2. If BLOCKED  → return block response. Zero money moves.
  3. If PASS     → issue pass token → PaymentAgent creates Razorpay order.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.payment import PaymentAgent
from app.agents.validator import ValidatorAgent
from app.core.cart_access import assert_cart_owned_by_session
from app.core.database import get_db
from app.core.rate_limit import CHECKOUT_LIMIT, limiter
from app.core.security import generate_idempotency_key, generate_session_id
from app.models.cart import Cart
from app.schemas.chat import ChatMessageResponse, CheckoutRequest
from app.schemas.validator import ValidationRequest
from app.services.audit_service import AuditService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/checkout", response_model=ChatMessageResponse)
@limiter.limit(CHECKOUT_LIMIT)
async def checkout(request: Request, req: CheckoutRequest, db: AsyncSession = Depends(get_db)):
    """
    Checkout gate for human shopper.

    STEP 1 — Validator (non-bypassable):
        Checks price, stock, spend limits, unaccepted suggestions.
    STEP 2 — Payment (only on PASS token):
        PaymentAgent creates Razorpay order. Money never moves on BLOCK.
    """
    session_id = req.session_id or generate_session_id()
    idempotency_key = req.idempotency_key or generate_idempotency_key("pay_human")

    cart = (await db.execute(select(Cart).where(Cart.id == req.cart_id))).scalar_one_or_none()
    if not cart:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found.")
    assert_cart_owned_by_session(cart, session_id)

    val_result = await ValidatorAgent.validate_cart(
        db,
        ValidationRequest(
            cart_id=req.cart_id,
            idempotency_key=idempotency_key,
            session_id=session_id,
            is_ai_buyer=False,
        ),
    )

    await AuditService.log_validation_result(db, val_result, session_id=session_id)

    if not val_result.is_valid:
        logger.warning("Checkout BLOCKED", cart_id=req.cart_id, reason_code=val_result.reason_code)
        return ChatMessageResponse(
            reply=f"Checkout Blocked by Safety Validator: {val_result.message}",
            session_id=session_id,
            cart_id=req.cart_id,
            is_blocked=True,
            block_reason_code=val_result.reason_code,
        )

    checkout_data = await PaymentAgent().execute_payment(db, val_result.pass_token)

    return ChatMessageResponse(
        reply=(
            f"Validation Passed! Razorpay Order '{checkout_data['razorpay_order_id']}' created "
            f"for ₹{checkout_data['amount_rupees']:.2f}. Proceed to payment."
        ),
        session_id=session_id,
        cart_id=req.cart_id,
        checkout_data=checkout_data,
        is_blocked=False,
    )
