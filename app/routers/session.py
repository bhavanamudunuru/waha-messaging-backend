"""
Root health check and WAHA session status endpoints.
"""

from fastapi import APIRouter

from app.services.waha_client import get_session_status

router = APIRouter(tags=["session"])


@router.get("/")
def root():
    return {"status": "ok", "service": "WhatsApp Messaging Service API"}


@router.get("/api/session-status")
async def session_status():
    """Check if the WAHA WhatsApp session is connected."""
    return await get_session_status()
