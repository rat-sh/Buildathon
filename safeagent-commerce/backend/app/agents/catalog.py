"""
agents/catalog.py — Catalog Agent (MCP-style AI-to-AI Tools Surface)
=====================================================================
Exposes canonical tool-calling functions for external AI buyers:
  1. list_products(category, max_price_paisa, limit)
  2. get_product(product_id)
  3. create_purchase_intent(buyer_id, items, idempotency_key)
  4. get_spending_limits(is_ai_buyer=True)

Designed for machine-to-machine deterministic commerce transactions.
"""

from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import get_limits_for_buyer
from app.models.cart import Cart, CartItem, CartStatus
from app.models.product import Product

logger = structlog.get_logger(__name__)


class CatalogAgent:
    """
    Catalog Tool Agent exposing structured APIs for external AI buyers.
    """

    @staticmethod
    async def list_products(
        db: AsyncSession,
        category: Optional[str] = None,
        max_price_paisa: Optional[int] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """List active, in-stock products with optional filtering."""
        stmt = select(Product).where(
            Product.is_active == True,
            Product.stock_quantity > 0,
        )

        if category:
            stmt = stmt.where(Product.category == category)
        if max_price_paisa:
            stmt = stmt.where(Product.price_paisa <= max_price_paisa)

        stmt = stmt.limit(limit)
        results = (await db.execute(stmt)).scalars().all()

        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "category": p.category,
                "brand": p.brand,
                "sku": p.sku,
                "price_paisa": p.price_paisa,
                "price_rupees": p.price_paisa / 100,
                "currency": p.currency,
                "stock_quantity": p.stock_quantity,
                "attributes": p.attributes_json,
            }
            for p in results
        ]

    @staticmethod
    async def get_product(db: AsyncSession, product_id: int) -> Optional[Dict[str, Any]]:
        """Get canonical product schema by ID."""
        stmt = select(Product).where(Product.id == product_id)
        p = (await db.execute(stmt)).scalar_one_or_none()

        if not p:
            return None

        return {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "category": p.category,
            "brand": p.brand,
            "sku": p.sku,
            "price_paisa": p.price_paisa,
            "price_rupees": p.price_paisa / 100,
            "currency": p.currency,
            "stock_quantity": p.stock_quantity,
            "is_active": p.is_active,
            "attributes": p.attributes_json,
        }

    @staticmethod
    async def get_spending_limits(is_ai_buyer: bool = True) -> Dict[str, Any]:
        """Return spending limits configured for AI or human buyers."""
        limits = get_limits_for_buyer(is_ai_buyer)
        return {
            "buyer_type": limits["buyer_type"],
            "per_tx_limit_paisa": limits["per_tx_limit_paisa"],
            "per_tx_limit_rupees": limits["per_tx_limit_paisa"] / 100,
            "daily_ceiling_paisa": limits["daily_ceiling_paisa"],
            "daily_ceiling_rupees": limits["daily_ceiling_paisa"] / 100,
            "currency": "INR",
        }

    @staticmethod
    async def create_purchase_intent(
        db: AsyncSession,
        buyer_id: str,
        items: List[Dict[str, Any]],  # [{"product_id": 1, "quantity": 1}]
        idempotency_key: str,
    ) -> Dict[str, Any]:
        """
        Create a purchase intent (cart) for an external AI buyer.

        Args:
            db: Async DB session
            buyer_id: Unique string token identifying external AI buyer
            items: List of line item dicts containing product_id and quantity
            idempotency_key: Key for payment idempotency

        Returns:
            Purchase intent summary dictionary
        """
        cart = Cart(buyer_id=buyer_id, status=CartStatus.OPEN)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)

        total_paisa = 0
        cart_items_summary = []

        for item_def in items:
            pid = item_def.get("product_id")
            qty = item_def.get("quantity", 1)

            stmt = select(Product).where(Product.id == pid)
            product = (await db.execute(stmt)).scalar_one_or_none()

            if not product:
                raise ValueError(f"Product ID {pid} does not exist.")

            charged_price = product.price_paisa
            cart_item = CartItem(
                cart_id=cart.id,
                product_id=product.id,
                quantity=qty,
                charged_price_paisa=charged_price,
                is_suggestion=False,
                explicitly_accepted=True,  # Direct purchase intent line item
            )
            db.add(cart_item)
            total_paisa += charged_price * qty
            cart_items_summary.append({
                "product_id": product.id,
                "name": product.name,
                "quantity": qty,
                "unit_price_paisa": charged_price,
                "line_total_paisa": charged_price * qty,
            })

        await db.commit()

        return {
            "cart_id": cart.id,
            "buyer_id": buyer_id,
            "idempotency_key": idempotency_key,
            "total_paisa": total_paisa,
            "total_rupees": total_paisa / 100,
            "items": cart_items_summary,
            "status": "intent_created",
        }
