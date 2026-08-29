"""
agents/validator.py — Safety Gate Orchestrator (Non-Bypassable)
================================================================
Runs the 7 deterministic checks (from validator_checks.py) sequentially.
Fails fast on the first failing check (Fail-Closed).

ARCHITECTURE PRINCIPLE:
  - Pure deterministic Python — zero LLM calls.
  - Nothing reaches Razorpay without a PASS token from this module.
  - Each check lives in validator_checks.py (one function = one check).

7 checks (reason codes):
  ITEM_NOT_FOUND | ITEM_INACTIVE | PRICE_MISMATCH | STOCK_OUT |
  TX_LIMIT_EXCEEDED | DAILY_LIMIT_EXCEEDED | ADDON_NOT_ACCEPTED |
  DUPLICATE_IDEMPOTENCY_KEY | CART_ALREADY_PAID
"""

import time

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.validator_checks import (
    check_addon_accepted,
    check_cart_checkout_eligible,
    check_daily_ceiling,
    check_idempotency,
    check_item_active,
    check_item_exists,
    check_price_integrity,
    check_stock,
    check_tx_limit,
)
from app.core.limits import get_limits_for_buyer
from app.models.cart import Cart, CartItem
from app.schemas.validator import ValidationRequest, ValidationResult, ValidatorPassToken

logger = structlog.get_logger(__name__)


class ValidatorAgent:
    """Pure deterministic validation engine — stateless per request."""

    @staticmethod
    async def validate_cart(db: AsyncSession, request: ValidationRequest) -> ValidationResult:
        """
        Run all 7 checks in sequence. Return BLOCK on first failure, PASS if all pass.
        """
        logger.info("Validator started", cart_id=request.cart_id, is_ai_buyer=request.is_ai_buyer)

        # Check 7: Idempotency
        if (result := await check_idempotency(db, request)):
            return result

        # Load cart
        cart = (await db.execute(
            select(Cart)
            .options(selectinload(Cart.items).selectinload(CartItem.product))
            .where(Cart.id == request.cart_id)
        )).scalar_one_or_none()

        if not cart:
            from app.agents.validator_checks import _block
            return _block(request, "ITEM_NOT_FOUND", 0,
                          {"check": "cart_exists", "cart_id": request.cart_id},
                          f"Cart {request.cart_id} does not exist.")

        if not cart.items:
            from app.agents.validator_checks import _block
            return _block(request, "ITEM_NOT_FOUND", 0,
                          {"check": "cart_not_empty", "items_count": 0},
                          "Cart is empty.")

        if (result := await check_cart_checkout_eligible(db, request, cart)):
            return result

        cart_total = cart.total_paisa

        # Checks 1a, 1b, 2, 3, 6: per-item checks
        for item in cart.items:
            for check_fn in (check_item_exists, check_item_active, check_price_integrity, check_stock, check_addon_accepted):
                if (result := check_fn(request, item, cart_total)):
                    return result

        # Check 4: Per-transaction limit
        limits = get_limits_for_buyer(request.is_ai_buyer)
        if (result := check_tx_limit(request, cart_total, limits)):
            return result

        # Check 5: Daily ceiling
        daily_result = await check_daily_ceiling(db, request, cart_total, limits)
        if isinstance(daily_result, ValidationResult):
            return daily_result
        daily_spent = daily_result if daily_result is not None else 0

        # ALL PASSED — issue pass token
        pass_token = ValidatorPassToken(
            cart_id=request.cart_id,
            idempotency_key=request.idempotency_key,
            total_paisa=cart_total,
            session_id=request.session_id,
            buyer_id=request.buyer_id,
            is_ai_buyer=request.is_ai_buyer,
            issued_at_timestamp=time.time(),
        )
        logger.info("Validator PASS: all 7 checks passed", cart_id=request.cart_id, total_paisa=cart_total)

        return ValidationResult(
            is_valid=True,
            decision="PASS",
            reason_code="PASS",
            cart_id=request.cart_id,
            idempotency_key=request.idempotency_key,
            total_paisa=cart_total,
            evidence={
                "check": "all_passed",
                "items_count": len(cart.items),
                "cart_total_paisa": cart_total,
                "per_tx_limit_paisa": limits["per_tx_limit_paisa"],
                "daily_spent_paisa": daily_spent,
                "daily_ceiling_paisa": limits["daily_ceiling_paisa"],
            },
            pass_token=pass_token,
            message="Validation successful. All safety checks passed.",
        )
