"""
All outbound HTTP communication with the WAHA (WhatsApp HTTP API) server lives here.
Nothing outside this file should talk to WAHA directly.
"""

import httpx

from app.core.config import WAHA_URL, WAHA_API_KEY, WAHA_SESSION
from app.core.logging import logger


def _waha_headers(include_content_type: bool = True) -> dict:
    headers = {}
    if include_content_type:
        headers["Content-Type"] = "application/json"
    if WAHA_API_KEY:
        headers["X-Api-Key"] = WAHA_API_KEY
    return headers


async def send_via_waha(chat_id: str, text: str) -> dict:
    """Posts a sendText request to the WAHA API."""
    url = f"{WAHA_URL}/api/sendText"
    payload = {
        "session": WAHA_SESSION,
        "chatId": chat_id,
        "text": text,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, json=payload, headers=_waha_headers())
        if response.status_code >= 400:
            raise Exception(f"WAHA returned {response.status_code}: {response.text}")
        return response.json()


async def get_session_status() -> dict:
    """Check if the WAHA WhatsApp session is connected."""
    url = f"{WAHA_URL}/api/sessions/{WAHA_SESSION}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=_waha_headers(include_content_type=False))
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
