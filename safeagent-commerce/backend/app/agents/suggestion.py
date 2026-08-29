"""
agents/suggestion.py — Suggestion Agent (Upsell & Cross-Sell)
==============================================================
SAFETY CONTRACT (NON-NEGOTIABLE):
  1. Suggests 1–2 complementary add-on items based on affinity rules & remaining budget.
  2. NEVER auto-adds items with explicitly_accepted = True.
  3. All suggested items MUST have is_suggestion = True, explicitly_accepted = False.
  4. Only an explicit user/AI policy action can accept a suggestion.
  5. The Validator Agent will BLOCK any cart containing unaccepted suggestions.
"""

from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.limits import MAX_SUGGESTIONS_PER_SESSION, get_limits_for_buyer
from app.models.cart import Cart, CartItem
from app.models.product import Product

logger = structlog.get_logger(__name__)


class SuggestionAgent:
    """
    Suggestion Agent for non-intrusive, budget-aware upsell recommendations.
    """

    @staticmethod
    async def get_suggestions_for_cart(
        db: AsyncSession,
        cart_id: int,
        is_ai_buyer: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Generate up to 2 relevant upsell suggestions for a cart.

        Args:
            db: Async DB session
            cart_id: Current cart ID
            is_ai_buyer: Buyer type for spending limit evaluation

        Returns:
            List of suggested items with rationale and price details
        """
        stmt = (
            select(Cart)
            .options(selectinload(Cart.items).selectinload(CartItem.product))
            .where(Cart.id == cart_id)
        )
        cart = (await db.execute(stmt)).scalar_one_or_none()

        if not cart or not cart.items:
            return []

        cart_total_paisa = cart.total_paisa
        limits = get_limits_for_buyer(is_ai_buyer)
        remaining_budget_paisa = limits["per_tx_limit_paisa"] - cart_total_paisa

        if remaining_budget_paisa <= 0:
            logger.info("No remaining budget for suggestions", remaining_budget=remaining_budget_paisa)
            return []

        existing_product_ids = {item.product_id for item in cart.items}

        # Collect affinity product IDs from items in cart
        affinity_ids: List[int] = []
        for item in cart.items:
            if item.product and item.product.affinity_product_ids:
                try:
                    ids = [int(i.strip()) for i in item.product.affinity_product_ids.split(",") if i.strip()]
                    affinity_ids.extend(ids)
                except ValueError:
                    pass

        # Query candidates matching affinity IDs, within remaining budget, active, in stock
        candidates: List[Product] = []

        if affinity_ids:
            # Filter out items already in cart
            valid_affinity_ids = [pid for pid in affinity_ids if pid not in existing_product_ids]
            if valid_affinity_ids:
                stmt_aff = select(Product).where(
                    Product.id.in_(valid_affinity_ids),
                    Product.is_active == True,
                    Product.stock_quantity > 0,
                    Product.price_paisa <= remaining_budget_paisa,
                ).limit(MAX_SUGGESTIONS_PER_SESSION)
                candidates = list((await db.execute(stmt_aff)).scalars().all())

        # If affinity query yielded fewer than 2 candidates, fallback to accessories category
        if len(candidates) < MAX_SUGGESTIONS_PER_SESSION:
            needed = MAX_SUGGESTIONS_PER_SESSION - len(candidates)
            excluded_ids = existing_product_ids.union({c.id for c in candidates})

            stmt_cat = select(Product).where(
                Product.category == "accessories",
                Product.id.not_in(excluded_ids),
                Product.is_active == True,
                Product.stock_quantity > 0,
                Product.price_paisa <= remaining_budget_paisa,
            ).limit(needed)
            fallback = list((await db.execute(stmt_cat)).scalars().all())
            candidates.extend(fallback)

        suggestions = []
        for product in candidates[:MAX_SUGGESTIONS_PER_SESSION]:
            rationale = f"Pairs well with items in your cart (₹{product.price_paisa / 100:.2f})"
            suggestions.append({
                "product_id": product.id,
                "name": product.name,
                "category": product.category,
                "price_paisa": product.price_paisa,
                "price_rupees": product.price_paisa / 100,
                "rationale": rationale,
                "is_suggestion": True,
                # SAFETY: ALWAYS False by default! Never auto-accepted!
                "explicitly_accepted": False,
            })

        logger.info("SuggestionAgent generated recommendations", count=len(suggestions))
        return suggestions
