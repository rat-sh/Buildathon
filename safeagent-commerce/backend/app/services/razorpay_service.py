"""
services/razorpay_service.py — Razorpay SDK Wrapper
====================================================
Wraps official razorpay Python SDK (Test Mode).

Safety Contracts:
  - Interfaces with Razorpay Orders API for creating orders.
  - Passes idempotency key in receipt / notes payload.
  - Handles SDK exceptions cleanly.
  - Supports simulated fallback if using dummy test keys (e.g. unit tests or local dev).
"""

from typing import Any, Dict, Optional

import razorpay
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class RazorpayService:
    """
    Service wrapper around Razorpay Python SDK.
    Used by Payment Agent and Webhooks.
    """

    def __init__(self):
        self.key_id = settings.RAZORPAY_KEY_ID
        self.key_secret = settings.RAZORPAY_KEY_SECRET
        self.webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET

        # Initialize official client if real test keys are configured
        self._is_placeholder = (
            "REPLACE_ME" in self.key_id.upper()
            or "REPLACE_ME" in self.key_secret.upper()
            or self.key_id.startswith("rzp_test_placeholder")
            or not self.key_secret
            or self.key_secret == "placeholder_secret"
        )

        if not self._is_placeholder:
            self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
        else:
            self.client = None
            logger.info("RazorpayService initialized in SIMULATED mode (placeholder keys detected)")

    def create_order(
        self,
        amount_paisa: int,
        idempotency_key: str,
        currency: str = "INR",
        notes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create an order in Razorpay using official Orders API.

        Args:
            amount_paisa: Order total in paisa (integer)
            idempotency_key: Unique idempotency key (used as receipt)
            currency: Currency code (default INR)
            notes: Additional metadata dictionary

        Returns:
            Dictionary response containing razorpay order details
            {"id": "order_...", "amount": 1000, "status": "created", ...}
        """
        notes_payload = notes or {}
        notes_payload["idempotency_key"] = idempotency_key

        payload = {
            "amount": amount_paisa,
            "currency": currency,
            "receipt": idempotency_key[:40],  # Razorpay receipt max len is 40 chars
            "notes": notes_payload,
        }

        if self._is_placeholder or self.client is None:
            # Simulated Razorpay response for offline testing or placeholder key usage
            simulated_order_id = f"order_sim_{idempotency_key[:16]}"
            logger.info(
                "Simulated Razorpay Order created",
                order_id=simulated_order_id,
                amount_paisa=amount_paisa,
            )
            return {
                "id": simulated_order_id,
                "entity": "order",
                "amount": amount_paisa,
                "amount_paid": 0,
                "amount_due": amount_paisa,
                "currency": currency,
                "receipt": payload["receipt"],
                "status": "created",
                "attempts": 0,
                "notes": notes_payload,
                "created_at": 1722345678,
            }

        try:
            logger.info("Calling Razorpay Orders API", amount_paisa=amount_paisa, receipt=payload["receipt"])
            response = self.client.order.create(data=payload)
            logger.info("Razorpay Order created successfully", razorpay_order_id=response.get("id"))
            return response
        except (
            razorpay.errors.BadRequestError,
            razorpay.errors.GatewayError,
            razorpay.errors.ServerError,
            razorpay.errors.SignatureVerificationError,
        ) as e:
            logger.error("Razorpay SDK Error during order creation", error=str(e))
            raise RuntimeError(f"Razorpay Order creation failed: {str(e)}") from e
        except Exception as e:
            logger.error("Unexpected error during Razorpay order creation", error=str(e))
            raise RuntimeError(f"Unexpected payment error: {str(e)}") from e

    def fetch_order(self, razorpay_order_id: str) -> Dict[str, Any]:
        """Fetch order status from Razorpay."""
        if self._is_placeholder or self.client is None:
            return {
                "id": razorpay_order_id,
                "entity": "order",
                "amount": 10000,
                "status": "paid" if "paid" in razorpay_order_id else "created",
            }
        try:
            return self.client.order.fetch(razorpay_order_id)
        except Exception as e:
            logger.error("Failed to fetch Razorpay order", order_id=razorpay_order_id, error=str(e))
            raise

    def fetch_payment(self, razorpay_payment_id: str) -> Dict[str, Any]:
        """Fetch payment details from Razorpay."""
        if self._is_placeholder or self.client is None:
            return {
                "id": razorpay_payment_id,
                "entity": "payment",
                "amount": 10000,
                "status": "captured",
            }
        try:
            return self.client.payment.fetch(razorpay_payment_id)
        except Exception as e:
            logger.error("Failed to fetch Razorpay payment", payment_id=razorpay_payment_id, error=str(e))
            raise
