"""Tests for budget parsing and cart item removal."""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from starlette.requests import Request

from app.core.database import Base
from app.main import app
from app.models.cart import Cart, CartItem, CartStatus
from app.models.product import Product
from app.services.budget_context import parse_budget_from_message, resolve_budget_rupees


def _fake_request() -> Request:
    return Request({
        "type": "http", "method": "POST", "path": "/chat/remove-item",
        "headers": [], "client": ("127.0.0.1", 0), "app": app,
    })


def test_parse_budget_from_message():
    assert parse_budget_from_message("my budget is 3000") == 3000.0
    assert parse_budget_from_message("running shoes under 4000") == 4000.0
    assert parse_budget_from_message("just hello") is None


def test_resolve_budget_prefers_message():
    assert resolve_budget_rupees(2000.0, "budget is 5000") == 5000.0
    assert resolve_budget_rupees(2000.0, "hello") == 2000.0


@pytest_asyncio.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_remove_item_from_open_cart(test_db: AsyncSession):
    from app.api.chat_mutations import remove_cart_item
    from app.schemas.chat import RemoveCartItemRequest

    cart = Cart(session_id="sess_rm", status=CartStatus.OPEN)
    test_db.add(cart)
    await test_db.commit()

    product = Product(
        name="Test Shoe", sku="T-1", category="running_shoes",
        price_paisa=100000, stock_quantity=5, is_active=True,
    )
    test_db.add(product)
    await test_db.commit()

    item = CartItem(cart_id=cart.id, product_id=product.id, quantity=1,
                    charged_price_paisa=100000, explicitly_accepted=True)
    test_db.add(item)
    await test_db.commit()
    await test_db.refresh(item)

    result = await remove_cart_item(
        _fake_request(),
        RemoveCartItemRequest(cart_id=cart.id, item_id=item.id, session_id="sess_rm"),
        db=test_db,
    )
    assert result["status"] == "success"

    remaining = (await test_db.execute(
        select(CartItem).where(CartItem.cart_id == cart.id)
    )).scalars().all()
    assert len(remaining) == 0
