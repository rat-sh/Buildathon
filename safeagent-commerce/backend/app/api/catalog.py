"""
api/catalog.py — AI Buyer MCP Tool Endpoints
============================================
Exposes tool endpoints for external AI buyers:
  - GET  /catalog/products
  - GET  /catalog/products/{id}
  - GET  /catalog/limits
  - POST /catalog/intent
  - POST /catalog/checkout  (Validator-gated, same safety rails)

Auth: Uses API key verification (X-AI-Buyer-Key).
"""

from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.catalog import CatalogAgent
from app.agents.payment import PaymentAgent
from app.agents.validator import ValidatorAgent
from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_ai_buyer_api_key
from app.schemas.catalog import AICheckoutRequest, PurchaseIntentRequest, PurchaseIntentResponse
from app.schemas.validator import ValidationRequest
from app.services.audit_service import AuditService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["catalog"])


def verify_buyer_auth(x_ai_buyer_key: Optional[str] = Header(None, alias="X-AI-Buyer-Key")) -> str:
    """Dependency: Verifies API key for AI buyer endpoints."""
    expected_key = settings.AI_BUYER_API_KEY
    if not x_ai_buyer_key or not verify_ai_buyer_api_key(x_ai_buyer_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-AI-Buyer-Key header.",
        )
    return x_ai_buyer_key


@router.get("/products")
async def list_products(
    category: Optional[str] = Query(None, description="Category filter"),
    max_price_paisa: Optional[int] = Query(None, description="Max price in paisa"),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """MCP Tool: Search catalog products."""
    return await CatalogAgent.list_products(db, category=category, max_price_paisa=max_price_paisa, limit=limit)


@router.get("/products/{product_id}")
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    """MCP Tool: Get canonical product by ID."""
    product = await CatalogAgent.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    return product


@router.get("/limits")
async def get_spending_limits():
    """MCP Tool: Get spending limits for AI buyers."""
    return await CatalogAgent.get_spending_limits(is_ai_buyer=True)


@router.post("/intent", response_model=PurchaseIntentResponse)
async def create_purchase_intent(
    req: PurchaseIntentRequest,
    db: AsyncSession = Depends(get_db),
    auth_key: str = Depends(verify_buyer_auth),
):
    """
    MCP Tool: Create a purchase intent (cart) for an AI buyer.
    """
    try:
        items_dict = [{"product_id": item.product_id, "quantity": item.quantity} for item in req.items]
        intent = await CatalogAgent.create_purchase_intent(
            db=db,
            buyer_id=req.buyer_id,
            items=items_dict,
            idempotency_key=req.idempotency_key,
        )

        await AuditService.log_event(
            db=db,
            actor="ai_buyer",
            action="create_purchase_intent",
            decision="PASS",
            buyer_id=req.buyer_id,
            target_type="cart",
            target_id=str(intent["cart_id"]),
            evidence={"idempotency_key": req.idempotency_key, "total_paisa": intent["total_paisa"]},
            message=f"AI Buyer '{req.buyer_id}' created purchase intent for cart #{intent['cart_id']}.",
        )

        return intent
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/checkout")
async def ai_buyer_checkout(
    req: AICheckoutRequest,
    db: AsyncSession = Depends(get_db),
    auth_key: str = Depends(verify_buyer_auth),
):
    """
    MCP Tool: Execute payment for AI buyer purchase intent.

    SAME SAFETY GATE APPLIED TO AI BUYERS:
      1. ValidatorAgent checks item integrity, stock, AI spending limits, idempotency key.
      2. On PASS, PaymentAgent creates Razorpay order.
      3. On BLOCK, returns structured failure response + logs audit event.
    """
    val_req = ValidationRequest(
        cart_id=req.cart_id,
        idempotency_key=req.idempotency_key,
        buyer_id=req.buyer_id,
        is_ai_buyer=True,
    )

    # ── VALIDATOR GATE ────────────────────────────────────────────────────────
    val_result = await ValidatorAgent.validate_cart(db, val_req)
    await AuditService.log_validation_result(db, val_result, buyer_id=req.buyer_id)

    if not val_result.is_valid:
        logger.warning(
            "AI Buyer Checkout BLOCKED by Validator",
            buyer_id=req.buyer_id,
            reason_code=val_result.reason_code,
        )
        return {
            "status": "blocked",
            "is_valid": False,
            "reason_code": val_result.reason_code,
            "message": val_result.message,
            "evidence": val_result.evidence,
        }

    # ── PAYMENT AGENT EXECUTION ───────────────────────────────────────────────
    payment_agent = PaymentAgent()
    checkout_data = await payment_agent.execute_payment(db, val_result.pass_token)

    return {
        "status": "success",
        "is_valid": True,
        "reason_code": "PASS",
        "checkout_data": checkout_data,
    }
