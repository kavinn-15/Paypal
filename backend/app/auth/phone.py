import re
import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat
from fastapi import HTTPException, status


def normalize_phone_number(raw_phone: str, default_region: str = "IN") -> str:
    """
    Parses and formats a raw phone number into strict E.164 format (e.g. +919876543210).
    Raises HTTPException(400) if the phone number is invalid.
    """
    if not raw_phone or not raw_phone.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is required."
        )

    cleaned = raw_phone.strip()
    try:
        # If user did not include a leading '+', default to default_region (e.g. 'IN')
        parsed = phonenumbers.parse(cleaned, default_region if not cleaned.startswith("+") else None)
        if not phonenumbers.is_valid_number(parsed):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid phone number format for region {default_region}. Please check your number."
            )
        return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
    except NumberParseException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to parse phone number: {str(e)}"
        )


def is_valid_phone_number(raw_phone: str, default_region: str = "IN") -> bool:
    """
    Returns True if raw_phone can be parsed into a valid E.164 number.
    """
    try:
        cleaned = raw_phone.strip()
        parsed = phonenumbers.parse(cleaned, default_region if not cleaned.startswith("+") else None)
        return phonenumbers.is_valid_number(parsed)
    except Exception:
        return False


def get_phone_country_code(raw_phone: str, default_region: str = "IN") -> str:
    """
    Extracts the country calling code with leading '+', e.g. '+91'.
    """
    try:
        cleaned = raw_phone.strip()
        parsed = phonenumbers.parse(cleaned, default_region if not cleaned.startswith("+") else None)
        return f"+{parsed.country_code}"
    except Exception:
        return "+91"


def mask_phone_number(e164_phone: str) -> str:
    """
    Masks middle digits of an E.164 phone number for privacy display.
    Example: +919876543210 -> +91 98*** **210
    """
    if not e164_phone or len(e164_phone) < 7:
        return e164_phone

    country_code = get_phone_country_code(e164_phone)
    national_part = e164_phone[len(country_code):]

    if len(national_part) <= 4:
        return f"{country_code} {'*' * len(national_part)}"

    visible_prefix = national_part[:2]
    visible_suffix = national_part[-3:]
    masked_middle = "*" * (len(national_part) - 5)

    return f"{country_code} {visible_prefix}{masked_middle}{visible_suffix}"

