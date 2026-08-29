"""
services/audit_analysis.py — Deterministic audit log analysis (no invented numbers)
====================================================================================
Maps operator questions to safe SQL aggregations over audit_events.
Never uses LLM for counts. All answers come from real DB queries.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditDecision, AuditEvent

PURCHASE_ACTIONS = ("verify_payment", "payment_captured", "create_order")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _start_of_today_utc() -> datetime:
    now = _utc_now()
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc)


async def get_summary_stats(db: AsyncSession) -> dict[str, int]:
    """Live counts for ops header strip."""
    total = (await db.execute(select(func.count(AuditEvent.id)))).scalar() or 0
    pass_c = (await db.execute(
        select(func.count(AuditEvent.id)).where(AuditEvent.decision == AuditDecision.PASS)
    )).scalar() or 0
    block_c = (await db.execute(
        select(func.count(AuditEvent.id)).where(AuditEvent.decision == AuditDecision.BLOCK)
    )).scalar() or 0
    info_c = (await db.execute(
        select(func.count(AuditEvent.id)).where(AuditEvent.decision == AuditDecision.INFO)
    )).scalar() or 0
    return {"total": total, "pass": pass_c, "block": block_c, "info": info_c}


async def get_threat_alerts(db: AsyncSession) -> list[dict[str, str]]:
    """High-severity patterns for alert banner."""
    alerts: list[dict[str, str]] = []
    since_hour = _utc_now() - timedelta(hours=1)

    hmac_count = (await db.execute(
        select(func.count(AuditEvent.id)).where(
            AuditEvent.reason_code == "INVALID_HMAC_SIGNATURE",
            AuditEvent.created_at >= since_hour,
        )
    )).scalar() or 0

    if hmac_count >= 3:
        alerts.append({
            "level": "critical",
            "message": f"ALERT: {hmac_count} INVALID_HMAC_SIGNATURE events in the last hour — possible webhook attack.",
        })
    elif hmac_count >= 1:
        alerts.append({
            "level": "warning",
            "message": f"WARNING: {hmac_count} INVALID_HMAC_SIGNATURE rejection(s) in the last hour.",
        })

    block_hour = (await db.execute(
        select(func.count(AuditEvent.id)).where(
            AuditEvent.decision == AuditDecision.BLOCK,
            AuditEvent.created_at >= since_hour,
        )
    )).scalar() or 0

    if block_hour >= 10:
        alerts.append({
            "level": "warning",
            "message": f"Elevated block rate: {block_hour} BLOCK events in the last hour.",
        })

    return alerts


async def analyze_question(db: AsyncSession, question: str) -> dict[str, Any]:
    """Answer operator questions using deterministic SQL only."""
    q = question.strip().lower()
    if not q:
        return _help_response()

    today_start = _start_of_today_utc()
    since_hour = _utc_now() - timedelta(hours=1)

    # ── Threat summary ────────────────────────────────────────────────────────
    if "threat" in q and "summary" in q:
        blocks_today = (await db.execute(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.decision == AuditDecision.BLOCK,
                AuditEvent.created_at >= today_start,
            )
        )).scalar() or 0

        reason_rows = (await db.execute(
            select(AuditEvent.reason_code, func.count(AuditEvent.id))
            .where(AuditEvent.decision == AuditDecision.BLOCK, AuditEvent.created_at >= today_start)
            .group_by(AuditEvent.reason_code)
            .order_by(func.count(AuditEvent.id).desc())
            .limit(8)
        )).all()

        hmac_hour = (await db.execute(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.reason_code == "INVALID_HMAC_SIGNATURE",
                AuditEvent.created_at >= since_hour,
            )
        )).scalar() or 0

        breakdown = {row[0] or "UNKNOWN": row[1] for row in reason_rows}
        lines = [f"Blocks today: {blocks_today}", f"HMAC failures (1h): {hmac_hour}"]
        if breakdown:
            lines.append("Top block reasons today: " + ", ".join(f"{k}={v}" for k, v in breakdown.items()))

        return {
            "answer": "\n".join(lines),
            "data": {"blocks_today": blocks_today, "hmac_last_hour": hmac_hour, "breakdown": breakdown},
            "query_type": "threat_summary",
        }

    # ── Purchases today ───────────────────────────────────────────────────────
    if re.search(r"how many purchases|purchases today|payments captured", q):
        count = (await db.execute(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.decision == AuditDecision.PASS,
                AuditEvent.action.in_(PURCHASE_ACTIONS),
                AuditEvent.created_at >= today_start,
            )
        )).scalar() or 0
        return {
            "answer": f"{count} successful purchase/payment event(s) today (UTC).",
            "data": {"count": count, "window": "today_utc"},
            "query_type": "purchases_today",
        }

    # ── Blocked count ─────────────────────────────────────────────────────────
    if re.search(r"how many blocked|blocked today|block count", q):
        window = today_start if "today" in q else None
        stmt = select(func.count(AuditEvent.id)).where(AuditEvent.decision == AuditDecision.BLOCK)
        if window:
            stmt = stmt.where(AuditEvent.created_at >= window)
        count = (await db.execute(stmt)).scalar() or 0
        label = "today (UTC)" if window else "all time"
        return {
            "answer": f"{count} BLOCK event(s) {label}.",
            "data": {"count": count},
            "query_type": "blocked_count",
        }

    # ── Specific reason code ──────────────────────────────────────────────────
    reason_match = re.search(
        r"(tx_limit_exceeded|invalid_hmac_signature|price_mismatch|stock_out|"
        r"addon_not_accepted|duplicate_idempotency_key|cart_already_paid|daily_limit_exceeded)",
        q,
    )
    if reason_match or re.search(r"how many.*reason", q):
        code = reason_match.group(1).upper() if reason_match else None
        if not code:
            for token in q.upper().split():
                if token.endswith("_EXCEEDED") or token.startswith("INVALID_"):
                    code = token
                    break
        if code:
            count = (await db.execute(
                select(func.count(AuditEvent.id)).where(AuditEvent.reason_code == code)
            )).scalar() or 0
            return {
                "answer": f"{count} event(s) with reason code {code}.",
                "data": {"reason_code": code, "count": count},
                "query_type": "reason_code_count",
            }

    # ── HMAC last hour ────────────────────────────────────────────────────────
    if re.search(r"invalid_hmac|hmac.*last hour|hmac signature", q):
        count = (await db.execute(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.reason_code == "INVALID_HMAC_SIGNATURE",
                AuditEvent.created_at >= since_hour,
            )
        )).scalar() or 0
        return {
            "answer": f"{count} INVALID_HMAC_SIGNATURE event(s) in the last hour.",
            "data": {"count": count, "reason_code": "INVALID_HMAC_SIGNATURE"},
            "query_type": "hmac_last_hour",
        }

    # ── Events by actor ───────────────────────────────────────────────────────
    actor_match = re.search(
        r"(validator_agent|payment_agent|webhook_handler|human|ai_buyer|api|shopping_agent)",
        q,
    )
    if actor_match or re.search(r"events by actor|how many.*validator", q):
        actor = actor_match.group(1) if actor_match else "validator_agent"
        count = (await db.execute(
            select(func.count(AuditEvent.id)).where(AuditEvent.actor == actor)
        )).scalar() or 0
        return {
            "answer": f"{count} event(s) from actor '{actor}'.",
            "data": {"actor": actor, "count": count},
            "query_type": "actor_count",
        }

    # ── PASS / INFO totals ────────────────────────────────────────────────────
    if "how many pass" in q or "approved" in q:
        count = (await db.execute(
            select(func.count(AuditEvent.id)).where(AuditEvent.decision == AuditDecision.PASS)
        )).scalar() or 0
        return {"answer": f"{count} PASS event(s) total.", "data": {"count": count}, "query_type": "pass_count"}

    if "how many info" in q:
        count = (await db.execute(
            select(func.count(AuditEvent.id)).where(AuditEvent.decision == AuditDecision.INFO)
        )).scalar() or 0
        return {"answer": f"{count} INFO event(s) total.", "data": {"count": count}, "query_type": "info_count"}

    return _help_response()


def _help_response() -> dict[str, Any]:
    return {
        "answer": (
            "Supported queries (real DB counts only):\n"
            "• How many purchases today?\n"
            "• How many blocked?\n"
            "• How many TX_LIMIT_EXCEEDED?\n"
            "• Any INVALID_HMAC_SIGNATURE in last hour?\n"
            "• Show threat summary\n"
            "• How many events by actor validator_agent?"
        ),
        "data": {},
        "query_type": "help",
    }
