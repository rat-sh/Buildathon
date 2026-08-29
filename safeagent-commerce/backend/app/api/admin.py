"""
api/admin.py — Read-Only Admin Audit Log API
=============================================
SAFETY CONTRACT:
  - Read-Only endpoints for querying the immutable audit_events table.
  - Allows merchants, auditors, and judges to verify every decision made by agents & validator.
  - NO POST/PUT/DELETE routes exist in this router.
"""

from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.audit import AuditDecision, AuditEvent
from app.services.audit_analysis import analyze_question
from app.services.audit_service import AuditService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["admin"])


class AuditAnalyzeRequest(BaseModel):
    question: str


@router.post("/audit/analyze")
async def analyze_audit_log(req: AuditAnalyzeRequest, db: AsyncSession = Depends(get_db)):
    """Deterministic log analysis — all counts from real audit_events table."""
    return await analyze_question(db, req.question)


@router.get("/audit/events")
async def list_audit_events(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    actor: Optional[str] = Query(None, description="Filter by actor (e.g. validator_agent, payment_agent)"),
    decision: Optional[str] = Query(None, description="Filter by decision (PASS, BLOCK, INFO, ERROR)"),
    session_id: Optional[str] = Query(None, description="Filter by human session ID"),
    buyer_id: Optional[str] = Query(None, description="Filter by AI buyer ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Query immutable audit event log with filtering options.
    """
    events = await AuditService.get_events(
        db=db,
        limit=limit,
        offset=offset,
        actor=actor,
        decision=decision,
        session_id=session_id,
        buyer_id=buyer_id,
    )

    output = []
    for e in events:
        evidence_data = None
        if e.evidence_json:
            import json
            try:
                evidence_data = json.loads(e.evidence_json)
            except Exception:
                evidence_data = e.evidence_json

        output.append({
            "id": e.id,
            "actor": e.actor,
            "action": e.action,
            "decision": e.decision.value,
            "reason_code": e.reason_code,
            "session_id": e.session_id,
            "buyer_id": e.buyer_id,
            "target_type": e.target_type,
            "target_id": e.target_id,
            "evidence": evidence_data,
            "message": e.message,
            "created_at": e.created_at.isoformat(),
        })

    return {
        "count": len(output),
        "limit": limit,
        "offset": offset,
        "events": output,
    }


@router.get("/audit/summary")
async def audit_summary(db: AsyncSession = Depends(get_db)):
    """
    Get summary statistics of decisions made by the system.
    """
    # Total count
    stmt_total = select(func.count(AuditEvent.id))
    total_events = (await db.execute(stmt_total)).scalar() or 0

    # Decision counts
    stmt_pass = select(func.count(AuditEvent.id)).where(AuditEvent.decision == AuditDecision.PASS)
    pass_count = (await db.execute(stmt_pass)).scalar() or 0

    stmt_block = select(func.count(AuditEvent.id)).where(AuditEvent.decision == AuditDecision.BLOCK)
    block_count = (await db.execute(stmt_block)).scalar() or 0

    # Reason code breakdown for BLOCK events
    stmt_reasons = (
        select(AuditEvent.reason_code, func.count(AuditEvent.id))
        .where(AuditEvent.decision == AuditDecision.BLOCK)
        .group_by(AuditEvent.reason_code)
    )
    reason_results = (await db.execute(stmt_reasons)).all()
    reason_breakdown = {row[0] or "UNKNOWN": row[1] for row in reason_results}

    return {
        "total_audit_events": total_events,
        "pass_count": pass_count,
        "block_count": block_count,
        "blocks_by_reason_code": reason_breakdown,
    }
