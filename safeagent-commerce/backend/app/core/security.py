"""
core/security.py — Idempotency + Webhook HMAC verification helpers
===================================================================
Two critical safety functions:

1. generate_idempotency_key()
   Creates a unique key for each payment attempt.
   The Validator checks this key is not already in the orders table.
   Prevents double-charges from retries, network duplicates, etc.

2. verify_razorpay_webhook_signature()
   HMAC-SHA256 verification of incoming Razorpay webhooks.
   This MUST be called FIRST in the webhook handler, before any
   order state is updated. If signature fails → reject and log.
   Never update order state on an unverified webhook.

3. verify_razorpay_payment_signature()
   Verifies the payment signature returned after checkout completion.
   Used to confirm a payment is authentic before marking captured.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timezone


def generate_idempotency_key(prefix: str = "pay") -> str:
    """
    Generate a cryptographically unique idempotency key.

    Format: {prefix}_{timestamp_ms}_{random_hex}
    Example: pay_1722345678901_a3f8b2c1d4e5f6a7

    The Validator checks this key against the orders table before
    allowing any payment. If it already exists → DUPLICATE_IDEMPOTENCY_KEY.

    Args:
        prefix: Short identifier for the payment source (default: "pay")

    Returns:
        A unique idempotency key string (safe for DB storage and Razorpay API)
    """
    timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    random_part = secrets.token_hex(16)  # 32 hex chars = 128 bits of entropy
    return f"{prefix}_{timestamp_ms}_{random_part}"


def verify_razorpay_webhook_signature(
    payload_body: bytes,
    razorpay_signature: str,
    webhook_secret: str,
) -> bool:
    """
    Verify a Razorpay webhook payload using HMAC-SHA256.

    SAFETY CONTRACT:
      This function MUST be called before ANY order state change in
      the webhook handler. If it returns False, the handler must:
        1. Return HTTP 400
        2. Log an AUDIT event with decision=BLOCK, action=webhook_rejected
        3. NOT update any order state

    How Razorpay signs webhooks:
      signature = HMAC_SHA256(webhook_secret, raw_body_bytes)
      Razorpay sends this in the X-Razorpay-Signature header.

    Args:
        payload_body: Raw request body bytes (do NOT parse JSON first)
        razorpay_signature: Value of X-Razorpay-Signature header
        webhook_secret: Your Razorpay webhook secret from dashboard

    Returns:
        True if signature is valid, False otherwise (BLOCK on False)
    """
    if not payload_body or not razorpay_signature or not webhook_secret:
        # Missing any component → reject (fail closed)
        return False

    expected_signature = hmac.new(
        key=webhook_secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Constant-time comparison — prevents timing attacks
    return hmac.compare_digest(expected_signature, razorpay_signature)


def verify_razorpay_payment_signature(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
    key_secret: str,
) -> bool:
    """
    Verify the payment signature returned by Razorpay after checkout.

    Razorpay's signing formula for payment verification:
      signature = HMAC_SHA256(key_secret, f"{order_id}|{payment_id}")

    SAFETY CONTRACT:
      This MUST be verified before marking an order as CAPTURED.
      If verification fails, the order stays in AUTHORIZED state and
      a BLOCK audit event is logged.

    Args:
        razorpay_order_id: The Razorpay order ID (order_*)
        razorpay_payment_id: The Razorpay payment ID (pay_*)
        razorpay_signature: The signature to verify
        key_secret: Your Razorpay key secret

    Returns:
        True if signature is valid, False otherwise
    """
    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, key_secret]):
        return False

    payload = f"{razorpay_order_id}|{razorpay_payment_id}"
    expected_signature = hmac.new(
        key=key_secret.encode("utf-8"),
        msg=payload.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_signature, razorpay_signature)


def generate_session_id() -> str:
    """
    Generate a unique session ID for human shoppers.
    Used to track cart, daily spend, and audit events per session.
    """
    return f"sess_{secrets.token_urlsafe(24)}"


def verify_ai_buyer_api_key(provided_key: str, expected_key: str) -> bool:
    """
    Verify an AI buyer's API key using constant-time comparison.
    Prevents timing attacks on API key verification.
    """
    if not provided_key or not expected_key:
        return False
    return hmac.compare_digest(provided_key, expected_key)
