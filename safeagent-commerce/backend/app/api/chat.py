"""
api/chat.py — Human Chat Endpoints (HTMX & JSON compatible)
===========================================================
Safety Contracts:
  - ShoppingAgent searches real catalog.
  - SuggestionAgent proposes add-ons with explicitly_accepted=False.
  - /chat/accept-addon flips explicitly_accepted=True ONLY via explicit user action.
  - /chat/checkout invokes ValidatorAgent FIRST.
  - Money moves ONLY when Validator returns PASS token to PaymentAgent.
"""

from typing import Any, Dict, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.payment import PaymentAgent
from app.agents.shopping import ShoppingAgent
from app.agents.suggestion import SuggestionAgent
from app.agents.validator import ValidatorAgent
from app.core.database import get_db
from app.core.security import generate_idempotency_key, generate_session_id
from app.models.cart import Cart, CartItem, CartStatus
from app.models.product import Product
from app.schemas.chat import (
    AcceptAddonRequest,
    AddToCartRequest,
    ChatMessageRequest,
    ChatMessageResponse,
    CheckoutRequest,
)
from app.schemas.validator import ValidationRequest
from app.services.audit_service import AuditService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/message", response_model=ChatMessageResponse)
async def chat_message(
    req: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Process incoming human customer chat message.
    Handles product search, intent detection, and recommendations.
    """
    session_id = req.session_id or generate_session_id()
    text = req.message.strip().lower()

    shopping_agent = ShoppingAgent()
    suggestion_agent = SuggestionAgent()

    # Search real catalog
    products = await shopping_agent.search_catalog(db, prompt=req.message)

    # Get active cart or create one if user selected products
    cart_id = req.cart_id
    cart_summary = None
    suggestions = []

    if cart_id:
        stmt = (
            select(Cart)
            .options(selectinload(Cart.items).selectinload(CartItem.product))
            .where(Cart.id == cart_id)
        )
        cart = (await db.execute(stmt)).scalar_one_or_none()
        if cart:
            cart_summary = {
                "cart_id": cart.id,
                "status": cart.status.value,
                "total_rupees": cart.total_paisa / 100,
                "items_count": len(cart.items),
                "items": [
                    {
                        "id": item.id,
                        "product_id": item.product_id,
                        "name": item.product.name if item.product else "Product",
                        "quantity": item.quantity,
                        "price_rupees": item.charged_price_paisa / 100,
                        "is_suggestion": item.is_suggestion,
                        "explicitly_accepted": item.explicitly_accepted,
                    }
                    for item in cart.items
                ],
            }
            suggestions = await suggestion_agent.get_suggestions_for_cart(db, cart_id)

    # Audit log user chat event
    await AuditService.log_event(
        db=db,
        actor="human",
        action="chat_message",
        decision="INFO",
        session_id=session_id,
        target_type="cart",
        target_id=str(cart_id) if cart_id else None,
        evidence={"message": req.message, "products_found": len(products)},
        message=f"Customer chat: '{req.message}'",
    )

    if not products:
        reply = "I couldn't find exact matches in our catalog for that request. Try searching for running shoes, socks, protein, or insoles."
    else:
        reply = f"I found {len(products)} matching items in our catalog for you!"

    return ChatMessageResponse(
        reply=reply,
        session_id=session_id,
        cart_id=cart_id,
        products=products,
        suggestions=suggestions,
        cart_summary=cart_summary,
    )


@router.post("/add-to-cart")
async def add_to_cart(
    req: AddToCartRequest,
    db: AsyncSession = Depends(get_db),
):
    """Add a regular product to the customer's cart."""
    session_id = req.session_id or generate_session_id()

    stmt_p = select(Product).where(Product.id == req.product_id)
    product = (await db.execute(stmt_p)).scalar_one_or_none()

    if not product or not product.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product is unavailable or inactive.",
        )

    # Get or create cart
    cart = None
    if req.cart_id:
        stmt_c = select(Cart).where(Cart.id == req.cart_id)
        cart = (await db.execute(stmt_c)).scalar_one_or_none()

    if not cart or cart.status != CartStatus.OPEN:
        cart = Cart(session_id=session_id, status=CartStatus.OPEN)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)

    item = CartItem(
        cart_id=cart.id,
        product_id=product.id,
        quantity=req.quantity,
        charged_price_paisa=product.price_paisa,
        is_suggestion=False,
        explicitly_accepted=True,  # User explicitly selected this main item
    )
    db.add(item)
    await db.commit()

    # Log Audit Event
    await AuditService.log_event(
        db=db,
        actor="human",
        action="add_to_cart",
        decision="PASS",
        session_id=session_id,
        target_type="cart",
        target_id=str(cart.id),
        evidence={"product_id": product.id, "price_paisa": product.price_paisa},
        message=f"Added '{product.name}' to cart.",
    )

    return {
        "status": "success",
        "cart_id": cart.id,
        "session_id": session_id,
        "added_item": {"product_id": product.id, "name": product.name, "price_rupees": product.price_paisa / 100},
    }


@router.post("/add-suggestion")
async def add_suggestion_to_cart(
    req: AddToCartRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Add a suggested item to cart with explicitly_accepted=False.
    Must be explicitly accepted by user via /chat/accept-addon before checkout!
    """
    session_id = req.session_id or generate_session_id()

    stmt_p = select(Product).where(Product.id == req.product_id)
    product = (await db.execute(stmt_p)).scalar_one_or_none()

    if not product or not product.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product unavailable.",
        )

    stmt_c = select(Cart).where(Cart.id == req.cart_id)
    cart = (await db.execute(stmt_c)).scalar_one_or_none()

    if not cart or cart.status != CartStatus.OPEN:
        raise HTTPException(status_code=400, detail="Invalid active cart.")

    item = CartItem(
        cart_id=cart.id,
        product_id=product.id,
        quantity=1,
        charged_price_paisa=product.price_paisa,
        is_suggestion=True,
        explicitly_accepted=False,  # SAFETY: NOT ACCEPTED YET
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    return {
        "status": "suggestion_added_pending_accept",
        "cart_id": cart.id,
        "item_id": item.id,
        "product_id": product.id,
        "explicitly_accepted": False,
    }


@router.post("/accept-addon")
async def accept_addon(
    req: AcceptAddonRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Explicit user action to accept a suggested add-on item in the cart.
    Flips explicitly_accepted = True.
    """
    stmt = select(CartItem).where(CartItem.id == req.item_id, CartItem.cart_id == req.cart_id)
    item = (await db.execute(stmt)).scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found.")

    item.explicitly_accepted = True
    await db.commit()

    await AuditService.log_event(
        db=db,
        actor="human",
        action="accept_suggestion",
        decision="PASS",
        session_id=req.session_id,
        target_type="cart_item",
        target_id=str(item.id),
        evidence={"product_id": item.product_id, "explicitly_accepted": True},
        message=f"Customer explicitly accepted add-on item #{item.id}.",
    )

    return {"status": "success", "item_id": item.id, "explicitly_accepted": True}


@router.post("/checkout", response_model=ChatMessageResponse)
async def checkout(
    req: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Execute checkout gate for human shopper.

    CRITICAL SAFETY FLOW:
      1. Calls ValidatorAgent.validate_cart()
      2. If Validator BLOCKS -> Return block response with clear reason code. ZERO money moves.
      3. If Validator PASSES -> Pass token issued -> PaymentAgent executes Razorpay order creation.
    """
    session_id = req.session_id or generate_session_id()
    idempotency_key = req.idempotency_key or generate_idempotency_key("pay_human")

    val_req = ValidationRequest(
        cart_id=req.cart_id,
        idempotency_key=idempotency_key,
        session_id=session_id,
        is_ai_buyer=False,
    )

    # ── STEP 1: VALIDATOR GATE (NON-BYPASSABLE) ──────────────────────────────
    val_result = await ValidatorAgent.validate_cart(db, val_req)

    # Log Validator audit event
    await AuditService.log_validation_result(db, val_result, session_id=session_id)

    if not val_result.is_valid:
        logger.warning(
            "Checkout BLOCKED by Validator",
            cart_id=req.cart_id,
            reason_code=val_result.reason_code,
        )
        return ChatMessageResponse(
            reply=f"🚫 Checkout Blocked by Safety Validator: {val_result.message}",
            session_id=session_id,
            cart_id=req.cart_id,
            is_blocked=True,
            block_reason_code=val_result.reason_code,
        )

    # ── STEP 2: PAYMENT EXECUTION (Validator PASS Token Required) ────────────
    payment_agent = PaymentAgent()
    checkout_data = await payment_agent.execute_payment(db, val_result.pass_token)

    reply = (
        f"✅ Validation Passed! Razorpay Order '{checkout_data['razorpay_order_id']}' created for "
        f"₹{checkout_data['amount_rupees']:.2f}. Proceed to payment."
    )

    return ChatMessageResponse(
        reply=reply,
        session_id=session_id,
        cart_id=req.cart_id,
        checkout_data=checkout_data,
        is_blocked=False,
    )
