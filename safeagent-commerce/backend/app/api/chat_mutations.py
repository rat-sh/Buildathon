"""
api/chat_mutations.py — Cart Write Endpoints
=============================================
POST /chat/add-to-cart    — adds explicitly accepted item
POST /chat/add-suggestion — adds item with explicitly_accepted=False (safety default)
POST /chat/accept-addon   — flips explicitly_accepted=True on user action

Safety contract:
  - Suggestions are NEVER auto-accepted.
  - accept-addon requires explicit user button press (audited).
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import generate_session_id
from app.models.cart import Cart, CartItem, CartStatus
from app.models.product import Product
from app.schemas.chat import AcceptAddonRequest, AddToCartRequest, RemoveCartItemRequest
from app.services.audit_service import AuditService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/add-to-cart")
async def add_to_cart(req: AddToCartRequest, db: AsyncSession = Depends(get_db)):
    """Add a regular product (explicitly accepted) to the cart."""
    session_id = req.session_id or generate_session_id()

    product = (await db.execute(select(Product).where(Product.id == req.product_id))).scalar_one_or_none()
    if not product or not product.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product is unavailable or inactive.")

    cart = None
    if req.cart_id:
        cart = (await db.execute(select(Cart).where(Cart.id == req.cart_id))).scalar_one_or_none()

    if not cart or cart.status != CartStatus.OPEN:
        cart = Cart(session_id=session_id, status=CartStatus.OPEN)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)

    db.add(CartItem(
        cart_id=cart.id,
        product_id=product.id,
        quantity=req.quantity,
        charged_price_paisa=product.price_paisa,
        is_suggestion=False,
        explicitly_accepted=True,
    ))
    await db.commit()

    await AuditService.log_event(
        db=db, actor="human", action="add_to_cart", decision="PASS",
        session_id=session_id, target_type="cart", target_id=str(cart.id),
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
async def add_suggestion_to_cart(req: AddToCartRequest, db: AsyncSession = Depends(get_db)):
    """
    Add a suggested item with explicitly_accepted=False.
    SAFETY: Must be accepted via /accept-addon before checkout.
    """
    session_id = req.session_id or generate_session_id()

    product = (await db.execute(select(Product).where(Product.id == req.product_id))).scalar_one_or_none()
    if not product or not product.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product unavailable.")

    cart = (await db.execute(select(Cart).where(Cart.id == req.cart_id))).scalar_one_or_none()
    if not cart or cart.status != CartStatus.OPEN:
        raise HTTPException(status_code=400, detail="Invalid active cart.")

    item = CartItem(
        cart_id=cart.id, product_id=product.id, quantity=1,
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
async def accept_addon(req: AcceptAddonRequest, db: AsyncSession = Depends(get_db)):
    """
    Explicit user action to accept a suggested add-on.
    Flips explicitly_accepted = True and creates an audit trail.
    """
    item = (await db.execute(
        select(CartItem).where(CartItem.id == req.item_id, CartItem.cart_id == req.cart_id)
    )).scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found.")

    item.explicitly_accepted = True
    await db.commit()

    await AuditService.log_event(
        db=db, actor="human", action="accept_suggestion", decision="PASS",
        session_id=req.session_id, target_type="cart_item", target_id=str(item.id),
        evidence={"product_id": item.product_id, "explicitly_accepted": True},
        message=f"Customer explicitly accepted add-on item #{item.id}.",
    )

    return {"status": "success", "item_id": item.id, "explicitly_accepted": True}


@router.post("/remove-item")
async def remove_cart_item(req: RemoveCartItemRequest, db: AsyncSession = Depends(get_db)):
    """Remove a cart line item. Only allowed while cart is OPEN (not paid/locked)."""
    cart = (await db.execute(select(Cart).where(Cart.id == req.cart_id))).scalar_one_or_none()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found.")
    if cart.status != CartStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove items — cart is no longer open for edits.",
        )

    item = (await db.execute(
        select(CartItem).where(CartItem.id == req.item_id, CartItem.cart_id == req.cart_id)
    )).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found.")

    product_name = "item"
    if item.product_id:
        product = (await db.execute(select(Product).where(Product.id == item.product_id))).scalar_one_or_none()
        if product:
            product_name = product.name

    await db.execute(
        delete(CartItem).where(CartItem.id == req.item_id, CartItem.cart_id == req.cart_id)
    )
    await db.commit()

    await AuditService.log_event(
        db=db, actor="human", action="remove_from_cart", decision="INFO",
        session_id=req.session_id, target_type="cart_item", target_id=str(req.item_id),
        evidence={"cart_id": req.cart_id, "product_id": item.product_id},
        message=f"Removed '{product_name}' from cart #{req.cart_id}.",
    )

    return {"status": "success", "cart_id": req.cart_id, "removed_item_id": req.item_id}
