"""
scripts/seed_db.py — Database Seed Script
===========================================
Populates the SQLite database with sample products from data/products.json.
Safe to run multiple times (idempotent).
"""

import asyncio
import json
import os
import sys

# Ensure backend folder is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal, init_db
from app.models.product import Product


async def seed():
    print("🌱 Initializing Database tables...")
    await init_db()

    seed_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "products.json"))
    if not os.path.exists(seed_file):
        print(f"❌ Seed file not found at {seed_file}")
        return

    with open(seed_file, "r") as f:
        data = json.load(f)

    products_data = data.get("products", [])
    print(f"📦 Loaded {len(products_data)} products from JSON")

    async with AsyncSessionLocal() as db:
        added_count = 0
        for p in products_data:
            stmt = select(Product).where(Product.sku == p["sku"])
            existing = (await db.execute(stmt)).scalar_one_or_none()

            if not existing:
                prod = Product(
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
                )
                db.add(prod)
                added_count += 1

        await db.commit()
        print(f"✅ Seeding complete! {added_count} new products added to DB.")


if __name__ == "__main__":
    asyncio.run(seed())
