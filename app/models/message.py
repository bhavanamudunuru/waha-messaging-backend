"""
Pydantic request/response models for message sending endpoints.
"""

import re
from typing import Optional

from pydantic import BaseModel, field_validator


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


class ScheduledMessageRequest(BaseModel):
    receiver_type: str   # "individual" or "group"
    receiver_id: str     # phone number or group_id
    message: str
    scheduled_time: str  # ISO format, IST local time: "2026-07-01T15:30:00"
    country_code: Optional[str] = None


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