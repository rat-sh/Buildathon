"""
agents/validator_checks.py — The 7 Deterministic Safety Checks
================================================================
Pure check functions called by ValidatorAgent.validate_cart().
Each function returns (is_valid, ValidationResult | None).
None means the check PASSED. A ValidationResult means BLOCKED.

These are the only business rules that gate payment.
No LLM logic exists here. No external I/O except DB reads.
"""

from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import get_limits_for_buyer
from app.models.order import Order, OrderStatus
from app.schemas.validator import ValidationRequest, ValidationResult

logger = structlog.get_logger(__name__)


def _block(request: ValidationRequest, reason_code: str, total_paisa: int, evidence: dict, message: str) -> ValidationResult:
    """Shorthand to build a BLOCK result."""
    return ValidationResult(
        is_valid=False,
        decision="BLOCK",
        reason_code=reason_code,
        cart_id=request.cart_id,
        idempotency_key=request.idempotency_key,
        total_paisa=total_paisa,
        evidence=evidence,
        message=message,
    )


async def check_idempotency(db: AsyncSession, request: ValidationRequest) -> ValidationResult | None:
    """Check 7: Idempotency key must be unique — prevents double-charges."""
    existing = (await db.execute(
        select(Order).where(Order.idempotency_key == request.idempotency_key)
    )).scalar_one_or_none()

    if existing:
        logger.warning("Validator BLOCK: duplicate idempotency key", key=request.idempotency_key)
        return _block(
            request, "DUPLICATE_IDEMPOTENCY_KEY", 0,
            {"check": "idempotency_uniqueness", "idempotency_key": request.idempotency_key, "existing_order_id": existing.id},
            f"Idempotency key '{request.idempotency_key}' has already been used.",
        )
    return None


def check_item_exists(request: ValidationRequest, item, cart_total_paisa: int) -> ValidationResult | None:
    """Check 1a: Product must exist in catalog."""
    if not item.product:
        logger.warning("Validator BLOCK: product missing", product_id=item.product_id)
        return _block(
            request, "ITEM_NOT_FOUND", cart_total_paisa,
            {"check": "product_exists", "product_id": item.product_id},
            f"Product ID {item.product_id} not found in catalog.",
        )
    return None


def check_item_active(request: ValidationRequest, item, cart_total_paisa: int) -> ValidationResult | None:
    """Check 1b: Product must be active."""
    p = item.product
    if not p.is_active:
        logger.warning("Validator BLOCK: product inactive", product_id=p.id, name=p.name)
        return _block(
            request, "ITEM_INACTIVE", cart_total_paisa,
            {"check": "product_active", "product_id": p.id, "product_name": p.name, "is_active": p.is_active},
            f"Product '{p.name}' (ID {p.id}) is inactive and cannot be purchased.",
        )
    return None


def check_price_integrity(request: ValidationRequest, item, cart_total_paisa: int) -> ValidationResult | None:
    """Check 2: Charged price must not exceed catalog price — blocks LLM price inflation."""
    p = item.product
    if item.charged_price_paisa > p.price_paisa:
        logger.warning("Validator BLOCK: price mismatch", product_id=p.id, charged=item.charged_price_paisa, catalog=p.price_paisa)
        return _block(
            request, "PRICE_MISMATCH", cart_total_paisa,
            {"check": "price_integrity", "product_id": p.id, "product_name": p.name,
             "charged_price_paisa": item.charged_price_paisa, "catalog_price_paisa": p.price_paisa},
            f"Price mismatch for '{p.name}': charged ₹{item.charged_price_paisa/100:.2f} > catalog ₹{p.price_paisa/100:.2f}.",
        )
    return None


def check_stock(request: ValidationRequest, item, cart_total_paisa: int) -> ValidationResult | None:
    """Check 3: Requested quantity must not exceed available stock."""
    p = item.product
    if item.quantity > p.stock_quantity:
        logger.warning("Validator BLOCK: stock out", product_id=p.id, requested=item.quantity, available=p.stock_quantity)
        return _block(
            request, "STOCK_OUT", cart_total_paisa,
            {"check": "stock_availability", "product_id": p.id, "product_name": p.name,
             "requested_quantity": item.quantity, "available_stock": p.stock_quantity},
            f"Insufficient stock for '{p.name}': requested {item.quantity}, only {p.stock_quantity} available.",
        )
    return None


def check_addon_accepted(request: ValidationRequest, item, cart_total_paisa: int) -> ValidationResult | None:
    """Check 6: Every suggestion item must have explicit user opt-in."""
    p = item.product
    if item.is_suggestion and not item.explicitly_accepted:
        logger.warning("Validator BLOCK: addon not accepted", product_id=p.id, item_id=item.id)
        return _block(
            request, "ADDON_NOT_ACCEPTED", cart_total_paisa,
            {"check": "suggestion_provenance", "product_id": p.id, "product_name": p.name,
             "is_suggestion": True, "explicitly_accepted": False},
            f"Suggested add-on '{p.name}' was not explicitly accepted.",
        )
    return None


def check_tx_limit(request: ValidationRequest, cart_total_paisa: int, limits: dict) -> ValidationResult | None:
    """Check 4: Cart total must not exceed per-transaction limit."""
    per_tx_limit = limits["per_tx_limit_paisa"]
    if cart_total_paisa > per_tx_limit:
        logger.warning("Validator BLOCK: tx limit exceeded", total=cart_total_paisa, limit=per_tx_limit)
        return _block(
            request, "TX_LIMIT_EXCEEDED", cart_total_paisa,
            {"check": "per_tx_limit", "cart_total_paisa": cart_total_paisa,
             "per_tx_limit_paisa": per_tx_limit, "buyer_type": limits["buyer_type"]},
            f"Cart total ₹{cart_total_paisa/100:.2f} exceeds per-tx limit ₹{per_tx_limit/100:.2f} for {limits['buyer_type']} buyer.",
        )
    return None


async def check_daily_ceiling(db: AsyncSession, request: ValidationRequest, cart_total_paisa: int, limits: dict) -> ValidationResult | None:
    """Check 5: Daily spending ceiling — today's orders + this cart must not breach limit."""
    now_utc = datetime.now(timezone.utc)
    start_of_day = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=timezone.utc)

    q = select(func.coalesce(func.sum(Order.amount_paisa), 0)).where(
        Order.created_at >= start_of_day,
        Order.status.in_([OrderStatus.CREATED, OrderStatus.AUTHORIZED, OrderStatus.CAPTURED]),
    )
    if request.buyer_id:
        q = q.where(Order.buyer_id == request.buyer_id)
    elif request.session_id:
        q = q.where(Order.session_id == request.session_id)

    daily_spent = (await db.execute(q)).scalar() or 0
    daily_ceiling = limits["daily_ceiling_paisa"]

    if daily_spent + cart_total_paisa > daily_ceiling:
        logger.warning("Validator BLOCK: daily ceiling exceeded", spent=daily_spent, adding=cart_total_paisa, ceiling=daily_ceiling)
        return _block(
            request, "DAILY_LIMIT_EXCEEDED", cart_total_paisa,
            {"check": "daily_ceiling", "daily_spent_paisa": daily_spent, "cart_total_paisa": cart_total_paisa,
             "projected_total_paisa": daily_spent + cart_total_paisa, "daily_ceiling_paisa": daily_ceiling},
            f"Would breach daily limit. Spent today ₹{daily_spent/100:.2f} + this ₹{cart_total_paisa/100:.2f} > ceiling ₹{daily_ceiling/100:.2f}.",
        )
    return daily_spent
