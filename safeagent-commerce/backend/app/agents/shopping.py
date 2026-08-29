"""
agents/shopping.py — Shopping Agent
===================================
SAFETY CONTRACT:
  - Searches REAL catalog products in DB.
  - Never invents products, prices, or attributes.
  - Only active products (is_active=True) with stock_quantity > 0 are returned.
  - Uses LLM for NL intent parsing, but retrieves strictly from Product model.
"""

from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.services.llm_service import LLMService

logger = structlog.get_logger(__name__)


class ShoppingAgent:
    """
    Shopping Agent for catalog search and product recommendations.
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service or LLMService()

    async def search_catalog(
        self,
        db: AsyncSession,
        prompt: str,
        category: Optional[str] = None,
        max_price_rupees: Optional[float] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search catalog using natural language prompt or structured parameters.

        Args:
            db: Async DB session
            prompt: User natural language prompt (e.g. "running shoes under 4000")
            category: Optional category filter
            max_price_rupees: Optional max price in rupees
            limit: Maximum items to return

        Returns:
            List of matching real products from database
        """
        logger.info("ShoppingAgent searching catalog", prompt=prompt)

        # Parse NL intent if prompt provided
        intent = await self.llm_service.parse_shopping_intent(prompt)

        target_category = category or intent.get("category")
        max_price_paisa = int(max_price_rupees * 100) if max_price_rupees else intent.get("max_price_paisa")
        keywords = intent.get("query", prompt).split()

        # Query live DB: Product MUST be active and in stock
        stmt = select(Product).where(
            Product.is_active == True,
            Product.stock_quantity > 0,
        )

        if target_category:
            stmt = stmt.where(Product.category == target_category)

        if max_price_paisa:
            stmt = stmt.where(Product.price_paisa <= max_price_paisa)

        # Keyword filtering on name, description, brand
        if keywords:
            keyword_conditions = []
            for kw in keywords:
                if len(kw) >= 3:  # Filter out trivial short words
                    pattern = f"%{kw}%"
                    keyword_conditions.append(
                        or_(
                            Product.name.ilike(pattern),
                            Product.description.ilike(pattern),
                            Product.brand.ilike(pattern),
                            Product.category.ilike(pattern),
                        )
                    )
            if keyword_conditions:
                stmt = stmt.where(or_(*keyword_conditions))

        stmt = stmt.limit(limit)
        results = (await db.execute(stmt)).scalars().all()

        # If strict keyword match returned empty, fallback to category/price search
        if not results and (target_category or max_price_paisa):
            fallback_stmt = select(Product).where(
                Product.is_active == True,
                Product.stock_quantity > 0,
            )
            if target_category:
                fallback_stmt = fallback_stmt.where(Product.category == target_category)
            if max_price_paisa:
                fallback_stmt = fallback_stmt.where(Product.price_paisa <= max_price_paisa)

            fallback_stmt = fallback_stmt.limit(limit)
            results = (await db.execute(fallback_stmt)).scalars().all()

        output = []
        for p in results:
            output.append({
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
            })

        logger.info("ShoppingAgent search completed", results_count=len(output))
        return output
