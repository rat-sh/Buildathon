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
from app.services.budget_context import resolve_budget_rupees
from app.services.llm_service import LLMService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["chat"])

_GREETINGS = {"hi", "hello", "hey", "hi there", "greetings", "good morning", "good evening"}


@router.post("/message", response_model=ChatMessageResponse)
async def chat_message(
    req: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """Process a human customer chat message. No cart mutation happens here."""
    session_id = req.session_id or generate_session_id()
    shopping_agent = ShoppingAgent()
    suggestion_agent = SuggestionAgent()
    llm_service = LLMService()

    msg_lower = req.message.strip().lower()
    is_greeting = msg_lower in _GREETINGS

    budget_rupees = resolve_budget_rupees(req.budget_rupees, req.message)

    search_result = await shopping_agent.search_catalog(
        db, prompt=req.message, max_price_rupees=budget_rupees,
    )
    products = search_result.get("products", [])
    match_tier = search_result.get("match_tier", "exact_match")
    is_above_budget = search_result.get("is_above_budget", False)

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
            user_budget_paisa = int(budget_rupees * 100) if budget_rupees else None
            suggestions = await suggestion_agent.get_suggestions_for_cart(
                db, cart_id, user_budget_paisa=user_budget_paisa,
            )

    await AuditService.log_event(
        db=db,
        actor="human",
        action="chat_message",
        decision="INFO",
        session_id=session_id,
        target_type="cart",
        target_id=str(cart_id) if cart_id else None,
        evidence={
            "message": req.message,
            "products_found": len(products),
            "budget_rupees": budget_rupees,
            "match_tier": match_tier,
            "is_above_budget": is_above_budget,
        },
        message=f"Customer chat: '{req.message}'",
    )

    reply = await llm_service.generate_conversational_reply(
        req.message,
        products,
        budget_rupees=budget_rupees,
        is_greeting=is_greeting,
        match_tier=match_tier,
        is_above_budget=is_above_budget,
    )

    if not budget_rupees and not is_greeting and not products:
        reply += " If you share a rough budget, I can narrow results to what fits."

    displayed_products = [] if is_greeting else products

    return ChatMessageResponse(
        reply=reply,
        session_id=session_id,
        cart_id=cart_id,
        budget_rupees=budget_rupees,
        is_above_budget=is_above_budget if not is_greeting else False,
        match_tier=match_tier if not is_greeting else None,
        products=displayed_products,
        suggestions=suggestions if not is_greeting else [],
        cart_summary=cart_summary,
    )
