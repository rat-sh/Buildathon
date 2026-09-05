"""
api/views.py — HTML View Router (Jinja2 Templates)
"""

import json

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import generate_session_id
from app.services.audit_analysis import get_summary_stats, get_threat_alerts
from app.services.audit_service import AuditService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["views"])
templates = Jinja2Templates(directory="app/templates")


def _format_reason_code(decision: str, reason_code: str | None) -> str:
    if reason_code:
        return reason_code
    if decision == "INFO":
        return "—"
    if decision == "ERROR":
        return "ERROR"
    return decision


@router.get("/")
async def chat_view(request: Request):
    """Render customer AI Shopping Assistant chat interface."""
    from app.core.config import settings
    session_id = generate_session_id()
    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "session_id": session_id,
            "active_page": "shopping",
            "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        },
    )


@router.get("/admin/audit")
async def audit_view(request: Request, is_mock: bool = False, db: AsyncSession = Depends(get_db)):
    """Render ops-console audit log viewer. Defaults to live real events (is_mock=False)."""
    from app.core.config import settings
    events = await AuditService.get_events(db=db, limit=200, is_mock=is_mock)
    stats = await get_summary_stats(db)
    alerts = await get_threat_alerts(db)

    processed_events = []
    for e in events:
        evidence_str = ""
        if e.evidence_json:
            try:
                evidence_str = json.dumps(json.loads(e.evidence_json), indent=2)
            except Exception:
                evidence_str = e.evidence_json

        decision = e.decision.value
        processed_events.append({
            "id": e.id,
            "actor": e.actor,
            "action": e.action,
            "decision": decision,
            "reason_code": _format_reason_code(decision, e.reason_code),
            "session_id": e.session_id or "—",
            "buyer_id": e.buyer_id or "—",
            "target_type": e.target_type or "—",
            "target_id": e.target_id or "—",
            "target": f"{e.target_type or '—'}:{e.target_id or '—'}",
            "session_buyer": e.buyer_id or e.session_id or "—",
            "evidence_json": evidence_str,
            "message": e.message or "—",
            "is_mock": getattr(e, "is_mock", False),
            "threat_level": getattr(e, "threat_level", "LOW"),
            "created_at": e.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        })

    return templates.TemplateResponse(
        request=request,
        name="admin/audit.html",
        context={
            "events": processed_events,
            "stats": stats,
            "alerts": alerts,
            "active_page": "audit",
            "is_mock": is_mock,
            "admin_api_key": settings.ADMIN_API_KEY,
        },
    )
