"""
database.py — SQLAlchemy 2.0 async engine + session factory
============================================================
Design decisions:
  - Async engine (aiosqlite for dev, asyncpg for prod)
  - Session factory via async_sessionmaker
  - init_db() is idempotent — safe to call on every startup
  - Auto-seeds catalog products from data/products.json if DB is empty
"""

import json
import os
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Create tables if needed and seed catalog products if empty."""
    from app.models import audit, cart, order, product  # noqa: F401
    from app.models.product import Product

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed products if empty
    async with AsyncSessionLocal() as db:
        count = (await db.execute(select(func.count(Product.id)))).scalar() or 0
        if count == 0:
            seed_file = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "products.json")
            )
            if os.path.exists(seed_file):
                with open(seed_file, "r") as f:
                    data = json.load(f)
                for p in data.get("products", []):
                    db.add(Product(
                        name=p["name"],
                        description=p.get("description"),
                        category=p["category"],
                        brand=p.get("brand"),
                        sku=p["sku"],
                        price_paisa=p["price_paisa"],
                        currency=p.get("currency", "INR"),
                        stock_quantity=p.get("stock_quantity", 10),
                        is_active=p.get("is_active", True),
                        attributes_json=p.get("attributes_json"),
                        affinity_product_ids=p.get("affinity_product_ids"),
                    ))
                await db.commit()
                logger.info("Auto-seeded catalog products into empty DB")


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
