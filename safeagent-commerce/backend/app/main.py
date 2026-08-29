"""
SafeAgent Commerce — FastAPI Application Entry Point
====================================================
Architecture contract:
  - ALL money decisions flow through Validator Agent (never bypassed)
  - Only Payment Agent is allowed to call Razorpay SDK
  - Every audit event is append-only (no update/delete)

Startup sequence:
  1. Load config & validate env vars
  2. Run DB migrations (create tables)
  3. Seed products if empty
  4. Mount routers
  5. Start server
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.database import init_db

logger = structlog.get_logger(__name__)


# ── Lifespan: runs on startup and shutdown ────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler — setup and teardown."""
    logger.info(
        "SafeAgent Commerce starting",
        env=settings.APP_ENV,
        db=settings.DATABASE_URL,
    )
    # Initialize DB tables (idempotent — safe to run every startup)
    await init_db()
    logger.info("Database initialized")
    yield
    # Teardown (nothing critical for now)
    logger.info("SafeAgent Commerce shutting down")


# ── Application Factory ───────────────────────────────────────────────────────
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="SafeAgent Commerce",
        description=(
            "Validator-gated multi-agent commerce system for Razorpay Buildathon 2026. "
            "LLMs propose. Deterministic Validator decides. Payment Agent executes."
        ),
        version="1.0.0",
        docs_url="/docs" if settings.DEBUG else None,  # Hide docs in production
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST"],  # Restricted — no PATCH/DELETE on money routes
        allow_headers=["*"],
    )

    # ── Static files ──────────────────────────────────────────────────────────
    app.mount(
        "/static",
        StaticFiles(directory="app/static"),
        name="static",
    )

    # ── API Routers (imported lazily to avoid circular imports) ───────────────
    # Routers will be registered as they are built in later phases
    _register_routers(app)

    return app


def _register_routers(app: FastAPI) -> None:
    """
    Register all API routers.
    Order matters — more specific routes before generic ones.
    """
    # Health check (always available, no auth)
    from app.api.health import router as health_router
    app.include_router(health_router)

    # Chat (human HTMX path) — Phase 5
    from app.api.chat import router as chat_router
    app.include_router(chat_router, prefix="/chat", tags=["chat"])

    # Catalog (AI buyer path) — Phase 5
    from app.api.catalog import router as catalog_router
    app.include_router(catalog_router, prefix="/catalog", tags=["catalog"])

    # Webhooks (Razorpay) — Phase 3
    from app.api.webhooks import router as webhooks_router
    app.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])

    # Admin audit log — Phase 5
    # from app.api.admin import router as admin_router
    # app.include_router(admin_router, prefix="/admin", tags=["admin"])


# ── Application instance ──────────────────────────────────────────────────────
app = create_app()
