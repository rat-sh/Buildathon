"""
Health check router — always available, no auth required.
Used by Docker healthcheck and load balancers.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Lightweight liveness probe."""
    return {"status": "ok", "service": "safeagent-commerce"}


@router.get("/")
async def root():
    """Root redirect — points to chat UI or docs."""
    return {
        "service": "SafeAgent Commerce",
        "version": "1.0.0",
        "docs": "/docs",
        "chat": "/chat",
        "audit": "/admin/audit",
    }
