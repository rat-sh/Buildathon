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


# NOTE: GET / is handled by views.py (serves the chat HTML UI)
# This JSON response has been removed to allow the HTML page to load.
