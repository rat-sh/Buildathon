"""Tests for cart ownership (IDOR prevention)."""

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.requests import Request

from app.core.database import Base
from app.main import app
from app.models.cart import Cart, CartItem, CartStatus
from app.models.product import Product
from app.schemas.chat import RemoveCartItemRequest
from app.api.chat_mutations import remove_cart_item


def _fake_request() -> Request:
    return Request({
        "type": "http", "method": "POST", "path": "/chat/remove-item",
        "headers": [], "client": ("127.0.0.1", 0), "app": app,
    })


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
async def test_cannot_remove_item_from_another_sessions_cart(test_db: AsyncSession):
    cart = Cart(session_id="owner_sess", status=CartStatus.OPEN)
    test_db.add(cart)
    await test_db.commit()

    product = Product(
        name="Test Shoe", sku="SEC-1", category="running_shoes",
        price_paisa=100000, stock_quantity=5, is_active=True,
    )
    test_db.add(product)
    await test_db.commit()

    item = CartItem(
        cart_id=cart.id, product_id=product.id, quantity=1,
        charged_price_paisa=100000, explicitly_accepted=True,
    )
    test_db.add(item)
    await test_db.commit()
    await test_db.refresh(item)

    with pytest.raises(HTTPException) as exc_info:
        await remove_cart_item(
            _fake_request(),
            RemoveCartItemRequest(
                cart_id=cart.id,
                item_id=item.id,
                session_id="attacker_sess",
            ),
            db=test_db,
        )

    assert exc_info.value.status_code == 403
