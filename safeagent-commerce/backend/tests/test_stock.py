"""Tests for idempotent stock decrement on payment capture (webhook + verify)."""

import asyncio
import hashlib
import hmac
import json

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.cart import Cart, CartItem, CartStatus
from app.models.order import Order, OrderStatus
from app.models.product import Product


@pytest_asyncio.fixture
async def capture_db():
    """Cart + order ready for capture; product stock starts at 3, cart qty 2."""
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


def _sign_payment(order_id: str, payment_id: str) -> str:
    payload = f"{order_id}|{payment_id}"
    return hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _post_webhook(client: TestClient, rzp_order_id: str, payment_id: str = "pay_stock_1"):
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {"entity": {"order_id": rzp_order_id, "id": payment_id}},
        },
    }
    body = json.dumps(payload).encode("utf-8")
    return client.post(
        "/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": _sign_webhook(body)},
    )


def _post_verify(client: TestClient, rzp_order_id: str, payment_id: str = "pay_verify_1"):
    sig = _sign_payment(rzp_order_id, payment_id)
    return client.post(
        "/api/verify-payment",
        json={
            "razorpay_order_id": rzp_order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": sig,
            "session_id": "sess_stock",
        },
    )


@pytest.mark.asyncio
async def test_webhook_capture_decrements_stock(capture_db):
    db, product_id, rzp_order_id = capture_db

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        response = _post_webhook(client, rzp_order_id)
    app.dependency_overrides.clear()

    assert response.status_code == 200
    product = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one()
    assert product.stock_quantity == 1


@pytest.mark.asyncio
async def test_verify_payment_decrements_stock(capture_db):
    db, product_id, rzp_order_id = capture_db

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        response = _post_verify(client, rzp_order_id)
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "captured"
    product = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one()
    assert product.stock_quantity == 1


@pytest.mark.asyncio
async def test_verify_then_webhook_does_not_double_decrement(capture_db):
    db, product_id, rzp_order_id = capture_db

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        verify_resp = _post_verify(client, rzp_order_id, "pay_dual_1")
        webhook_resp = _post_webhook(client, rzp_order_id, "pay_dual_2")
    app.dependency_overrides.clear()

    assert verify_resp.status_code == 200
    assert webhook_resp.status_code == 200
    product = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one()
    assert product.stock_quantity == 1


@pytest.mark.asyncio
async def test_webhook_then_verify_does_not_double_decrement(capture_db):
    db, product_id, rzp_order_id = capture_db

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        webhook_resp = _post_webhook(client, rzp_order_id, "pay_dual_3")
        verify_resp = _post_verify(client, rzp_order_id, "pay_dual_4")
    app.dependency_overrides.clear()

    assert webhook_resp.status_code == 200
    assert verify_resp.status_code == 200
    product = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one()
    assert product.stock_quantity == 1
