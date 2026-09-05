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
from sqlalchemy import select, and_, or_
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
    ) -> Dict[str, Any]:
        """
        Search catalog using natural language prompt or structured parameters.

        Args:
            db: Async DB session
            prompt: User natural language prompt (e.g. "running shoes under 4000")
            category: Optional category filter
            max_price_rupees: Optional max price in rupees
            limit: Maximum items to return

        Returns:
            Dict containing matching real products and match tier metadata:
            {
                "products": [...],
                "match_tier": "exact_match" | "relaxed_keywords" | "above_budget" | "category_only" | "no_match",
                "is_above_budget": bool,
                "budget_rupees": float | None,
                "count": int
            }
        """
        logger.info("ShoppingAgent searching catalog", prompt=prompt)

        # Parse NL intent if prompt provided
        intent = await self.llm_service.parse_shopping_intent(prompt)

        target_category = category or intent.get("category")
        max_price_paisa = int(max_price_rupees * 100) if max_price_rupees else intent.get("max_price_paisa")
        effective_max_price_rupees = (max_price_paisa / 100) if max_price_paisa else max_price_rupees
        keywords = intent.get("query", prompt).split()

        match_tier = "no_match"
        is_above_budget = False

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
        # Use AND across keywords so "running shoes" doesn't match socks.
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
                # AND all keyword conditions — every keyword must match at least one field
                stmt = stmt.where(and_(*keyword_conditions))

        stmt = stmt.limit(limit)
        results = (await db.execute(stmt)).scalars().all()
        if results:
            match_tier = "exact_match"

        # Fallback 1: relax keyword AND → OR (in case AND is too strict for a single word)
        if not results and keywords:
            relaxed_stmt = select(Product).where(
                Product.is_active == True,
                Product.stock_quantity > 0,
            )
            if target_category:
                relaxed_stmt = relaxed_stmt.where(Product.category == target_category)
            if max_price_paisa:
                relaxed_stmt = relaxed_stmt.where(Product.price_paisa <= max_price_paisa)
            kw_or_conditions = []
            for kw in keywords:
                if len(kw) >= 3:
                    pattern = f"%{kw}%"
                    kw_or_conditions.append(
                        or_(
                            Product.name.ilike(pattern),
                            Product.description.ilike(pattern),
                            Product.brand.ilike(pattern),
                            Product.category.ilike(pattern),
                        )
                    )
            if kw_or_conditions:
                relaxed_stmt = relaxed_stmt.where(or_(*kw_or_conditions))
            relaxed_stmt = relaxed_stmt.limit(limit)
            results = (await db.execute(relaxed_stmt)).scalars().all()
            if results:
                match_tier = "relaxed_keywords"

        # Fallback 2: If still empty and a price filter is active, drop it so we can
        # at least show products that exist. Flag as above_budget so downstream components don't lie.
        if not results and max_price_paisa:
            noprice_stmt = select(Product).where(
                Product.is_active == True,
                Product.stock_quantity > 0,
            )
            if target_category:
                noprice_stmt = noprice_stmt.where(Product.category == target_category)
            if keywords:
                kw_or_conditions = []
                for kw in keywords:
                    if len(kw) >= 3:
                        pattern = f"%{kw}%"
                        kw_or_conditions.append(
                            or_(
                                Product.name.ilike(pattern),
                                Product.description.ilike(pattern),
                                Product.brand.ilike(pattern),
                                Product.category.ilike(pattern),
                            )
                        )
                if kw_or_conditions:
                    noprice_stmt = noprice_stmt.where(or_(*kw_or_conditions))
            noprice_stmt = noprice_stmt.limit(limit)
            results = (await db.execute(noprice_stmt)).scalars().all()
            if results:
                match_tier = "above_budget"
                is_above_budget = True
                logger.info(
                    "ShoppingAgent: price fallback used — items found above budget",
                    max_price_paisa=max_price_paisa,
                    results_count=len(results),
                )

        # Fallback 3: category/price only (no keywords)
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
            if results:
                match_tier = "category_only"
                if max_price_paisa and any(p.price_paisa > max_price_paisa for p in results):
                    is_above_budget = True

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

        logger.info(
            "ShoppingAgent search completed",
            results_count=len(output),
            match_tier=match_tier,
            is_above_budget=is_above_budget,
        )
        return {
            "products": output,
            "match_tier": match_tier,
            "is_above_budget": is_above_budget,
            "budget_rupees": effective_max_price_rupees,
            "count": len(output),
        }
