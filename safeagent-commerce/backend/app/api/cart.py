"""
api/cart.py — Cart Read Endpoint
=================================
Single responsibility: read cart state from DB for the frontend.
The frontend calls GET /chat/cart/{cart_id} after every mutation
so the cart sidebar always reflects real database state.

Safety contract:
  - Read-only. No money or state changes happen here.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.cart import Cart, CartItem

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["cart"])


@router.get("/cart/{cart_id}")
async def get_cart(cart_id: int, db: AsyncSession = Depends(get_db)):
    """
    Return full cart contents from the database.

    Called by the frontend after every add/accept/checkout mutation
    to replace local JS state with real DB state.
    Never returns mock data.
    """
    stmt = (
        select(Cart)
        .options(selectinload(Cart.items).selectinload(CartItem.product))
        .where(Cart.id == cart_id)
    )
    cart = (await db.execute(stmt)).scalar_one_or_none()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found.")

    items = [
        {
            "item_id": item.id,
            "product_id": item.product_id,
            "name": item.product.name if item.product else "Product",
            "quantity": item.quantity,
            "price_rupees": item.charged_price_paisa / 100,
            "is_suggestion": item.is_suggestion,
            "explicitly_accepted": item.explicitly_accepted,
        }
        for item in cart.items
    ]

    return {
        "cart_id": cart.id,
        "status": cart.status.value,
        "total_rupees": sum(i["price_rupees"] * i["quantity"] for i in items),
        "items_count": len(items),
        "items": items,
    }
