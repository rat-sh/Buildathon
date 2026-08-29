"""tests/test_audit_analysis.py — Deterministic audit log analysis queries"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.database import Base
from app.models.audit import AuditDecision, AuditEvent
from app.services.audit_analysis import analyze_question, get_summary_stats


@pytest_asyncio.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        session.add_all([
            AuditEvent(actor="validator_agent", action="validate_cart", decision=AuditDecision.BLOCK,
                       reason_code="TX_LIMIT_EXCEEDED", message="Blocked"),
            AuditEvent(actor="webhook_handler", action="webhook_received", decision=AuditDecision.BLOCK,
                       reason_code="INVALID_HMAC_SIGNATURE", message="HMAC fail"),
            AuditEvent(actor="api", action="verify_payment", decision=AuditDecision.PASS,
                       reason_code=None, message="Payment captured"),
            AuditEvent(actor="human", action="chat_message", decision=AuditDecision.INFO,
                       message="Hello"),
        ])
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_summary_stats(test_db: AsyncSession):
    stats = await get_summary_stats(test_db)
    assert stats["total"] == 4
    assert stats["pass"] == 1
    assert stats["block"] == 2
    assert stats["info"] == 1


@pytest.mark.asyncio
async def test_blocked_count(test_db: AsyncSession):
    result = await analyze_question(test_db, "How many blocked?")
    assert result["query_type"] == "blocked_count"
    assert "2" in result["answer"]


@pytest.mark.asyncio
async def test_reason_code_count(test_db: AsyncSession):
    result = await analyze_question(test_db, "How many TX_LIMIT_EXCEEDED?")
    assert result["query_type"] == "reason_code_count"
    assert "1" in result["answer"]


@pytest.mark.asyncio
async def test_threat_summary(test_db: AsyncSession):
    result = await analyze_question(test_db, "Show threat summary")
    assert result["query_type"] == "threat_summary"
    assert "Blocks today" in result["answer"]
