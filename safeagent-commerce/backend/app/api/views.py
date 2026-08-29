"""
api/views.py — HTML View Router (Jinja2 Templates)
==================================================
Serves HTML views matching Figma design:
  - GET /               -> AI Shopping Assistant chat interface
  - GET /admin/audit    -> Safety Audit Log viewer interface
"""

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import generate_session_id
from app.services.audit_service import AuditService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["views"])
templates = Jinja2Templates(directory="app/templates")


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
            "razorpay_key_id": settings.RAZORPAY_KEY_ID,  # Public key only — safe in HTML
        },
    )


@router.get("/admin/audit")
async def audit_view(request: Request, db: AsyncSession = Depends(get_db)):
    """Render admin audit log viewer interface."""
    events = await AuditService.get_events(db=db, limit=100)

    # Process events evidence JSON for display
    processed_events = []
    for e in events:
        evidence_str = ""
        if e.evidence_json:
            import json
            try:
                evidence_obj = json.loads(e.evidence_json)
                evidence_str = json.dumps(evidence_obj, indent=2)
            except Exception:
                evidence_str = e.evidence_json

        processed_events.append({
            "id": e.id,
            "actor": e.actor,
            "action": e.action,
            "decision": e.decision.value,
            "reason_code": e.reason_code or "PASS",
            "session_id": e.session_id or "-",
            "buyer_id": e.buyer_id or "-",
            "target_type": e.target_type or "-",
            "target_id": e.target_id or "-",
            "evidence_json": evidence_str,
            "message": e.message or "-",
            "created_at": e.created_at.strftime("%Y-%m-%d · %H:%M:%S UTC"),
        })

    return templates.TemplateResponse(
        request=request,
        name="admin/audit.html",
        context={
            "events": processed_events,
            "active_page": "audit",
        },
    )
