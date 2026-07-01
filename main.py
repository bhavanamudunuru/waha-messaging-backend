"""
WhatsApp Messaging Service - Backend
--------------------------------------
FastAPI backend that:
- Talks to WAHA (WhatsApp HTTP API) to send messages
- Stores all message logs in Firebase Firestore
- Frontend NEVER talks to WAHA directly
- WAHA API key is NEVER exposed to the frontend
"""

import os
import re
import time
import logging
from datetime import datetime
from typing import Optional, Literal

import httpx
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("whatsapp-service")

# ── WAHA Configuration ─────────────────────────────────────────────────
WAHA_URL      = os.getenv("WAHA_URL", "http://localhost:3000")
WAHA_API_KEY  = os.getenv("WAHA_API_KEY", "")
WAHA_SESSION  = os.getenv("WAHA_SESSION", "default")
DEFAULT_COUNTRY_CODE = os.getenv("DEFAULT_COUNTRY_CODE", "91")

# ── Rate limiting ──────────────────────────────────────────────────────
MIN_SECONDS_BETWEEN_SENDS = 2
_last_send_time = 0.0

# ── Firebase Initialization ────────────────────────────────────────────
firebase_cert = {
    "type":                        os.getenv("FIREBASE_TYPE"),
    "project_id":                  os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id":              os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key":                 os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n"),
    "client_email":                os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id":                   os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri":                    os.getenv("FIREBASE_AUTH_URI"),
    "token_uri":                   os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url":        f"https://www.googleapis.com/robot/v1/metadata/x509/{os.getenv('FIREBASE_CLIENT_EMAIL', '')}",
}

try:
    cred = credentials.Certificate(firebase_cert)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    logger.info("Firebase connected successfully!")
except Exception as e:
    logger.error(f"Firebase initialization failed: {e}")
    raise

# Firestore collection name
LOGS_COLLECTION = "message_logs"

# ── FastAPI App ────────────────────────────────────────────────────────
app = FastAPI(title="WhatsApp Messaging Service API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        # Add your Vercel URL here after deploying:
        # "https://your-app.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Firestore Log Helpers ──────────────────────────────────────────────
def write_log_to_firestore(entry: dict):
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


def clear_logs_from_firestore():
    """Deletes all documents in the message_logs collection."""
    try:
        docs = db.collection(LOGS_COLLECTION).stream()
        for doc in docs:
            doc.reference.delete()
        logger.info("All logs cleared from Firestore")
    except Exception as e:
        logger.error(f"Failed to clear logs from Firestore: {e}")


# ── Validation Helpers ─────────────────────────────────────────────────
def normalize_phone_to_chat_id(phone: str, country_code: str) -> str:
    """
    Converts a raw phone number into WAHA individual chat ID format.
    Example: 9876543210 + country 91 -> 919876543210@c.us
    """
    digits_only = re.sub(r"\D", "", phone)
    if digits_only.startswith(country_code):
        full_number = digits_only
    else:
        full_number = f"{country_code}{digits_only}"
    return f"{full_number}@c.us"


def validate_group_id(group_id: str) -> str:
    """
    Validates and normalizes a WhatsApp group ID.
    Accepts full format (120363426488518199@g.us) or just the numeric part.
    """
    group_id = group_id.strip()
    if group_id.endswith("@g.us"):
        return group_id
    if re.fullmatch(r"\d+", group_id):
        return f"{group_id}@g.us"
    raise ValueError("Invalid WhatsApp group ID format. Use numeric-id@g.us")


# ── Pydantic Request Models ────────────────────────────────────────────
class IndividualMessageRequest(BaseModel):
    phone_number: str
    message: str
    country_code: Optional[str] = None

    @field_validator("phone_number")
    @classmethod
    def phone_must_have_digits(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) < 7:
            raise ValueError("Phone number must have at least 7 digits")
        return v

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        if len(v) > 4096:
            raise ValueError("Message too long (max 4096 characters)")
        return v


class GroupMessageRequest(BaseModel):
    group_id: str
    message: str

    @field_validator("group_id")
    @classmethod
    def group_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Group ID cannot be empty")
        return v

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        if len(v) > 4096:
            raise ValueError("Message too long (max 4096 characters)")
        return v


# ── Rate Limit Check ───────────────────────────────────────────────────
def check_rate_limit():
    global _last_send_time
    now = time.time()
    elapsed = now - _last_send_time
    if elapsed < MIN_SECONDS_BETWEEN_SENDS:
        wait = round(MIN_SECONDS_BETWEEN_SENDS - elapsed, 1)
        raise HTTPException(
            status_code=429,
            detail=f"Sending too fast. Please wait {wait} more seconds.",
        )
    _last_send_time = now


# ── WAHA Communication ─────────────────────────────────────────────────
async def send_via_waha(chat_id: str, text: str) -> dict:
    """Posts a sendText request to the WAHA API."""
    url = f"{WAHA_URL}/api/sendText"
    headers = {"Content-Type": "application/json"}
    if WAHA_API_KEY:
        headers["X-Api-Key"] = WAHA_API_KEY

    payload = {
        "session": WAHA_SESSION,
        "chatId": chat_id,
        "text": text,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code >= 400:
            raise Exception(f"WAHA returned {response.status_code}: {response.text}")
        return response.json()


# ── API Routes ─────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "ok", "service": "WhatsApp Messaging Service API"}


@app.get("/api/session-status")
async def session_status():
    """Check if the WAHA WhatsApp session is connected."""
    url = f"{WAHA_URL}/api/sessions/{WAHA_SESSION}"
    headers = {}
    if WAHA_API_KEY:
        headers["X-Api-Key"] = WAHA_API_KEY
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return {
                    "connected": data.get("status") == "WORKING",
                    "status": data.get("status"),
                }
            return {"connected": False, "status": "UNKNOWN"}
    except Exception as e:
        logger.error(f"Could not reach WAHA: {e}")
        return {"connected": False, "status": "WAHA_UNREACHABLE", "error": str(e)}


@app.post("/api/send/individual")
async def send_individual_message(payload: IndividualMessageRequest):
    """Send a WhatsApp text message to an individual phone number."""
    check_rate_limit()

    country_code = payload.country_code or DEFAULT_COUNTRY_CODE
    chat_id = normalize_phone_to_chat_id(payload.phone_number, country_code)

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "receiver_type": "individual",
        "receiver_id": chat_id,
        "message": payload.message,
        "status": "failed",
        "error": None,
    }

    try:
        result = await send_via_waha(chat_id, payload.message)
        log_entry["status"] = "success"
        write_log_to_firestore(log_entry)
        logger.info(f"Message sent to {chat_id}")
        return {"success": True, "chat_id": chat_id, "waha_response": result}
    except Exception as e:
        error_message = str(e)
        log_entry["error"] = error_message
        write_log_to_firestore(log_entry)
        logger.error(f"Failed to send to {chat_id}: {error_message}")
        raise HTTPException(status_code=502, detail=f"Failed to send message: {error_message}")


@app.post("/api/send/group")
async def send_group_message(payload: GroupMessageRequest):
    """Send a WhatsApp text message to a WhatsApp group."""
    check_rate_limit()

    try:
        group_chat_id = validate_group_id(payload.group_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "receiver_type": "group",
        "receiver_id": group_chat_id,
        "message": payload.message,
        "status": "failed",
        "error": None,
    }

    try:
        result = await send_via_waha(group_chat_id, payload.message)
        log_entry["status"] = "success"
        write_log_to_firestore(log_entry)
        logger.info(f"Message sent to group {group_chat_id}")
        return {"success": True, "chat_id": group_chat_id, "waha_response": result}
    except Exception as e:
        error_message = str(e)
        log_entry["error"] = error_message
        write_log_to_firestore(log_entry)
        logger.error(f"Failed to send to group {group_chat_id}: {error_message}")
        raise HTTPException(status_code=502, detail=f"Failed to send message: {error_message}")


@app.get("/api/logs")
def get_logs(limit: int = 100):
    """Fetch the most recent message logs from Firestore."""
    logs = read_logs_from_firestore(limit)
    return {"count": len(logs), "logs": logs}


@app.delete("/api/logs")
def clear_logs():
    """Delete all message logs from Firestore."""
    clear_logs_from_firestore()
    return {"success": True, "message": "All logs cleared from Firestore"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
