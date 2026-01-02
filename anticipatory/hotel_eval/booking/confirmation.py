"""
Booking confirmation detection utilities.
"""

import re
from typing import List, Dict

from .extraction import extract_booking_number


# Confirmation phrases (including STT errors like bouquet = booking)
CONFIRMATION_PHRASES = [
    "your booking number is",
    "your bouquet number is",
    "your confirmation number is",
    "your reference number is",
    "your reservation number is",
    "booking number:",
    "bouquet number:",
    "confirmation number:",
    "i have confirmed your booking",
    "your booking has been confirmed",
    "your reservation has been confirmed",
    "booking is confirmed",
    "reservation is confirmed",
    "i've booked your",
    "successfully booked",
    "booking confirmed for",
    "reservation confirmed for",
    "your booking is confirmed",
    "your reservation is confirmed",
]

# Explicit confirmations (work without number)
EXPLICIT_CONFIRMATIONS = [
    "your booking has been confirmed",
    "i have confirmed your booking",
    "booking is now confirmed",
    "reservation is now confirmed",
    "your stay has been booked",
    "i've successfully booked",
    "your booking is confirmed",
    "your reservation is confirmed",
    "successfully made your reservation",
    "successfully made your booking",
]


def is_booking_confirmed(transcripts: List[Dict[str, str]]) -> bool:
    """
    Check if booking is confirmed based on transcript content.

    A booking is considered confirmed if:
    1. A confirmation phrase is present AND a valid booking number exists
    2. An explicit confirmation phrase is present (even without number)
    3. A confirmation + number mention pattern is found

    CRITICAL: If agent mentions issues/problems with booking, it's NOT confirmed.

    Args:
        transcripts: List of conversation transcripts

    Returns:
        True if the booking appears to be confirmed
    """
    agent_text = " ".join(
        t["content"].lower() for t in transcripts if t["role"] == "agent"
    )

    # Check for booking failure indicators - if any are present, booking is NOT confirmed
    failure_patterns = [
        "encountered an issue",
        "encountered a issue",
        "encountering an issue",
        "encountering a issue",
        "technical issue",
        "technical hitch",
        "technical problem",
        "unable to finalize",
        "unable to complete",
        "cannot finalize",
        "cannot complete",
        "can't finalize",
        "can't complete",
        "system issue",
        "preventing me from",
        "try that again",
        "try again",
        "let me try",
        "having trouble",
        "having difficulty",
    ]

    # If agent mentioned any failure/issue pattern, booking is NOT confirmed
    if any(pattern in agent_text for pattern in failure_patterns):
        return False

    has_confirmation_phrase = any(
        phrase in agent_text for phrase in CONFIRMATION_PHRASES
    )

    # Check for valid booking number
    booking_number = extract_booking_number(transcripts)
    has_valid_number = booking_number is not None

    explicit_confirmed = any(
        phrase in agent_text for phrase in EXPLICIT_CONFIRMATIONS
    )

    # Pattern: confirmation + number nearby (including STT errors)
    has_number_mention = bool(re.search(
        r'(confirmed|booked).*?(booking|bouquet|bucket|confirmation|reservation|reference)\s*(number)?\s*(is)?\s*\d{3,}',
        agent_text
    ))

    return (has_confirmation_phrase and has_valid_number) or explicit_confirmed or has_number_mention
