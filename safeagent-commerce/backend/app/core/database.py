"""
database.py — SQLAlchemy 2.0 async engine + session factory
============================================================
Design decisions:
  - Async engine (aiosqlite for dev, asyncpg for prod)
  - Session factory via async_sessionmaker
  - init_db() is idempotent — safe to call on every startup
  - No auto-commit: every DB write is explicit (ACID control)
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


# ── Base class for all SQLAlchemy models ──────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Async engine ──────────────────────────────────────────────────────────────
# echo=True in dev for SQL logging; False in prod
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    # SQLite-specific: check_same_thread must be False for async
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

# ── Session factory ───────────────────────────────────────────────────────────
# expire_on_commit=False — prevents accessing attributes after commit in async
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db() -> None:
    """
    Create all tables if they don't exist.
    Import models here so they register with Base.metadata before create_all.
    This is idempotent — safe to call on every startup.
    """
    # Import all models to register them with Base
    # These imports MUST happen before create_all
    from app.models import audit, cart, order, product  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """
    FastAPI dependency — yields an async DB session.
    Automatically rolls back on exception and closes session.

    Usage:
        @router.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
