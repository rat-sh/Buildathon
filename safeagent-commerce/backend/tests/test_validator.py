"""
tests/test_validator.py — Test suite for ValidatorAgent
=========================================================
Tests all 9 reason codes & validation checks:
  1. PASS
  2. ITEM_NOT_FOUND
  3. ITEM_INACTIVE
  4. PRICE_MISMATCH
  5. STOCK_OUT
  6. TX_LIMIT_EXCEEDED
  7. DAILY_LIMIT_EXCEEDED
  8. ADDON_NOT_ACCEPTED
  9. DUPLICATE_IDEMPOTENCY_KEY
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.database import Base
from app.core.limits import PER_TX_LIMIT_PAISA, DAILY_CEILING_PAISA, AI_BUYER_PER_TX_LIMIT_PAISA
from app.models.cart import Cart, CartItem, CartStatus
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.agents.validator import ValidatorAgent
from app.schemas.validator import ValidationRequest


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


# ── Sample Product Fixtures ───────────────────────────────────────────────────
@pytest_asyncio.fixture
async def seed_products(test_db: AsyncSession):
    p1 = Product(
        id=1,
        name="Nike Running Shoes",
        sku="NIKE-RUN-9",
        category="running_shoes",
        price_paisa=399900,  # ₹3,999.00
        currency="INR",
        stock_quantity=10,
        is_active=True,
    )
    p2 = Product(
        id=2,
        name="Discontinued Socks",
        sku="OLD-SOCKS",
        category="accessories",
        price_paisa=19900,   # ₹199.00
        currency="INR",
        stock_quantity=5,
        is_active=False,     # INACTIVE
    )
    p3 = Product(
        id=3,
        name="Low Stock Insoles",
        sku="INSOLES-LOW",
        category="accessories",
        price_paisa=49900,   # ₹499.00
        currency="INR",
        stock_quantity=1,    # Only 1 in stock
        is_active=True,
    )
    p4 = Product(
        id=4,
        name="Expensive Luxury Watch",
        sku="LUX-WATCH-1",
        category="electronics",
        price_paisa=1200000,  # ₹12,000.00 (Exceeds ₹10,000 PER_TX_LIMIT)
        currency="INR",
        stock_quantity=5,
        is_active=True,
    )
    test_db.add_all([p1, p2, p3, p4])
    await test_db.commit()
    return [p1, p2, p3, p4]


# ── TEST 1: PASS Case ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_validator_pass(test_db: AsyncSession, seed_products):
    cart = Cart(session_id="sess_123", status=CartStatus.OPEN)
    test_db.add(cart)
    await test_db.commit()
    await test_db.refresh(cart)

    item = CartItem(
        cart_id=cart.id,
        product_id=1,
        quantity=1,
        charged_price_paisa=399900,  # Matches catalog price
        is_suggestion=False,
        explicitly_accepted=False,
    )
    test_db.add(item)
    await test_db.commit()

    req = ValidationRequest(
        cart_id=cart.id,
        idempotency_key="idemp_pass_1",
        session_id="sess_123",
        is_ai_buyer=False,
    )

    res = await ValidatorAgent.validate_cart(test_db, req)

    assert res.is_valid is True
    assert res.decision == "PASS"
    assert res.reason_code == "PASS"
    assert res.pass_token is not None
    assert res.pass_token.cart_id == cart.id
    assert res.pass_token.total_paisa == 399900


# ── TEST 2: ITEM_NOT_FOUND (Invalid product_id) ──────────────────────────────
@pytest.mark.asyncio
async def test_validator_item_not_found(test_db: AsyncSession, seed_products):
    cart = Cart(session_id="sess_123", status=CartStatus.OPEN)
    test_db.add(cart)
    await test_db.commit()

    item = CartItem(
        cart_id=cart.id,
        product_id=999,  # Non-existent product ID
        quantity=1,
        charged_price_paisa=10000,
    )
    test_db.add(item)
    await test_db.commit()

    req = ValidationRequest(cart_id=cart.id, idempotency_key="idemp_notfound")
    res = await ValidatorAgent.validate_cart(test_db, req)

    assert res.is_valid is False
    assert res.decision == "BLOCK"
    assert res.reason_code == "ITEM_NOT_FOUND"


# ── TEST 3: ITEM_INACTIVE ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_validator_item_inactive(test_db: AsyncSession, seed_products):
    cart = Cart(session_id="sess_123", status=CartStatus.OPEN)
    test_db.add(cart)
    await test_db.commit()

    item = CartItem(
        cart_id=cart.id,
        product_id=2,  # Product 2 is is_active=False
        quantity=1,
        charged_price_paisa=19900,
    )
    test_db.add(item)
    await test_db.commit()

    req = ValidationRequest(cart_id=cart.id, idempotency_key="idemp_inactive")
    res = await ValidatorAgent.validate_cart(test_db, req)

    assert res.is_valid is False
    assert res.decision == "BLOCK"
    assert res.reason_code == "ITEM_INACTIVE"


# ── TEST 4: PRICE_MISMATCH (Charged price > catalog price) ───────────────────
@pytest.mark.asyncio
async def test_validator_price_mismatch(test_db: AsyncSession, seed_products):
    cart = Cart(session_id="sess_123", status=CartStatus.OPEN)
    test_db.add(cart)
    await test_db.commit()

    item = CartItem(
        cart_id=cart.id,
        product_id=1,  # Catalog price is ₹3,999 (399900 paisa)
        quantity=1,
        charged_price_paisa=450000,  # Tampered/hallucinated price: ₹4,500
    )
    test_db.add(item)
    await test_db.commit()

    req = ValidationRequest(cart_id=cart.id, idempotency_key="idemp_pricemismatch")
    res = await ValidatorAgent.validate_cart(test_db, req)

    assert res.is_valid is False
    assert res.decision == "BLOCK"
    assert res.reason_code == "PRICE_MISMATCH"


# ── TEST 5: STOCK_OUT (Quantity requested > available stock) ─────────────────
@pytest.mark.asyncio
async def test_validator_stock_out(test_db: AsyncSession, seed_products):
    cart = Cart(session_id="sess_123", status=CartStatus.OPEN)
    test_db.add(cart)
    await test_db.commit()

    item = CartItem(
        cart_id=cart.id,
        product_id=3,  # Stock is 1
        quantity=5,    # Requested 5
        charged_price_paisa=49900,
    )
    test_db.add(item)
    await test_db.commit()

    req = ValidationRequest(cart_id=cart.id, idempotency_key="idemp_stockout")
    res = await ValidatorAgent.validate_cart(test_db, req)

    assert res.is_valid is False
    assert res.decision == "BLOCK"
    assert res.reason_code == "STOCK_OUT"


# ── TEST 6: TX_LIMIT_EXCEEDED (Cart total > PER_TX_LIMIT) ────────────────────
@pytest.mark.asyncio
async def test_validator_tx_limit_exceeded(test_db: AsyncSession, seed_products):
    cart = Cart(session_id="sess_123", status=CartStatus.OPEN)
    test_db.add(cart)
    await test_db.commit()

    item = CartItem(
        cart_id=cart.id,
        product_id=4,  # Price is ₹12,000 (1200000 paisa), limit is ₹10,000 (1000000 paisa)
        quantity=1,
        charged_price_paisa=1200000,
    )
    test_db.add(item)
    await test_db.commit()

    req = ValidationRequest(cart_id=cart.id, idempotency_key="idemp_txlimit", is_ai_buyer=False)
    res = await ValidatorAgent.validate_cart(test_db, req)

    assert res.is_valid is False
    assert res.decision == "BLOCK"
    assert res.reason_code == "TX_LIMIT_EXCEEDED"


# ── TEST 7: DAILY_LIMIT_EXCEEDED ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_validator_daily_limit_exceeded(test_db: AsyncSession, seed_products):
    # Create an existing order for today totaling ₹18,000 (1800000 paisa)
    cart_old = Cart(session_id="sess_daily_user", status=CartStatus.PAID)
    test_db.add(cart_old)
    await test_db.commit()

    prior_order = Order(
        cart_id=cart_old.id,
        idempotency_key="prior_order_1",
        amount_paisa=1800000,
        status=OrderStatus.CAPTURED,
        session_id="sess_daily_user",
    )
    test_db.add(prior_order)

    # Now create new cart for ₹3,000 (300000 paisa) -> Total = ₹21,000 > ₹20,000 DAILY_CEILING
    cart_new = Cart(session_id="sess_daily_user", status=CartStatus.OPEN)
    test_db.add(cart_new)
    await test_db.commit()

    item = CartItem(
        cart_id=cart_new.id,
        product_id=1,
        quantity=1,
        charged_price_paisa=300000,  # ₹3,000
    )
    test_db.add(item)
    await test_db.commit()

    req = ValidationRequest(
        cart_id=cart_new.id,
        idempotency_key="idemp_dailylimit",
        session_id="sess_daily_user",
        is_ai_buyer=False,
    )
    res = await ValidatorAgent.validate_cart(test_db, req)

    assert res.is_valid is False
    assert res.decision == "BLOCK"
    assert res.reason_code == "DAILY_LIMIT_EXCEEDED"


# ── TEST 8: ADDON_NOT_ACCEPTED (Unaccepted suggestion) ───────────────────────
@pytest.mark.asyncio
async def test_validator_addon_not_accepted(test_db: AsyncSession, seed_products):
    cart = Cart(session_id="sess_123", status=CartStatus.OPEN)
    test_db.add(cart)
    await test_db.commit()

    # Main item (accepted / regular)
    item1 = CartItem(
        cart_id=cart.id,
        product_id=1,
        quantity=1,
        charged_price_paisa=399900,
        is_suggestion=False,
    )
    # Suggested add-on item but NOT accepted!
    item2 = CartItem(
        cart_id=cart.id,
        product_id=3,
        quantity=1,
        charged_price_paisa=49900,
        is_suggestion=True,
        explicitly_accepted=False,  # <--- NOT ACCEPTED BY USER
    )
    test_db.add_all([item1, item2])
    await test_db.commit()

    req = ValidationRequest(cart_id=cart.id, idempotency_key="idemp_addon")
    res = await ValidatorAgent.validate_cart(test_db, req)

    assert res.is_valid is False
    assert res.decision == "BLOCK"
    assert res.reason_code == "ADDON_NOT_ACCEPTED"


# ── TEST 9: DUPLICATE_IDEMPOTENCY_KEY ────────────────────────────────────────
@pytest.mark.asyncio
async def test_validator_duplicate_idempotency(test_db: AsyncSession, seed_products):
    cart = Cart(session_id="sess_123", status=CartStatus.OPEN)
    test_db.add(cart)
    await test_db.commit()

    item = CartItem(
        cart_id=cart.id,
        product_id=1,
        quantity=1,
        charged_price_paisa=399900,
    )
    test_db.add(item)

    # Pre-existing order with same idempotency key
    existing_order = Order(
        cart_id=cart.id,
        idempotency_key="idemp_used_already",
        amount_paisa=399900,
        status=OrderStatus.CREATED,
    )
    test_db.add(existing_order)
    await test_db.commit()

    req = ValidationRequest(cart_id=cart.id, idempotency_key="idemp_used_already")
    res = await ValidatorAgent.validate_cart(test_db, req)

    assert res.is_valid is False
    assert res.decision == "BLOCK"
    assert res.reason_code == "DUPLICATE_IDEMPOTENCY_KEY"


# ── TEST 10: CART_ALREADY_PAID (paid cart status) ────────────────────────────
@pytest.mark.asyncio
async def test_validator_cart_already_paid_status(test_db: AsyncSession, seed_products):
    cart = Cart(session_id="sess_paid", status=CartStatus.PAID)
    test_db.add(cart)
    await test_db.commit()

    item = CartItem(
        cart_id=cart.id,
        product_id=1,
        quantity=1,
        charged_price_paisa=399900,
    )
    test_db.add(item)
    await test_db.commit()

    req = ValidationRequest(
        cart_id=cart.id,
        idempotency_key="idemp_paid_cart",
        session_id="sess_paid",
        is_ai_buyer=False,
    )
    res = await ValidatorAgent.validate_cart(test_db, req)

    assert res.is_valid is False
    assert res.decision == "BLOCK"
    assert res.reason_code == "CART_ALREADY_PAID"


# ── TEST 11: CART_ALREADY_PAID (captured order on open cart) ─────────────────
@pytest.mark.asyncio
async def test_validator_cart_already_paid_captured_order(test_db: AsyncSession, seed_products):
    cart = Cart(session_id="sess_captured", status=CartStatus.LOCKED)
    test_db.add(cart)
    await test_db.commit()

    item = CartItem(
        cart_id=cart.id,
        product_id=1,
        quantity=1,
        charged_price_paisa=399900,
    )
    test_db.add(item)

    captured_order = Order(
        cart_id=cart.id,
        idempotency_key="idemp_captured",
        amount_paisa=399900,
        status=OrderStatus.CAPTURED,
        session_id="sess_captured",
    )
    test_db.add(captured_order)
    await test_db.commit()

    req = ValidationRequest(
        cart_id=cart.id,
        idempotency_key="idemp_retry_after_capture",
        session_id="sess_captured",
        is_ai_buyer=False,
    )
    res = await ValidatorAgent.validate_cart(test_db, req)

    assert res.is_valid is False
    assert res.decision == "BLOCK"
    assert res.reason_code == "CART_ALREADY_PAID"
