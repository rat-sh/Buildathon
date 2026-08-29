"""Tests for stock decrement on payment capture webhook."""

import json
import hmac
import hashlib

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.cart import Cart, CartItem, CartStatus
from app.models.order import Order, OrderStatus
from app.models.product import Product


@pytest_asyncio.fixture
async def webhook_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        product = Product(
            name="Stock Shoe", sku="STK-1", category="running_shoes",
            price_paisa=100000, stock_quantity=3, is_active=True,
        )
        session.add(product)
        await session.commit()

        cart = Cart(session_id="sess_stock", status=CartStatus.LOCKED)
        session.add(cart)
        await session.commit()

        session.add(CartItem(
            cart_id=cart.id, product_id=product.id, quantity=2,
            charged_price_paisa=200000, explicitly_accepted=True,
        ))
        await session.commit()

        order = Order(
            cart_id=cart.id,
            razorpay_order_id="order_stock_test",
            idempotency_key="idemp_stock",
            amount_paisa=200000,
            status=OrderStatus.CREATED,
            attempt_count=1,
            session_id="sess_stock",
        )
        session.add(order)
        await session.commit()
        await session.refresh(product)

        yield session, product.id, order.razorpay_order_id

    await engine.dispose()


def _sign_webhook(body: bytes) -> str:
    return hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()


@pytest.mark.asyncio
async def test_webhook_capture_decrements_stock(webhook_db):
    db, product_id, rzp_order_id = webhook_db

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {"entity": {"order_id": rzp_order_id, "id": "pay_stock_1"}},
        },
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {"X-Razorpay-Signature": _sign_webhook(body)}

    with TestClient(app) as client:
        response = client.post("/webhooks/razorpay", content=body, headers=headers)

    app.dependency_overrides.clear()

    assert response.status_code == 200

    product = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one()
    assert product.stock_quantity == 1
