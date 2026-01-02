"""
Voice selection logic for AI providers based on customer persona.
Selects appropriate voices for Gemini and OpenAI based on scenario attributes.
"""

from typing import Dict, List

# Voice characteristics for Gemini
# Available voices: Puck, Charon, Kore, Fenrir, Aoede, Leda, Orus, Zephyr
GEMINI_VOICES = {
    "male": {
        "neutral": "Puck",
        "deep": "Charon",
        "strong": "Fenrir",
        "mature": "Orus",
    },
    "female": {
        "young": "Kore",
        "pleasant": "Aoede",
        "elegant": "Leda",
    },
    "neutral": "Zephyr",
}

# OpenAI Realtime API voices
OPENAI_VOICES: List[str] = ["alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse"]

# Name indicators for gender inference
MALE_NAME_INDICATORS: List[str] = [
    "Rajesh", "Ramesh", "Arun", "Michael", "Aditya", "Sandeep", "Anand",
    "Amit", "Rohan", "Vikram", "Suresh", "Karthik", "Ravi", "Rahul",
    "Anil", "Kiran", "Siddharth", "Theo"
]

FEMALE_NAME_INDICATORS: List[str] = [
    "Priya", "Kamala", "Meenakshi", "Divya", "Sunita", "Maya",
    "Kavitha", "Meera", "Pooja", "Neelam", "Neha", "Lakshmi",
    "Tanvi", "Zara", "Shreya"
]


def _infer_gender(customer_name: str) -> str:
    """
    Infer gender from customer name.

    Args:
        customer_name: Full customer name

    Returns:
        'male', 'female', or 'unknown'
    """
    is_male = any(name in customer_name for name in MALE_NAME_INDICATORS)
    is_female = any(name in customer_name for name in FEMALE_NAME_INDICATORS)

    if is_male and not is_female:
        return "male"
    elif is_female and not is_male:
        return "female"
    return "unknown"


def select_gemini_voice(scenario: Dict) -> str:
    """
    Select appropriate Gemini voice based on customer persona.

    Voice characteristics:
    - Puck: Default, neutral (male)
    - Charon: Deep, serious (male)
    - Kore: Young, feminine (female)
    - Fenrir: Strong, masculine (male)
    - Aoede: Musical, pleasant (female)
    - Leda: Elegant, refined (female)
    - Orus: Mature, authoritative (male)
    - Zephyr: Light, airy (gender-neutral)

    Args:
        scenario: Scenario configuration dict

    Returns:
        Selected voice name
    """
    customer_name = scenario.get("customer", {}).get("name", "")
    tone = scenario.get("conversation_style", {}).get("tone", "normal")
    accent = scenario.get("conversation_style", {}).get("accent", "")
    additional_instructions = scenario.get("additional_instructions", "")

    gender = _infer_gender(customer_name)

    # Special cases based on tone and persona
    if tone == "gentle" or tone == "calm":
        return "Leda"  # Elegant, refined for calm/gentle personas
    elif tone == "nervous" or tone == "concerned":
        return "Kore"  # Young, feminine for nervous/concerned
    elif tone == "business" or tone == "professional":
        return "Orus" if gender == "male" else "Aoede"
    elif tone in ("enthusiastic", "very_happy", "excited"):
        return "Zephyr"  # Light, airy for enthusiastic personas
    elif accent == "British" or "British" in additional_instructions:
        return "Leda"  # Refined for British accent
    elif accent == "American" or "American" in additional_instructions:
        return "Fenrir" if gender == "male" else "Kore"
    elif "elderly" in additional_instructions.lower() or tone == "gentle":
        return "Leda"  # Elegant, mature voice
    elif "fast" in additional_instructions.lower() or tone == "business":
        return "Orus" if gender == "male" else "Aoede"

    # Default gender-based selection
    if gender == "male":
        if tone in ("polite_formal", "professional"):
            return "Orus"
        elif tone in ("warm", "friendly"):
            return "Puck"
        else:
            return "Fenrir"
    elif gender == "female":
        if tone in ("warm", "very_friendly", "friendly"):
            return "Aoede"
        elif tone in ("polite_formal", "serious"):
            return "Leda"
        else:
            return "Kore"

    # Fallback to variety based on scenario ID (for consistent but varied voices)
    scenario_id = scenario.get("id", "")
    voices = ["Puck", "Kore", "Aoede", "Fenrir", "Leda", "Orus", "Zephyr", "Charon"]
    return voices[hash(scenario_id) % len(voices)]


def select_openai_voice(scenario: Dict) -> str:
    """
    Select appropriate OpenAI Realtime API voice based on scenario.

    Available voices: alloy, ash, ballad, coral, echo, sage, shimmer, verse

    Args:
        scenario: Scenario configuration dict

    Returns:
        Selected voice name
    """
    scenario_id = scenario.get("id", "")
    return OPENAI_VOICES[hash(scenario_id) % len(OPENAI_VOICES)]


def select_voice_for_customer(scenario: Dict, provider: str = "gemini") -> str:
    """
    Select appropriate voice for customer based on provider and persona.

    Args:
        scenario: Scenario configuration dict
        provider: AI provider ('gemini' or 'openai')

    Returns:
        Selected voice name
    """
    if provider == "openai":
        return select_openai_voice(scenario)
    return select_gemini_voice(scenario)
