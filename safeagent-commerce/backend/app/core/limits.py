"""
core/limits.py — Hard spending limits (CODE CONSTANTS, not DB values)
======================================================================
CRITICAL SAFETY DESIGN:
  These limits are hard-coded Python constants — NOT stored in the database
  and NOT configurable via API.

  Why constants and not DB values?
  - An LLM agent cannot hallucinate or manipulate a Python constant
  - A DB value could theoretically be modified by a rogue write
  - A code constant requires a code review + deployment to change
  - This is the safest possible boundary for spending controls

  To change limits for production:
    1. Edit this file
    2. Code review
    3. Deploy
  Never expose a PUT /limits endpoint.

All monetary values are in PAISA (100 paisa = ₹1).
"""

# ── Per-Transaction Limit ─────────────────────────────────────────────────────
# Maximum amount allowed in a single cart/transaction.
# Validator check: cart_total_paisa <= PER_TX_LIMIT_PAISA
#
# ₹5,000 = 500,000 paisa
PER_TX_LIMIT_PAISA: int = 500_000  # ₹5,000

# ── Daily Spending Ceiling ────────────────────────────────────────────────────
# Maximum cumulative spending allowed per session/buyer per calendar day.
# Validator check: daily_spent_paisa + cart_total_paisa <= DAILY_CEILING_PAISA
#
# Applies to BOTH human sessions and AI buyers.
# AI buyers have an additional mandate-based check.
#
# ₹10,000 = 1,000,000 paisa
DAILY_CEILING_PAISA: int = 1_000_000  # ₹10,000

# ── Payment Retry Limit ───────────────────────────────────────────────────────
# Maximum number of payment attempts allowed per order.
# Payment Agent hard-stops after this many failures.
# Validator does NOT need to check this — Payment Agent enforces it directly.
MAX_PAYMENT_RETRIES: int = 2

# ── AI Buyer Specific Limits ──────────────────────────────────────────────────
# AI buyers have tighter limits by default.
# These apply only when buyer_id is set (AI path).
#
# ₹2,000 = 200,000 paisa
AI_BUYER_PER_TX_LIMIT_PAISA: int = 200_000  # ₹2,000

# ₹5,000 = 500,000 paisa
AI_BUYER_DAILY_CEILING_PAISA: int = 500_000  # ₹5,000

# ── Cart Configuration ────────────────────────────────────────────────────────
# Maximum number of distinct items allowed in a single cart
MAX_CART_ITEMS: int = 10

# Maximum quantity of a single product in one cart
MAX_SINGLE_ITEM_QUANTITY: int = 5

# ── Suggestion Limits ─────────────────────────────────────────────────────────
# Suggestion Agent may suggest at most this many items per session
MAX_SUGGESTIONS_PER_SESSION: int = 2

# ── Human-readable helpers ────────────────────────────────────────────────────
def paisa_to_rupees(paisa: int) -> float:
    """Convert paisa to rupees. For display ONLY — never use in calculations."""
    return paisa / 100


def rupees_to_paisa(rupees: float) -> int:
    """Convert rupees to paisa. Use this when accepting user input."""
    return int(rupees * 100)


def get_limits_for_buyer(is_ai_buyer: bool) -> dict:
    """
    Return the applicable limits for a given buyer type.
    Used by Validator Agent to select the correct limit set.
    """
    if is_ai_buyer:
        return {
            "per_tx_limit_paisa": AI_BUYER_PER_TX_LIMIT_PAISA,
            "daily_ceiling_paisa": AI_BUYER_DAILY_CEILING_PAISA,
            "buyer_type": "ai",
        }
    return {
        "per_tx_limit_paisa": PER_TX_LIMIT_PAISA,
        "daily_ceiling_paisa": DAILY_CEILING_PAISA,
        "buyer_type": "human",
    }
