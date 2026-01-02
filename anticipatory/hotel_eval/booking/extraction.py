"""
Booking number extraction from transcripts.
"""

import re
from typing import Optional, List, Dict

from .validation import is_valid_booking_number
from .number_parser import normalize_booking_number_text, extract_spelled_booking_code
from .patterns import (
    BOOKING_NUMBER_PATTERNS,
    INVALID_BOOKING_PATTERNS,
    CONFIRMATION_INDICATORS,
    SKIP_WORDS,
)


def extract_booking_number(
    transcripts: List[Dict[str, str]],
    allow_invalid: bool = False
) -> Optional[str]:
    """
    Extract booking number from transcripts.
    Handles various formats including simple numeric codes like "3456".

    Args:
        transcripts: List of conversation transcripts with 'role' and 'content' keys
        allow_invalid: If True, returns whatever the agent said as the booking number,
                      even if it's not a valid format (e.g., "number" instead of "12345")

    Returns:
        The extracted booking number, or None if not found
    """
    agent_text = " ".join(
        t["content"] for t in transcripts if t["role"] == "agent"
    )
    
    # First, try to extract spelled-out booking codes (e.g., "T. C. W. F. O.")
    spelled_code = extract_spelled_booking_code(agent_text)
    if spelled_code and is_valid_booking_number(spelled_code):
        return spelled_code
    
    # Normalize text (convert spelled numbers to digits)
    agent_text = normalize_booking_number_text(agent_text)
    agent_text_normalized = agent_text.lower()

    # Try main patterns
    for pattern in BOOKING_NUMBER_PATTERNS:
        match = re.search(pattern, agent_text, re.IGNORECASE)
        if match:
            candidate = match.group(1).upper().strip()
            if is_valid_booking_number(candidate):
                return candidate

    # Last resort: look for numbers near confirmation phrases
    for indicator in CONFIRMATION_INDICATORS:
        if indicator in agent_text_normalized:
            pos = agent_text_normalized.find(indicator)
            search_region = agent_text[pos:pos + 80]
            numbers = re.findall(r'\b(\d{3,8})\b', search_region)
            for num in numbers:
                if is_valid_booking_number(num):
                    return num

    # If allow_invalid is True, try to extract whatever the agent said as the "number"
    if allow_invalid:
        for pattern in INVALID_BOOKING_PATTERNS:
            match = re.search(pattern, agent_text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                # Special case: if agent literally said "number" as the booking number, return it
                # This indicates the agent said something like "your booking number is number"
                if candidate.lower() == "number":
                    return "number"
                # Skip other common filler words
                if candidate.lower() not in SKIP_WORDS:
                    return candidate

    return None


def extract_raw_booking_number(transcripts: List[Dict[str, str]]) -> Optional[str]:
    """
    Extract whatever the agent said as the booking number, valid or not.
    Used to capture the actual value for error reporting.

    Args:
        transcripts: List of conversation transcripts

    Returns:
        The raw extracted value, or None if not found
    """
    return extract_booking_number(transcripts, allow_invalid=True)
