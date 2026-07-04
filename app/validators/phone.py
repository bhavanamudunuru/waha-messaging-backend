"""
Validation / normalization helpers for phone numbers and WhatsApp group IDs.
"""

import re


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
