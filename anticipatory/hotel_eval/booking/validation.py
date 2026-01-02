"""
Booking number validation utilities.
"""

import re
from typing import Set

from ..config import FALSE_POSITIVE_WORDS


def is_valid_booking_number(candidate: str, false_positives: Set[str] = None) -> bool:
    """
    Validate if a string looks like a real booking number.
    Accepts 3-8 digit numeric codes, alphanumeric codes, and letter-only codes.

    Args:
        candidate: The string to validate
        false_positives: Optional set of words to reject (defaults to FALSE_POSITIVE_WORDS)

    Returns:
        True if the candidate looks like a valid booking number
    """
    if false_positives is None:
        false_positives = FALSE_POSITIVE_WORDS

    candidate_clean = candidate.strip().upper()
    candidate_lower = candidate.lower()

    # Must not be a common word
    if candidate_lower in false_positives:
        return False

    # Must be at least 3 characters
    if len(candidate_clean) < 3:
        return False

    # All-letter codes: accept if 3-8 characters (e.g., "TCWFO", "ABC")
    # This handles booking codes that are purely alphabetic
    if candidate_clean.isalpha():
        return 3 <= len(candidate_clean) <= 8

    # Pure numeric codes: must be 3-8 digits
    if candidate_clean.isdigit():
        return 3 <= len(candidate_clean) <= 8

    # Alphanumeric codes
    if re.match(r"^[A-Z0-9-]+$", candidate_clean):
        # Must have at least one digit
        if not any(c.isdigit() for c in candidate_clean):
            return False
        # Should not be a phone number (10+ consecutive digits)
        digits_only = re.sub(r"[^0-9]", "", candidate_clean)
        if len(digits_only) >= 10:
            return False
        return True

    return False
