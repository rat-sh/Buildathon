"""
models/audit.py — Immutable structured audit event log
=======================================================
Design contracts:
  - APPEND ONLY. No UPDATE or DELETE on this table, ever.
  - Every money-touching decision (pass or fail) must produce an event.
  - Events have structured fields so judges/merchants can query:
      "Show me all Validator decisions" → filter by actor + action
      "Show me all AI buyer transactions" → filter by buyer_id
      "Show me all blocked payments" → filter by decision=BLOCK
  - evidence_json stores the raw data the decision was based on
    (cart state, prices, limits at the moment of decision)

Actors:
  - shopping_agent, suggestion_agent, catalog_agent
  - validator_agent (most important — always logs PASS or BLOCK)
  - payment_agent
  - webhook_handler
  - system (startup, seed events)
  - human / ai_buyer (external actors)

Actions:
  - search_products, add_to_cart, suggest_item, accept_suggestion
  - validate_cart (result: PASS or BLOCK + reason_code)
  - create_order, payment_captured, payment_failed
  - webhook_received, webhook_verified, webhook_rejected
"""

from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditDecision(str, PyEnum):
    """
    High-level outcome of the event.
    PASS = allowed / succeeded
    BLOCK = rejected before money moved
    INFO = informational (no money decision)
    ERROR = system error
    """
    PASS = "PASS"
    BLOCK = "BLOCK"
    INFO = "INFO"
    ERROR = "ERROR"


class AuditEvent(Base):
    """
    A single immutable audit event.

    SAFETY RULE: This table has NO update or delete route.
    The audit_service.py only exposes an `append_event()` function.
    There is no `update_event()` or `delete_event()` function.

    Fields:
      actor        — who/what took the action (e.g. validator_agent, human)
      session_id   — human session or AI buyer ID (for filtering)
      action       — what happened (e.g. validate_cart, create_order)
      decision     — PASS / BLOCK / INFO / ERROR
      reason_code  — Validator reason code (e.g. PRICE_MISMATCH) or None
      target_type  — what the action was on (cart, order, product)
      target_id    — ID of the target entity
      evidence_json— raw JSON snapshot of the data at decision time
                     (prices, limits, quantities) — for auditability
      message      — human-readable summary of what happened
    """

    __tablename__ = "audit_events"

    # ── Primary key — auto-incrementing, never reassigned ─────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Who acted ────────────────────────────────────────────────────────────
    actor: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # ── Session context ───────────────────────────────────────────────────────
    session_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True
    )
    buyer_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True
    )

    # ── What happened ─────────────────────────────────────────────────────────
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    decision: Mapped[AuditDecision] = mapped_column(
        Enum(AuditDecision), nullable=False, index=True
    )

    # ── Validator reason code — populated for validate_cart events ────────────
    # Matches the exact reason codes: PASS, PRICE_MISMATCH, STOCK_OUT, etc.
    reason_code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )

    # ── Target entity ─────────────────────────────────────────────────────────
    target_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ── Evidence — JSON snapshot of state at decision time ────────────────────
    # This is the raw data the decision was based on.
    # Store as TEXT (JSON string) for SQLite compatibility.
    evidence_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Human-readable message ────────────────────────────────────────────────
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── SOC Security Metadata & Mock Separation ──────────────────────────────
    is_mock: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    threat_level: Mapped[str] = mapped_column(
        String(20), default="LOW", nullable=False, index=True
    )

    # ── Immutable timestamp ───────────────────────────────────────────────────
    # No updated_at — this record must never change after insertion
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<AuditEvent id={self.id} actor={self.actor} "
            f"action={self.action} decision={self.decision} "
            f"reason={self.reason_code}>"
        )
