"""
api/__init__.py — API Routers exports
"""

from app.api.admin import router as admin_router
from app.api.catalog import router as catalog_router
from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.views import router as views_router
from app.api.webhooks import router as webhooks_router

__all__ = [
    "health_router",
    "webhooks_router",
    "chat_router",
    "catalog_router",
    "admin_router",
    "views_router",
]
