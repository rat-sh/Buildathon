"""
agents/validator.py — Deterministic Safety Gate (Non-Bypassable)
=================================================================
CORE ARCHITECTURE PRINCIPLE:
  LLMs can ONLY propose.
  The Validator Agent is a 100% PURE DETERMINISTIC PYTHON CODE GATE.
  No LLM prompt or decision logic exists inside this file.
  Nothing reaches Razorpay or Payment Agent without a PASS result from this gate.

7 Mandatory Safety Checks:
  1. ITEM INTEGRITY       : product_id exists and is_active = True (ITEM_NOT_FOUND / ITEM_INACTIVE)
  2. PRICE INTEGRITY      : charged_price_paisa <= catalog price_paisa (PRICE_MISMATCH)
  3. STOCK INTEGRITY      : quantity_requested <= stock_quantity (STOCK_OUT)
  4. PER-TX LIMIT         : cart_total_paisa <= per_tx_limit (TX_LIMIT_EXCEEDED)
  5. DAILY SPEND CEILING  : daily_spent + cart_total <= daily_ceiling (DAILY_LIMIT_EXCEEDED)
  6. SUGGESTION PROVENANCE: every suggestion item has explicitly_accepted = True (ADDON_NOT_ACCEPTED)
  7. IDEMPOTENCY          : idempotency_key is unique across all orders (DUPLICATE_IDEMPOTENCY_KEY)

Reason codes (exact match required):
  PASS, ITEM_NOT_FOUND, ITEM_INACTIVE, PRICE_MISMATCH, STOCK_OUT,
  TX_LIMIT_EXCEEDED, DAILY_LIMIT_EXCEEDED, ADDON_NOT_ACCEPTED, DUPLICATE_IDEMPOTENCY_KEY
"""

import time
from datetime import datetime, timezone
from typing import Optional, Tuple

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.limits import get_limits_for_buyer
from app.models.cart import Cart, CartItem, CartStatus
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.schemas.validator import ValidationRequest, ValidationResult, ValidatorPassToken

logger = structlog.get_logger(__name__)


class ValidatorAgent:
    """
    Pure deterministic validation engine.
    Stateless execution per request, reading live DB state.
    """

    @staticmethod
    async def validate_cart(
        db: AsyncSession,
        request: ValidationRequest,
    ) -> ValidationResult:
        """
        Runs the 7 deterministic validation checks sequentially.
        Fails fast on the first failing check (Fail-Closed).

        Args:
            db: Async SQLAlchemy database session
            request: ValidationRequest containing cart_id, idempotency_key, buyer context

        Returns:
            ValidationResult containing decision (PASS/BLOCK), reason_code, evidence, and pass_token
        """
        logger.info(
            "Validator execution started",
            cart_id=request.cart_id,
            idempotency_key=request.idempotency_key,
            is_ai_buyer=request.is_ai_buyer,
        )

        # ── CHECK 7: Idempotency Key Uniqueness ───────────────────────────────
        # SAFETY: Prevent double-charges from re-submitted requests or network retries.
        stmt_idemp = select(Order).where(Order.idempotency_key == request.idempotency_key)
        existing_order = (await db.execute(stmt_idemp)).scalar_one_or_none()

        if existing_order is not None:
            logger.warning(
                "Validator BLOCK: Duplicate idempotency key detected",
                idempotency_key=request.idempotency_key,
            )
            return ValidationResult(
                is_valid=False,
                decision="BLOCK",
                reason_code="DUPLICATE_IDEMPOTENCY_KEY",
                cart_id=request.cart_id,
                idempotency_key=request.idempotency_key,
                total_paisa=0,
                evidence={
                    "check": "idempotency_uniqueness",
                    "idempotency_key": request.idempotency_key,
                    "existing_order_id": existing_order.id,
                },
                message=f"Idempotency key '{request.idempotency_key}' has already been used.",
            )

        # ── Fetch Cart with Items ──────────────────────────────────────────────
        stmt_cart = (
            select(Cart)
            .options(selectinload(Cart.items).selectinload(CartItem.product))
            .where(Cart.id == request.cart_id)
        )
        cart = (await db.execute(stmt_cart)).scalar_one_or_none()

        if not cart:
            logger.warning("Validator BLOCK: Cart not found", cart_id=request.cart_id)
            return ValidationResult(
                is_valid=False,
                decision="BLOCK",
                reason_code="ITEM_NOT_FOUND",
                cart_id=request.cart_id,
                idempotency_key=request.idempotency_key,
                total_paisa=0,
                evidence={"check": "cart_exists", "cart_id": request.cart_id},
                message=f"Cart with ID {request.cart_id} does not exist.",
            )

        if not cart.items:
            logger.warning("Validator BLOCK: Empty cart", cart_id=request.cart_id)
            return ValidationResult(
                is_valid=False,
                decision="BLOCK",
                reason_code="ITEM_NOT_FOUND",
                cart_id=request.cart_id,
                idempotency_key=request.idempotency_key,
                total_paisa=0,
                evidence={"check": "cart_not_empty", "items_count": 0},
                message="Cart is empty.",
            )

        cart_total_paisa = cart.total_paisa

        # ── CHECK 1, 2, 3, 6: Line Item Level Checks ──────────────────────────
        for item in cart.items:
            product = item.product

            # Check 1a: Product exists
            if not product:
                logger.warning("Validator BLOCK: Item product missing", product_id=item.product_id)
                return ValidationResult(
                    is_valid=False,
                    decision="BLOCK",
                    reason_code="ITEM_NOT_FOUND",
                    cart_id=request.cart_id,
                    idempotency_key=request.idempotency_key,
                    total_paisa=cart_total_paisa,
                    evidence={
                        "check": "product_exists",
                        "product_id": item.product_id,
                    },
                    message=f"Product ID {item.product_id} not found in catalog.",
                )

            # Check 1b: Product is active
            if not product.is_active:
                logger.warning("Validator BLOCK: Product inactive", product_id=product.id, name=product.name)
                return ValidationResult(
                    is_valid=False,
                    decision="BLOCK",
                    reason_code="ITEM_INACTIVE",
                    cart_id=request.cart_id,
                    idempotency_key=request.idempotency_key,
                    total_paisa=cart_total_paisa,
                    evidence={
                        "check": "product_active",
                        "product_id": product.id,
                        "product_name": product.name,
                        "is_active": product.is_active,
                    },
                    message=f"Product '{product.name}' (ID {product.id}) is inactive and cannot be purchased.",
                )

            # Check 2: Price integrity (charged_price <= catalog price)
            # SAFETY: Prevents LLM hallucinated price inflation or price tampering.
            if item.charged_price_paisa > product.price_paisa:
                logger.warning(
                    "Validator BLOCK: Price mismatch detected (hallucination or tampering)",
                    product_id=product.id,
                    charged_paisa=item.charged_price_paisa,
                    catalog_paisa=product.price_paisa,
                )
                return ValidationResult(
                    is_valid=False,
                    decision="BLOCK",
                    reason_code="PRICE_MISMATCH",
                    cart_id=request.cart_id,
                    idempotency_key=request.idempotency_key,
                    total_paisa=cart_total_paisa,
                    evidence={
                        "check": "price_integrity",
                        "product_id": product.id,
                        "product_name": product.name,
                        "charged_price_paisa": item.charged_price_paisa,
                        "catalog_price_paisa": product.price_paisa,
                    },
                    message=(
                        f"Price mismatch for '{product.name}': charged price "
                        f"(₹{item.charged_price_paisa / 100:.2f}) exceeds catalog price "
                        f"(₹{product.price_paisa / 100:.2f})."
                    ),
                )

            # Check 3: Stock availability
            # SAFETY: Prevent selling out-of-stock items.
            if item.quantity > product.stock_quantity:
                logger.warning(
                    "Validator BLOCK: Stock out",
                    product_id=product.id,
                    requested_qty=item.quantity,
                    stock_qty=product.stock_quantity,
                )
                return ValidationResult(
                    is_valid=False,
                    decision="BLOCK",
                    reason_code="STOCK_OUT",
                    cart_id=request.cart_id,
                    idempotency_key=request.idempotency_key,
                    total_paisa=cart_total_paisa,
                    evidence={
                        "check": "stock_availability",
                        "product_id": product.id,
                        "product_name": product.name,
                        "requested_quantity": item.quantity,
                        "available_stock": product.stock_quantity,
                    },
                    message=(
                        f"Insufficient stock for '{product.name}': requested {item.quantity}, "
                        f"only {product.stock_quantity} available."
                    ),
                )

            # Check 6: Suggestion provenance (explicit opt-in acceptance)
            # SAFETY: Suggestion agent must NEVER auto-accept items. Customer/AI must explicitly accept.
            if item.is_suggestion and not item.explicitly_accepted:
                logger.warning(
                    "Validator BLOCK: Add-on item not explicitly accepted",
                    product_id=product.id,
                    item_id=item.id,
                )
                return ValidationResult(
                    is_valid=False,
                    decision="BLOCK",
                    reason_code="ADDON_NOT_ACCEPTED",
                    cart_id=request.cart_id,
                    idempotency_key=request.idempotency_key,
                    total_paisa=cart_total_paisa,
                    evidence={
                        "check": "suggestion_provenance",
                        "product_id": product.id,
                        "product_name": product.name,
                        "is_suggestion": item.is_suggestion,
                        "explicitly_accepted": item.explicitly_accepted,
                    },
                    message=f"Suggested add-on item '{product.name}' was not explicitly accepted.",
                )

        # ── CHECK 4: Per-Transaction Limit ────────────────────────────────────
        limits = get_limits_for_buyer(request.is_ai_buyer)
        per_tx_limit = limits["per_tx_limit_paisa"]

        if cart_total_paisa > per_tx_limit:
            logger.warning(
                "Validator BLOCK: Transaction limit exceeded",
                cart_total_paisa=cart_total_paisa,
                per_tx_limit_paisa=per_tx_limit,
                buyer_type=limits["buyer_type"],
            )
            return ValidationResult(
                is_valid=False,
                decision="BLOCK",
                reason_code="TX_LIMIT_EXCEEDED",
                cart_id=request.cart_id,
                idempotency_key=request.idempotency_key,
                total_paisa=cart_total_paisa,
                evidence={
                    "check": "per_tx_limit",
                    "cart_total_paisa": cart_total_paisa,
                    "per_tx_limit_paisa": per_tx_limit,
                    "buyer_type": limits["buyer_type"],
                },
                message=(
                    f"Cart total (₹{cart_total_paisa / 100:.2f}) exceeds single transaction limit "
                    f"(₹{per_tx_limit / 100:.2f}) for {limits['buyer_type']} buyer."
                ),
            )

        # ── CHECK 5: Daily Spending Ceiling ───────────────────────────────────
        # Calculate spending today for this session / buyer
        now_utc = datetime.now(timezone.utc)
        start_of_day = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=timezone.utc)

        # Query completed or active non-failed orders created today
        query_daily = select(func.coalesce(func.sum(Order.amount_paisa), 0)).where(
            Order.created_at >= start_of_day,
            Order.status.in_([OrderStatus.CREATED, OrderStatus.AUTHORIZED, OrderStatus.CAPTURED]),
        )

        if request.buyer_id:
            query_daily = query_daily.where(Order.buyer_id == request.buyer_id)
        elif request.session_id:
            query_daily = query_daily.where(Order.session_id == request.session_id)

        daily_spent_paisa = (await db.execute(query_daily)).scalar() or 0
        daily_ceiling = limits["daily_ceiling_paisa"]

        if daily_spent_paisa + cart_total_paisa > daily_ceiling:
            logger.warning(
                "Validator BLOCK: Daily spending ceiling exceeded",
                daily_spent_paisa=daily_spent_paisa,
                cart_total_paisa=cart_total_paisa,
                daily_ceiling_paisa=daily_ceiling,
            )
            return ValidationResult(
                is_valid=False,
                decision="BLOCK",
                reason_code="DAILY_LIMIT_EXCEEDED",
                cart_id=request.cart_id,
                idempotency_key=request.idempotency_key,
                total_paisa=cart_total_paisa,
                evidence={
                    "check": "daily_ceiling",
                    "daily_spent_paisa": daily_spent_paisa,
                    "cart_total_paisa": cart_total_paisa,
                    "projected_total_paisa": daily_spent_paisa + cart_total_paisa,
                    "daily_ceiling_paisa": daily_ceiling,
                },
                message=(
                    f"Transaction would breach daily limit. Currently spent today: "
                    f"₹{daily_spent_paisa / 100:.2f}, attempting: ₹{cart_total_paisa / 100:.2f}, "
                    f"daily ceiling: ₹{daily_ceiling / 100:.2f}."
                ),
            )

        # ── ALL CHECKS PASSED: Issue Pass Token ───────────────────────────────
        pass_token = ValidatorPassToken(
            cart_id=request.cart_id,
            idempotency_key=request.idempotency_key,
            total_paisa=cart_total_paisa,
            session_id=request.session_id,
            buyer_id=request.buyer_id,
            is_ai_buyer=request.is_ai_buyer,
            issued_at_timestamp=time.time(),
        )

        logger.info(
            "Validator PASS: All 7 checks successful",
            cart_id=request.cart_id,
            total_paisa=cart_total_paisa,
        )

        return ValidationResult(
            is_valid=True,
            decision="PASS",
            reason_code="PASS",
            cart_id=request.cart_id,
            idempotency_key=request.idempotency_key,
            total_paisa=cart_total_paisa,
            evidence={
                "check": "all_passed",
                "items_count": len(cart.items),
                "cart_total_paisa": cart_total_paisa,
                "per_tx_limit_paisa": per_tx_limit,
                "daily_spent_paisa": daily_spent_paisa,
                "daily_ceiling_paisa": daily_ceiling,
            },
            pass_token=pass_token,
            message="Validation successful. All safety checks passed.",
        )
