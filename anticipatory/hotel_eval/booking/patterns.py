"""
Regex patterns for booking number extraction.
Includes patterns that account for STT transcription errors.
"""

from typing import List

# Patterns ordered from most specific to most general
# Note: Include STT transcription errors like "bouquet", "boofing", "bucket" for "booking"
BOOKING_NUMBER_PATTERNS: List[str] = [
    # Format: TC-2024-1234 or similar with dashes
    r"(?:booking|bouquet|bucket|boofing|buffing)\s*numbers?[:\s]+(?:is\s+)?([A-Z]{2,4}[-][0-9]{4}[-][0-9]+)",
    r"confirmation\s*numbers?[:\s]+(?:is\s+)?([A-Z]{2,4}[-][0-9]{4}[-][0-9]+)",
    r"reference\s*numbers?[:\s]+(?:is\s+)?([A-Z]{2,4}[-][0-9]{4}[-][0-9]+)",

    # Alphanumeric codes (letters AND numbers mixed)
    r"(?:booking|bouquet|bucket|boofing|buffing)\s*numbers?[:\s]+(?:is\s+)?([A-Z]+[0-9]+[A-Z0-9]*)",
    r"(?:booking|bouquet|bucket|boofing|buffing)\s*numbers?[:\s]+(?:is\s+)?([0-9]+[A-Z]+[A-Z0-9]*)",
    r"confirmation\s*numbers?[:\s]+(?:is\s+)?([A-Z]+[0-9]+[A-Z0-9]*)",
    r"confirmation\s*numbers?[:\s]+(?:is\s+)?([0-9]+[A-Z]+[A-Z0-9]*)",

    # Simple numeric booking numbers
    r"(?:booking|bouquet|bucket|boofing|buffing)\s*numbers?[:\s]+(?:is\s+)?(\d{3,8})\b",
    r"confirmation\s*numbers?[:\s]+(?:is\s+)?(\d{3,8})\b",
    r"reference\s*numbers?[:\s]+(?:is\s+)?(\d{3,8})\b",
    r"reservation\s*numbers?[:\s]+(?:is\s+)?(\d{3,8})\b",

    # "your booking/confirmation is [number]" patterns
    r"your (?:booking|bouquet|bucket|boofing|buffing) (?:number )?is[:\s]+([A-Z0-9-]{3,15})",
    r"your confirmation (?:number )?is[:\s]+([A-Z0-9-]{3,15})",
    r"your reservation (?:number )?is[:\s]+([A-Z0-9-]{3,15})",
    r"your reference (?:number )?is[:\s]+([A-Z0-9-]{3,15})",

    # Fallback pattern
    r"(?:confirmed|booked).*?(?:booking|bouquet|bucket|boofing|buffing|confirmation|reference|reservation)\s*(?:number)?\s*(?:is)?\s*[:\s]+([A-Z0-9-]{3,15})",
]

# Patterns for extracting any value (even invalid) as booking number
INVALID_BOOKING_PATTERNS: List[str] = [
    # Capture any word after "booking number is" (including STT errors)
    r"(?:booking|bouquet|bucket|boofing|buffing)\s*numbers?[:\s]+(?:is\s+)?(\w+)",
    r"confirmation\s*numbers?[:\s]+(?:is\s+)?(\w+)",
    r"reference\s*numbers?[:\s]+(?:is\s+)?(\w+)",
    r"reservation\s*numbers?[:\s]+(?:is\s+)?(\w+)",
    r"your (?:booking|bouquet|bucket|boofing|buffing) (?:number )?is[:\s]+(\w+)",
    r"your confirmation (?:number )?is[:\s]+(\w+)",
]

# Confirmation indicators for fallback extraction
# Includes STT transcription errors (bouquet = booking, bucket = booking, boofing = booking)
CONFIRMATION_INDICATORS: List[str] = [
    "booking number",
    "bouquet number",
    "bucket number",
    "boofing number",
    "buffing number",
    "confirmation number",
    "reference number",
    "reservation number",
    "your booking is",
    "your bouquet is",
    "your boofing is",
    "booking confirmed",
    "reservation confirmed",
]

# Words to skip when extracting invalid booking numbers
SKIP_WORDS = {
    "the", "a", "an", "your", "our", "this", "that", "it",
    "for", "and", "or", "is", "number"
}
