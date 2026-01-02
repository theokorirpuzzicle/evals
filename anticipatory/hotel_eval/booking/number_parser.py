"""
Convert spelled-out numbers to digits for booking number extraction.
Handles STT transcription of booking codes like "T C W F O" or "THREE TWO ONE".
"""

import re
from typing import Optional


# Mapping of spelled-out numbers to digits
WORD_TO_DIGIT = {
    'zero': '0', 'oh': '0', 'o': '0',
    'one': '1', 'won': '1',
    'two': '2', 'to': '2', 'too': '2',
    'three': '3', 'tree': '3',
    'four': '4', 'for': '4', 'fore': '4',
    'five': '5',
    'six': '6', 'sex': '6',
    'seven': '7',
    'eight': '8', 'ate': '8',
    'nine': '9', 'niner': '9',
}


def convert_spelled_numbers(text: str) -> str:
    """
    Convert spelled-out numbers in text to their digit equivalents.
    
    Examples:
        "THREE TWO ONE" -> "321"
        "T C W F O" -> "TCWFO"
        "ONE ZERO FIVE" -> "105"
    
    Args:
        text: Text potentially containing spelled-out numbers
        
    Returns:
        Text with spelled-out numbers converted to digits
    """
    result = text
    
    # Convert each spelled-out number
    for word, digit in WORD_TO_DIGIT.items():
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(word) + r'\b'
        result = re.sub(pattern, digit, result, flags=re.IGNORECASE)
    
    return result


def extract_spelled_booking_code(text: str) -> Optional[str]:
    """
    Extract booking codes that were spelled out letter-by-letter or number-by-number.
    
    Examples:
        "T C W F O" -> "TCWFO"
        "T. C. W. F. O." -> "TCWFO"
        "THREE TWO ONE QRY" -> "321QRY"
    
    Args:
        text: Text to search
        
    Returns:
        Extracted booking code or None
    """
    # Pattern 1: Single letters/digits separated by spaces or dots
    # Matches: "T C W F O" or "T. C. W. F. O."
    pattern_spaced = r'\b([A-Z0-9][\s.]+[A-Z0-9][\s.A-Z0-9]{2,20})\b'
    matches = re.findall(pattern_spaced, text, re.IGNORECASE)
    
    for match in matches:
        # Remove spaces and dots
        cleaned = re.sub(r'[\s.]', '', match).upper()
        # Must be 3-8 characters
        if 3 <= len(cleaned) <= 8:
            return cleaned
    
    # Pattern 2: Spelled-out numbers
    # Look for sequences like "THREE TWO ONE"
    text_with_digits = convert_spelled_numbers(text)
    
    # If conversion happened, try to extract the number
    if text_with_digits != text:
        # Look for digit sequences that resulted from conversion
        pattern_digits = r'\b(\d{3,8})\b'
        digit_matches = re.findall(pattern_digits, text_with_digits)
        if digit_matches:
            return digit_matches[0]
    
    return None


def normalize_booking_number_text(text: str) -> str:
    """
    Normalize text before booking number extraction.
    Converts spelled-out formats to standard format.
    
    Args:
        text: Raw text from transcript
        
    Returns:
        Normalized text
    """
    # First try to extract spelled codes
    spelled_code = extract_spelled_booking_code(text)
    
    if spelled_code:
        # Replace the spelled-out version with the normalized version
        # Find the original text that matched
        pattern_spaced = r'([A-Z0-9][\s.]+[A-Z0-9][\s.A-Z0-9]{2,20})'
        text = re.sub(pattern_spaced, spelled_code, text, flags=re.IGNORECASE, count=1)
    
    # Convert any remaining spelled numbers
    text = convert_spelled_numbers(text)
    
    return text
