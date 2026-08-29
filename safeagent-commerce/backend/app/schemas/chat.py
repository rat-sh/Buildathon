"""
schemas/chat.py — Pydantic schemas for Human Chat API
======================================================
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    """Incoming user chat message."""
    message: str = Field(description="User natural language text")
    session_id: Optional[str] = Field(default=None, description="Human session ID")
    cart_id: Optional[int] = Field(default=None, description="Active cart ID if exists")


class AddToCartRequest(BaseModel):
    """Add product to cart."""
    product_id: int
    quantity: int = 1
    session_id: Optional[str] = None
    cart_id: Optional[int] = None


class AcceptAddonRequest(BaseModel):
    """Explicitly accept a suggested add-on item."""
    cart_id: int
    item_id: int
    session_id: Optional[str] = None


class CheckoutRequest(BaseModel):
    """Initiate checkout on cart."""
    cart_id: int
    session_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class ChatMessageResponse(BaseModel):
    """Structured response for chat interaction."""
    reply: str
    session_id: str
    cart_id: Optional[int] = None
    products: List[Dict[str, Any]] = Field(default_factory=list)
    suggestions: List[Dict[str, Any]] = Field(default_factory=list)
    cart_summary: Optional[Dict[str, Any]] = None
    checkout_data: Optional[Dict[str, Any]] = None
    is_blocked: bool = False
    block_reason_code: Optional[str] = None
