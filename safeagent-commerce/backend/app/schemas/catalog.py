"""
schemas/catalog.py — Pydantic schemas for AI Buyer Catalog MCP API
===================================================================
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PurchaseIntentItem(BaseModel):
    """Line item in purchase intent."""
    product_id: int
    quantity: int = 1


class PurchaseIntentRequest(BaseModel):
    """Purchase intent submitted by an external AI buyer."""
    buyer_id: str = Field(description="Unique AI buyer token/identifier")
    items: List[PurchaseIntentItem] = Field(description="List of requested line items")
    idempotency_key: str = Field(description="Unique transaction idempotency key")


class AICheckoutRequest(BaseModel):
    """Execute payment for AI buyer purchase intent."""
    cart_id: int
    buyer_id: str
    idempotency_key: str


class PurchaseIntentResponse(BaseModel):
    """Response returned after purchase intent creation."""
    cart_id: int
    buyer_id: str
    idempotency_key: str
    total_paisa: int
    total_rupees: float
    items: List[Dict[str, Any]]
    status: str
