"""
services/audit_service.py — Append-Only Structured Audit Trail Service
========================================================================
SAFETY CONTRACT:
  - This service is APPEND-ONLY.
  - No update_event() or delete_event() functions exist in this file or module.
  - Every money-related decision (Validator PASS/BLOCK, Razorpay order creation,
    webhook verification, payment capture/failure) MUST produce an AuditEvent.
  - Raw evidence (prices, stock, limits, evidence_json) is stored as a JSON string
    for complete auditability by merchants and judges.
"""

import json
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditDecision, AuditEvent
from app.schemas.validator import ValidationResult

logger = structlog.get_logger(__name__)


class AuditService:
    """
    Append-Only Audit Service for tracking all agent actions, validator decisions,
    and payment state changes.
    """

    @staticmethod
    async def log_event(
        db: AsyncSession,
        actor: str,
        action: str,
        decision: AuditDecision | str,
        session_id: Optional[str] = None,
        buyer_id: Optional[str] = None,
        reason_code: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        evidence: Optional[Dict[str, Any]] = None,
        message: Optional[str] = None,
    ) -> AuditEvent:
        """
        Append a single structured audit event to the DB.

        Args:
            db: Async database session
            actor: Component taking action (e.g. validator_agent, payment_agent, shopping_agent)
            action: Action string (e.g. validate_cart, create_order, webhook_received)
            decision: AuditDecision enum or string ("PASS", "BLOCK", "INFO", "ERROR")
            session_id: Optional human session ID
            buyer_id: Optional AI buyer ID
            reason_code: Optional Validator reason code (e.g. PRICE_MISMATCH)
            target_type: Entity type (cart, order, product)
            target_id: Entity ID
            evidence: Raw dictionary of evidence parameters (serialized to JSON)
            message: Human-readable explanation

        Returns:
            The created AuditEvent DB instance
        """
        # Convert string decision to AuditDecision enum if needed
        if isinstance(decision, str):
            decision = AuditDecision(decision.upper())

        evidence_json_str = None
        if evidence:
            try:
                evidence_json_str = json.dumps(evidence, default=str)
            except Exception as e:
                logger.error("Failed to serialize audit evidence to JSON", error=str(e))
                evidence_json_str = json.dumps({"raw": str(evidence)})

        event = AuditEvent(
            actor=actor,
            session_id=session_id,
            buyer_id=buyer_id,
            action=action,
            decision=decision,
            reason_code=reason_code,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            evidence_json=evidence_json_str,
            message=message,
        )

        db.add(event)
        await db.commit()
        await db.refresh(event)

        logger.info(
            "Audit event recorded",
            audit_id=event.id,
            actor=actor,
            action=action,
            decision=event.decision.value,
            reason_code=reason_code,
        )

        return event

    @staticmethod
    async def log_validation_result(
        db: AsyncSession,
        result: ValidationResult,
        session_id: Optional[str] = None,
        buyer_id: Optional[str] = None,
    ) -> AuditEvent:
        """
        Helper method specifically for logging a ValidatorAgent result.
        """
        decision = AuditDecision.PASS if result.is_valid else AuditDecision.BLOCK
        return await AuditService.log_event(
            db=db,
            actor="validator_agent",
            action="validate_cart",
            decision=decision,
            session_id=session_id,
            buyer_id=buyer_id,
            reason_code=result.reason_code,
            target_type="cart",
            target_id=str(result.cart_id),
            evidence=result.evidence,
            message=result.message,
        )

    @staticmethod
    async def get_events(
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0,
        actor: Optional[str] = None,
        decision: Optional[str] = None,
        session_id: Optional[str] = None,
        buyer_id: Optional[str] = None,
    ) -> List[AuditEvent]:
        """
        Query audit events with filtering. Read-Only access.
        """
        stmt = select(AuditEvent).order_by(desc(AuditEvent.id))

        if actor:
            stmt = stmt.where(AuditEvent.actor == actor)
        if decision:
            stmt = stmt.where(AuditEvent.decision == AuditDecision(decision.upper()))
        if session_id:
            stmt = stmt.where(AuditEvent.session_id == session_id)
        if buyer_id:
            stmt = stmt.where(AuditEvent.buyer_id == buyer_id)

        stmt = stmt.offset(offset).limit(limit)
        results = await db.execute(stmt)
        return list(results.scalars().all())
