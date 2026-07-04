"""
Endpoints for sending WhatsApp messages to individuals and groups.
"""

import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.core.config import DEFAULT_COUNTRY_CODE, IST
from app.core.logging import logger
from app.middleware.rate_limit import check_rate_limit
from app.models.message import IndividualMessageRequest, GroupMessageRequest, ScheduledMessageRequest
from app.services.firestore_service import write_log_to_firestore
from app.services.waha_client import send_via_waha
from app.validators.phone import normalize_phone_to_chat_id, validate_group_id

router = APIRouter(prefix="/api/send", tags=["messages"])


@router.post("/individual")
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


@router.post("/group")
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

"""
Endpoints for sending WhatsApp messages to individuals and groups.
"""

import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.core.config import DEFAULT_COUNTRY_CODE, IST
from app.core.logging import logger
from app.middleware.rate_limit import check_rate_limit
from app.models.message import IndividualMessageRequest, GroupMessageRequest, ScheduledMessageRequest
from app.services.firestore_service import write_log_to_firestore
from app.services.waha_client import send_via_waha
from app.validators.phone import normalize_phone_to_chat_id, validate_group_id

router = APIRouter(prefix="/api/send", tags=["messages"])


@router.post("/individual")
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


@router.post("/group")
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

@router.post("/scheduled")
async def schedule_message(payload: ScheduledMessageRequest):
    """Schedule a WhatsApp message to be sent at a specific time (IST)."""
    try:
        scheduled_dt = datetime.fromisoformat(payload.scheduled_time).replace(tzinfo=IST)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid scheduled_time format. Use: 2026-07-01T15:30:00")

    delay = (scheduled_dt - datetime.now(IST)).total_seconds()
    if delay < 0:
        raise HTTPException(status_code=400, detail="Scheduled time must be in the future.")

    if payload.receiver_type == "individual":
        country_code = payload.country_code or DEFAULT_COUNTRY_CODE
        chat_id = normalize_phone_to_chat_id(payload.receiver_id, country_code)
    elif payload.receiver_type == "group":
        try:
            chat_id = validate_group_id(payload.receiver_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="receiver_type must be 'individual' or 'group'")

    async def send_later():
        await asyncio.sleep(delay)
        log_entry = {
            "timestamp": datetime.now(IST).isoformat(),
            "receiver_type": payload.receiver_type,
            "receiver_id": chat_id,
            "message": payload.message,
            "status": "failed",
            "error": None,
            "scheduled": True,
            "scheduled_time": payload.scheduled_time,
        }
        try:
            await send_via_waha(chat_id, payload.message)
            log_entry["status"] = "success"
            logger.info(f"Scheduled message sent to {chat_id}")
        except Exception as e:
            log_entry["error"] = str(e)
            logger.error(f"Scheduled message failed to {chat_id}: {e}")
        finally:
            write_log_to_firestore(log_entry)

    asyncio.create_task(send_later())
    return {
        "success": True,
        "message": f"Message scheduled for {payload.scheduled_time}",
        "chat_id": chat_id,
        "delay_seconds": round(delay),
    }