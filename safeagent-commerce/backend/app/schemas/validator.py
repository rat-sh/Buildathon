"""
schemas/validator.py — Pydantic schemas for Validator Agent requests and results
===================================================================================
Safety contract:
  - ValidatorPassToken is generated ONLY when decision is PASS.
  - Payment Agent requires a valid ValidatorPassToken before creating any Razorpay order.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ValidationRequest(BaseModel):
    """Input parameters for validating a cart before payment execution."""
    cart_id: int
    idempotency_key: str
    session_id: Optional[str] = None
    buyer_id: Optional[str] = None
    is_ai_buyer: bool = False


class ValidatorPassToken(BaseModel):
    """
    Cryptographic / structured token representing a successful validation PASS.
    Passed to Payment Agent as proof of validation.
    """
    cart_id: int
    idempotency_key: str
    total_paisa: int
    session_id: Optional[str] = None
    buyer_id: Optional[str] = None
    is_ai_buyer: bool = False
    issued_at_timestamp: float


class ValidationResult(BaseModel):
    """
    Complete result returned by the Validator Agent.
    """
    is_valid: bool = Field(description="True if all checks passed, False otherwise")
    decision: str = Field(description="PASS or BLOCK")
    reason_code: str = Field(
        description="Reason code: PASS, ITEM_NOT_FOUND, ITEM_INACTIVE, PRICE_MISMATCH, STOCK_OUT, TX_LIMIT_EXCEEDED, DAILY_LIMIT_EXCEEDED, ADDON_NOT_ACCEPTED, DUPLICATE_IDEMPOTENCY_KEY, CART_ALREADY_PAID"
    )
    cart_id: int
    idempotency_key: str
    total_paisa: int
    evidence: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw snapshot data used for decision audit trail"
    )
    pass_token: Optional[ValidatorPassToken] = Field(
        default=None,
        description="Populated ONLY on PASS"
    )
    message: str = Field(description="Human readable summary of validation result")
