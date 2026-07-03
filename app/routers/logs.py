"""
Endpoints for reading and clearing message logs.
"""

from fastapi import APIRouter

from app.services.firestore_service import read_logs_from_firestore, clear_logs_from_firestore

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
def get_logs(limit: int = 100):
    """Fetch the most recent message logs from Firestore."""
    logs = read_logs_from_firestore(limit)
    return {"count": len(logs), "logs": logs}


@router.delete("")
def clear_logs():
    """Delete all message logs from Firestore."""
    clear_logs_from_firestore()
    return {"success": True, "message": "All logs cleared from Firestore"}
