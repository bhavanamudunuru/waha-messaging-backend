"""
Simple in-memory rate limiter to stop messages being sent too quickly
(protects against WAHA / WhatsApp throttling or bans).
"""

import time

from fastapi import HTTPException

from app.core.config import MIN_SECONDS_BETWEEN_SENDS

_last_send_time = 0.0


def check_rate_limit() -> None:
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
