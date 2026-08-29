"""
api/chat_message.py — POST /chat/message
=========================================
Searches the real product catalog and returns AI reply + suggestions.
Does NOT modify cart state. Read + audit only.
"""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.shopping import ShoppingAgent
from app.agents.suggestion import SuggestionAgent
from app.core.database import get_db
from app.core.security import generate_session_id
from app.models.cart import Cart, CartItem
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse
from app.services.audit_service import AuditService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/message", response_model=ChatMessageResponse)
async def chat_message(
    req: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Process a human customer chat message.
    Searches real catalog, returns product matches and AI suggestions.
    No cart mutation happens here.
    """
    session_id = req.session_id or generate_session_id()
    shopping_agent = ShoppingAgent()
    suggestion_agent = SuggestionAgent()

    products = await shopping_agent.search_catalog(db, prompt=req.message)

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
                        "item_id": item.id,
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

    reply = (
        f"I found {len(products)} matching items in our catalog for you!"
        if products
        else "I couldn't find exact matches. Try: running shoes, socks, protein, or insoles."
    )

    return ChatMessageResponse(
        reply=reply,
        session_id=session_id,
        cart_id=cart_id,
        products=products,
        suggestions=suggestions,
        cart_summary=cart_summary,
    )
