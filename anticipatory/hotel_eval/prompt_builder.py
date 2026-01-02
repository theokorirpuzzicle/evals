"""
System prompt builder for the simulated customer (Gemini).
"""

from typing import Dict, List, Any


def build_system_instruction(scenario: Dict[str, Any]) -> str:
    """Build the complete system instruction for Gemini."""
    customer = scenario.get("customer", {})
    preferences = scenario.get("preferences", {})
    style = scenario.get("conversation_style", {})
    additional_instructions = scenario.get("additional_instructions", "")

    opening = style.get("opening", "wait_for_agent")
    greeting = style.get("greeting", "Hello")
    opening_line = style.get("opening_line", "")
    tone = style.get("tone", "polite")
    pace = style.get("pace", "normal")
    verbosity = style.get("verbosity", "concise")
    accent = style.get("accent", "")
    phrases = style.get("phrases", [])

    opening_instructions = _build_opening_instructions(
        opening, greeting, opening_line, style
    )
    tone_instructions = _build_tone_instructions(tone)
    pace_instructions = _build_pace_instructions(pace)
    verbosity_instructions = _build_verbosity_instructions(verbosity)
    accent_instructions = _build_accent_instructions(accent)
    phrase_instructions = _build_phrase_instructions(
        phrases, style.get("language_mix", [])
    )

    return f"""YOU ARE THE CUSTOMER, NOT THE AGENT.

You are {customer.get("name", "a customer")} - a person calling to book a hotel room at The Tamara Resorts.
You are speaking WITH a hotel booking agent who will help you.

CRITICAL: You are the CUSTOMER making the call. The agent is the one who answers and helps you book.
- YOU ask to book a room
- The AGENT asks for your details and helps you
- Never speak as the agent or say things like "How may I assist you?" - that's the agent's line, not yours.

{opening_instructions}

YOUR PRIMARY GOAL: Complete the booking and GET A BOOKING NUMBER. Do not end the call without a booking number!

CONVERSATION STYLE:
- {tone_instructions}
- {pace_instructions}
- {verbosity_instructions}
- {accent_instructions}
- {phrase_instructions}

CRITICAL RULES FOR COMPLETING THE BOOKING:
1. ALWAYS respond when the agent asks you something - never stay silent
2. When asked ANY confirmation question, say "Yes" clearly
3. When asked about proceeding/confirming, say "Yes, please confirm the booking"
4. If the agent summarizes the booking, say "Yes, that's all correct. Please confirm."
5. If there's a pause after pricing, say "That sounds good, let's book it"
6. The booking is NOT complete until you hear a booking/confirmation number
7. If you haven't received a booking number after providing all info, ask: "Can you confirm the booking now?"
8. WAIT for the agent to finish speaking before responding - don't interrupt
9. Do NOT repeat yourself - if you already said something, wait for the agent to respond

YOUR INFORMATION (provide clearly when asked):
- Full Name: {customer.get("name", "Guest")}
- Phone: {customer.get("phone", "+91 98765 43210")}
- Email: {customer.get("email", "guest@example.com")}

YOUR BOOKING PREFERENCES:
- Hotel: {preferences.get("hotel", "Tamara Coorg")}
- Check-in: {preferences.get("checkin", "tomorrow")}
- Duration: {preferences.get("duration", "3 nights")}
- Guests: {preferences.get("guests", "2 adults")}
- Room type: {preferences.get("room_type", "Luxury Cottage")}

HOW TO RESPOND (only speak your lines, never narrate or describe):

When asked "How may I assist you?" → Say "I'd like to book a room please"

When asked for your name → Say "{customer.get("name", "Guest")}"

When asked for your phone number → Say "{customer.get("phone", "+91 98765 43210")}"

When information is repeated back for confirmation → Say "Yes, that's correct"

When asked which resort → Say "{preferences.get("hotel", "Tamara Coorg")}"

When asked about travel dates → Say "{preferences.get("checkin", "tomorrow")} for {preferences.get("duration", "3 nights")}"

When asked how many guests → Say "{preferences.get("guests", "2 adults")}"

When asked about getaway type → Say "Restful please"

When asked about rates → Say "Yes please"

When price is quoted → Say "That sounds good, let's proceed"

When asked about special occasions → Say "No, just a getaway" (unless instructed otherwise)

When asked for email → Say "{customer.get("email", "guest@example.com")}"

When asked to confirm → Say "Yes, please confirm the booking"

When recap is done → Say "Yes, everything is correct. Please confirm."

When booking number is given → Say "Thank you so much! Goodbye!" and END the conversation. Do not say anything else after goodbye.

When agent says goodbye/farewell → Say "Thank you, goodbye!" ONCE and stop speaking entirely.

When agent says they CANNOT complete the booking (technical issue, policy restriction, system problem) → Accept it gracefully. Say "I understand. Thank you for your help. Goodbye." and END the call. Do NOT keep asking to proceed.

IMPORTANT: Only speak your responses. Never say things like "Agent:" or describe what the agent is saying. Just respond naturally as a customer would.

WHEN TO STOP PUSHING:
- If the agent says "unable to complete", "cannot proceed", "technical issue", "call back later", or similar → STOP asking to book
- If the agent apologizes and says the booking cannot be done → Accept it and say goodbye
- Do NOT repeat "please proceed" or "confirm the booking" if the agent already said they can't

AFTER SAYING GOODBYE:
- Once you say "Goodbye" or "Thank you, goodbye!", STOP SPEAKING ENTIRELY
- Do NOT say goodbye multiple times
- Do NOT continue the conversation after farewells are exchanged
- The conversation is OVER after goodbye - remain silent

{additional_instructions}

REMEMBER: Your goal is to GET A BOOKING NUMBER. If the agent says they cannot complete it, accept gracefully and end the call."""


def _build_opening_instructions(
    opening: str, greeting: str, opening_line: str, style: Dict
) -> str:
    openings = {
        "wait_for_agent": f'Wait for agent greeting, then say "{greeting}, I\'d like to book a room please."',
        "direct_request": f'After agent greets, say: "{greeting}! I\'d like to book a room please."',
        "greeting_only": f'Say "{greeting}" when agent answers, wait for prompt, then ask to book.',
        "question_first": f'Start with: "{greeting}, {style.get("first_question", "Is this the booking line?")}" Then book.',
        "enthusiastic_intro": f'Be enthusiastic! "{greeting} {opening_line}" then book.',
        "hesitant_start": f'Start hesitantly: "{greeting}... {opening_line}" Let agent guide you.',
        "direct_efficient": f'Be direct: "{greeting}. {opening_line}" Give info upfront.',
        "chatty_intro": f'Start warmly: "{greeting} {opening_line}" Be friendly.',
        "uncertain_start": f'Sound uncertain: "{greeting}... {opening_line}" Let agent help.',
        "calm_request": f'Calmly say: "{greeting}. {opening_line}"',
        "concerned_query": f'Lead with concern: "{greeting}. {opening_line}" Then book.',
        "urgent_request": f'Show urgency: "{greeting}! {opening_line}"',
        "professional_inquiry": f'Be professional: "{greeting}. {opening_line}"',
        "allergy_first": f'Lead with medical concern: "{greeting}. {opening_line}" Then book.',
        "accessibility_inquiry": f'Start with accessibility: "{greeting}. {opening_line}"',
        "family_focused": f'Focus on family: "{greeting}. {opening_line}"',
        "wait_then_request": f'Wait for greeting, say "{greeting}", then request booking.',
        "excited_special": f'Share excitement: "{greeting} {opening_line}"',
        "happy_announcement": f'Start happy: "{greeting} {opening_line}"',
        "specific_date_focus": f'Focus on dates: "{greeting}. {opening_line}"',
        "budget_inquiry": f'Be upfront about budget: "{greeting}. {opening_line}"',
        "extended_stay_intro": f'Mention extended stay: "{greeting}. {opening_line}"',
        "returning_guest": f'Identify as returning: "{greeting} {opening_line}"',
        "booking_for_others": f'Clarify booking for others: "{greeting}. {opening_line}"',
        "interest_based": f'Lead with interest: "{greeting}. {opening_line}"',
        "referral_mention": f'Mention referral: "{greeting}. {opening_line}"',
        "social_media_inspired": f'Show enthusiasm: "{greeting} {opening_line}"',
        "time_sensitive": f'Mention timing: "{greeting}. {opening_line}"',
        "confused_start": f'Start confused: "{greeting}. {opening_line}" Let agent help.',
    }
    default_opening = f'Say "{greeting}" and ask to book.'
    return f"OPENING: {openings.get(opening, default_opening)}"


def _build_tone_instructions(tone: str) -> str:
    tones = {
        "polite": "Be polite and courteous.",
        "friendly": "Be warm and friendly.",
        "enthusiastic": "Sound excited!",
        "professional": "Keep professional tone.",
        "calm": "Maintain calm demeanor.",
        "nervous": "Sound slightly nervous at first.",
        "very_happy": "Sound happy and excited!",
        "warm": "Be warm and personable.",
        "serious": "Be serious and focused.",
        "gentle": "Be gentle and soft.",
        "pleasant": "Be pleasant and agreeable.",
        "excited": "Sound excited!",
        "very_friendly": "Be extra warm.",
        "polite_formal": "Be polite but formal.",
        "hopeful": "Sound hopeful.",
        "hopeful_urgent": "Sound hopeful with urgency.",
        "caring": "Show care.",
        "creative": "Be expressive.",
        "trusting": "Sound trusting.",
        "excited_millennial": "Sound young and enthusiastic!",
        "honest": "Be straightforward.",
        "relaxed": "Sound relaxed.",
        "practical": "Be practical.",
        "concerned": "Show concern.",
        "purposeful": "Be focused.",
        "business": "Keep it business-like.",
        "uncertain": "Sound uncertain.",
    }
    return tones.get(tone, "Be natural.")


def _build_pace_instructions(pace: str) -> str:
    paces = {
        "fast": "Speak quickly.",
        "slow": "Speak slowly.",
        "very_slow": "Speak very slowly with pauses.",
        "hesitant": "Speak with hesitation.",
        "measured": "Speak at measured pace.",
        "normal": "Speak naturally.",
        "quick": "Keep quick pace.",
        "enthusiastic": "Speak with energy.",
        "warm": "Speak warmly.",
        "unhurried": "Take your time.",
    }
    return paces.get(pace, "Speak naturally.")


def _build_verbosity_instructions(verbosity: str) -> str:
    verbosities = {
        "concise": "Keep responses short (1-2 sentences).",
        "minimal": "Use minimal words.",
        "medium": "Give appropriately detailed responses.",
        "chatty": "Chat a bit, add comments.",
        "very_chatty": "Be conversational.",
        "detailed": "Provide detailed responses.",
        "expressive": "Express yourself freely.",
        "business_like": "Keep efficient.",
    }
    return verbosities.get(verbosity, "Give natural responses.")


def _build_accent_instructions(accent: str) -> str:
    if not accent:
        return ""
    accents = {
        "Tamil": "Speak with Tamil accent.",
        "Hindi": "Speak with Hindi accent, use Hindi expressions.",
        "British": "Speak with British accent.",
        "American": "Speak with American accent.",
    }
    return accents.get(accent, "")


def _build_phrase_instructions(phrases: List[str], language_mix: List[str]) -> str:
    parts = []
    if phrases:
        parts.append(f"Use expressions like: {', '.join(phrases[:5])}.")
    if language_mix:
        parts.append(f"Mix in words like: {', '.join(language_mix[:5])}.")
    return " ".join(parts)
