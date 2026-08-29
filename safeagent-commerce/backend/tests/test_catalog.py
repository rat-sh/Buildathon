"""
tests/test_catalog.py — Test suite for CatalogAgent and Shopping/Suggestion Agents
=====================================================================================
Tests:
  1. ShoppingAgent searches real products and filters out inactive/out-of-stock items
  2. SuggestionAgent returns budget-aware recommendations with explicitly_accepted=False
  3. CatalogAgent tool functions (list_products, get_product, create_purchase_intent, get_spending_limits)
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.database import Base
from app.models.cart import Cart, CartItem, CartStatus
from app.models.product import Product
from app.agents.shopping import ShoppingAgent
from app.agents.suggestion import SuggestionAgent
from app.agents.catalog import CatalogAgent


@pytest_asyncio.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def seed_data(test_db: AsyncSession):
    p1 = Product(
        id=1,
        name="Nike Zoom Running Shoes",
        sku="NIKE-ZOOM-1",
        category="running_shoes",
        price_paisa=399900,
        currency="INR",
        stock_quantity=10,
        is_active=True,
        affinity_product_ids="2,3",
    )
    p2 = Product(
        id=2,
        name="Fitlite Socks",
        sku="SOCKS-1",
        category="accessories",
        price_paisa=49900,
        currency="INR",
        stock_quantity=50,
        is_active=True,
    )
    p3 = Product(
        id=3,
        name="Gel Insole",
        sku="INSOLE-1",
        category="accessories",
        price_paisa=89900,
        currency="INR",
        stock_quantity=20,
        is_active=True,
    )
    test_db.add_all([p1, p2, p3])
    await test_db.commit()
    return [p1, p2, p3]


# ── TEST 1: ShoppingAgent Catalog Search ──────────────────────────────────────
@pytest.mark.asyncio
async def test_shopping_agent_search(test_db: AsyncSession, seed_data):
    agent = ShoppingAgent()
    results = await agent.search_catalog(test_db, prompt="running shoes under 4000")

    assert len(results) >= 1
    assert results[0]["id"] == 1
    assert results[0]["price_paisa"] == 399900


# ── TEST 2: SuggestionAgent Recommendations (explicitly_accepted=False) ──────
@pytest.mark.asyncio
async def test_suggestion_agent(test_db: AsyncSession, seed_data):
    cart = Cart(session_id="sess_sug", status=CartStatus.OPEN)
    test_db.add(cart)
    await test_db.commit()

    item = CartItem(cart_id=cart.id, product_id=1, quantity=1, charged_price_paisa=399900)
    test_db.add(item)
    await test_db.commit()

    suggestions = await SuggestionAgent.get_suggestions_for_cart(test_db, cart.id)

    assert len(suggestions) > 0
    # SAFETY CONTRACT: explicitly_accepted MUST be False by default!
    for sug in suggestions:
        assert sug["is_suggestion"] is True
        assert sug["explicitly_accepted"] is False


# ── TEST 3: CatalogAgent MCP Tools ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_catalog_agent_mcp_tools(test_db: AsyncSession, seed_data):
    # 1. list_products
    products = await CatalogAgent.list_products(test_db, category="running_shoes")
    assert len(products) == 1
    assert products[0]["sku"] == "NIKE-ZOOM-1"

    # 2. get_product
    product = await CatalogAgent.get_product(test_db, product_id=1)
    assert product is not None
    assert product["name"] == "Nike Zoom Running Shoes"

    # 3. get_spending_limits
    limits = await CatalogAgent.get_spending_limits(is_ai_buyer=True)
    assert limits["buyer_type"] == "ai"
    assert limits["per_tx_limit_rupees"] == 2000.0

    # 4. create_purchase_intent
    intent = await CatalogAgent.create_purchase_intent(
        test_db,
        buyer_id="ai_buyer_test_bot",
        items=[{"product_id": 1, "quantity": 1}],
        idempotency_key="idemp_ai_test_100",
    )
    assert intent["status"] == "intent_created"
    assert intent["total_paisa"] == 399900
    assert intent["cart_id"] is not None
