"""
WhatsApp Messaging Service - Backend
--------------------------------------
FastAPI backend that:
- Talks to WAHA (WhatsApp HTTP API) to send messages
- Stores all message logs in Firebase Firestore
- Frontend NEVER talks to WAHA directly
- WAHA API key is NEVER exposed to the frontend

This file only wires the app together. Actual logic lives in
core/, models/, routers/, services/, validators/, and middleware/.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import ALLOWED_ORIGINS
from app.routers import session, messages, logs

app = FastAPI(title="WhatsApp Messaging Service API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session.router)
app.include_router(messages.router)
app.include_router(logs.router)
