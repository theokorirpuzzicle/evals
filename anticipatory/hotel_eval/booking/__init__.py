"""
Booking detection and validation utilities.
Handles extraction, validation, and conversation stage tracking.
"""

from .constants import CONVERSATION_STEPS
from .validation import is_valid_booking_number
from .extraction import extract_booking_number, extract_raw_booking_number
from .confirmation import is_booking_confirmed
from .stages import (
    get_conversation_stage,
    get_stage_progress,
    get_failed_at_description,
    is_call_ended,
)

__all__ = [
    # Constants
    "CONVERSATION_STEPS",
    # Validation
    "is_valid_booking_number",
    # Extraction
    "extract_booking_number",
    "extract_raw_booking_number",
    # Confirmation
    "is_booking_confirmed",
    # Stages
    "get_conversation_stage",
    "get_stage_progress",
    "get_failed_at_description",
    "is_call_ended",
]
