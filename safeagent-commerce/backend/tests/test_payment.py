"""
tests/test_payment.py — Test suite for PaymentAgent and Webhook Handler
========================================================================
Tests:
  1. PaymentAgent executes order creation with valid ValidatorPassToken
  2. PaymentAgent fails with ValueError if pass_token is invalid / missing
  3. PaymentAgent respects MAX_PAYMENT_RETRIES limit (max 2 retries)
  4. Webhook handler rejects invalid HMAC signature (HTTP 400)
  5. Webhook handler processes valid payment.captured event and updates order status
"""

import hmac
import hashlib
import json
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.database import Base, get_db
from app.core.config import settings
from app.models.cart import Cart, CartItem, CartStatus
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.agents.payment import PaymentAgent
from app.schemas.validator import ValidatorPassToken
from app.main import app


# ── In-Memory SQLite Async Database Fixture for Testing ───────────────────────
@pytest_asyncio.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


# ── TEST 1: PaymentAgent Execution with Valid Pass Token ──────────────────────
@pytest.mark.asyncio
async def test_payment_agent_valid_pass_token(test_db: AsyncSession):
    cart = Cart(session_id="sess_payment_test", status=CartStatus.OPEN)
    test_db.add(cart)
    await test_db.commit()

    pass_token = ValidatorPassToken(
        cart_id=cart.id,
        idempotency_key="idemp_pay_test_1",
        total_paisa=299900,
        session_id="sess_payment_test",
        is_ai_buyer=False,
        issued_at_timestamp=1722345678.0,
    )

    agent = PaymentAgent()
    result = await agent.execute_payment(test_db, pass_token)

    assert result["status"] == "created"
    assert result["amount_paisa"] == 299900
    assert result["attempt_count"] == 1
    assert "razorpay_order_id" in result

    # Verify cart status is locked
    await test_db.refresh(cart)
    assert cart.status == CartStatus.LOCKED


# ── TEST 2: PaymentAgent Token Requirement Enforcement ────────────────────────
@pytest.mark.asyncio
async def test_payment_agent_rejects_missing_pass_token(test_db: AsyncSession):
    agent = PaymentAgent()
    with pytest.raises(ValueError) as exc_info:
        await agent.execute_payment(test_db, pass_token="invalid_token_string")

    assert "ValidatorPassToken" in str(exc_info.value)


# ── TEST 3: PaymentAgent Enforces MAX_PAYMENT_RETRIES (Max 2) ────────────────
@pytest.mark.asyncio
async def test_payment_agent_max_retries_exceeded(test_db: AsyncSession):
    cart = Cart(session_id="sess_retry_test", status=CartStatus.OPEN)
    test_db.add(cart)
    await test_db.commit()

    # Pre-create 2 existing order attempts
    order1 = Order(cart_id=cart.id, idempotency_key="idemp_retry_1", amount_paisa=10000, attempt_count=1)
    order2 = Order(cart_id=cart.id, idempotency_key="idemp_retry_2", amount_paisa=10000, attempt_count=2)
    test_db.add_all([order1, order2])
    await test_db.commit()

    pass_token = ValidatorPassToken(
        cart_id=cart.id,
        idempotency_key="idemp_retry_3",  # Attempt 3 -> should block
        total_paisa=10000,
        session_id="sess_retry_test",
        is_ai_buyer=False,
        issued_at_timestamp=1722345678.0,
    )

    agent = PaymentAgent()
    with pytest.raises(RuntimeError) as exc_info:
        await agent.execute_payment(test_db, pass_token)

    assert "Maximum payment retries" in str(exc_info.value)

    # Verify cart is marked FAILED
    await test_db.refresh(cart)
    assert cart.status == CartStatus.FAILED


# ── TEST 4: Webhook HMAC Signature Failure Rejection ─────────────────────────
def test_webhook_invalid_hmac_rejected():
    client = TestClient(app)

    headers = {"X-Razorpay-Signature": "invalid_bogus_signature"}
    payload = {"event": "payment.captured", "payload": {}}

    response = client.post("/webhooks/razorpay", json=payload, headers=headers)

    assert response.status_code == 400
    assert "Invalid Razorpay webhook signature" in response.json()["detail"]
