"""
Booking detection utilities - backward compatibility shim.

This module re-exports all booking detection functions from the new
modular booking subpackage for backward compatibility.
"""

from .booking import (
    CONVERSATION_STEPS,
    is_valid_booking_number,
    extract_booking_number,
    extract_raw_booking_number,
    is_booking_confirmed,
    get_conversation_stage,
    get_stage_progress,
    get_failed_at_description,
    is_call_ended,
)

__all__ = [
    "CONVERSATION_STEPS",
    "is_valid_booking_number",
    "extract_booking_number",
    "extract_raw_booking_number",
    "is_booking_confirmed",
    "get_conversation_stage",
    "get_stage_progress",
    "get_failed_at_description",
    "is_call_ended",
]
