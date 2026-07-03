"""
Firebase / Firestore integration.
Handles connection setup and all reads/writes to the message_logs collection.
"""

import firebase_admin
from firebase_admin import credentials, firestore

from app.core.config import FIREBASE_CERT, LOGS_COLLECTION
from app.core.logging import logger

try:
    cred = credentials.Certificate(FIREBASE_CERT)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    logger.info("Firebase connected successfully!")
except Exception as e:
    logger.error(f"Firebase initialization failed: {e}")
    raise


def write_log_to_firestore(entry: dict) -> None:
    """Saves a message log entry to Firestore."""
    try:
        db.collection(LOGS_COLLECTION).add(entry)
        logger.info(f"Log saved to Firestore: {entry['receiver_id']} - {entry['status']}")
    except Exception as e:
        logger.error(f"Failed to write log to Firestore: {e}")


def read_logs_from_firestore(limit: int = 100) -> list:
    """Reads the most recent message logs from Firestore, newest first."""
    try:
        docs = (
            db.collection(LOGS_COLLECTION)
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
    except Exception as e:
        logger.error(f"Failed to read logs from Firestore: {e}")
        return []


def clear_logs_from_firestore() -> None:
    """Deletes all documents in the message_logs collection."""
    try:
        docs = db.collection(LOGS_COLLECTION).stream()
        for doc in docs:
            doc.reference.delete()
        logger.info("All logs cleared from Firestore")
    except Exception as e:
        logger.error(f"Failed to clear logs from Firestore: {e}")
