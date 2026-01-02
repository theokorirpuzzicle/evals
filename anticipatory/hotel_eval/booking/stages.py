"""
Conversation stage detection and tracking utilities.
"""

import re
from typing import List, Dict, Tuple, Optional

from .constants import CONVERSATION_STEPS, STAGE_DESCRIPTIONS
from .confirmation import is_booking_confirmed
from .extraction import extract_booking_number, extract_raw_booking_number


def get_conversation_stage(transcripts: List[Dict[str, str]]) -> str:
    """
    Determine the current stage of the booking conversation.
    Maps to the 13-step agent conversation flow from agent-prompt.txt.

    Args:
        transcripts: List of conversation transcripts

    Returns:
        The current conversation stage name
    """
    agent_text = " ".join(
        t["content"].lower() for t in transcripts if t["role"] == "agent"
    )
    customer_text = " ".join(
        t["content"].lower() for t in transcripts if t["role"] == "customer"
    )

    # Check stages in reverse order (most advanced first)

    # BOOKING_CONFIRMED - Final success state
    if is_booking_confirmed(transcripts):
        return "BOOKING_CONFIRMED"

    # CONFIRMATION_ASKED - Agent asked to confirm booking
    if any(p in agent_text for p in [
        "shall i go ahead", "shall i confirm", "shall i book",
        "should i proceed", "shall i secure", "ready to confirm",
        "would you like me to book", "shall i make the reservation"
    ]):
        return "CONFIRMATION_ASKED"

    # RECAP_DONE - Agent summarized the booking
    if any(p in agent_text for p in [
        "let me recap", "let me quickly recap", "to summarize",
        "you're looking at", "so that's", "just to confirm"
    ]) and any(w in agent_text for w in ["inr", "total", "nights"]):
        return "RECAP_DONE"

    # EMAIL_COLLECTED - Customer provided email
    if "email" in agent_text and "@" in customer_text:
        return "EMAIL_COLLECTED"

    # OCCASION_ASKED - Agent asked about special occasions
    if any(p in agent_text for p in [
        "special occasion", "celebrating", "anniversary", "birthday",
        "honeymoon", "any occasion"
    ]):
        return "OCCASION_ASKED"

    # EXPERIENCE_SHAPED - Agent discussed experiences/activities
    if any(p in agent_text for p in [
        "spa", "plantation walk", "guided", "activities", "experiences",
        "yoga", "meditation", "nature walk"
    ]) and any(w in agent_text for w in ["enjoy", "love", "recommend"]):
        return "EXPERIENCE_SHAPED"

    # RATE_QUOTED - Price has been quoted
    if any(w in agent_text for w in ["total", "inr", "comes to", "rupees"]) and re.search(r'\d{4,}', agent_text):
        return "RATE_QUOTED"

    # ROOM_POSITIONED - Room type discussed/recommended
    if any(w in agent_text for w in [
        "cottage", "luxury cottage", "suite cottage", "eden lotus",
        "heritage room", "heritage suite", "superior luxury"
    ]):
        return "ROOM_POSITIONED"

    # EXPERIENCE_INTENT - Agent asked about getaway type
    if any(p in agent_text for p in [
        "what kind of getaway", "restful", "experiential", "nature-focused",
        "how would you like to spend"
    ]):
        return "EXPERIENCE_INTENT"

    # OCCUPANCY_CHECKED - Guest count discussed
    if any(p in agent_text for p in [
        "how many guests", "how many people", "any children",
        "children traveling", "adults", "occupancy"
    ]) and any(w in customer_text for w in ["adult", "people", "guests", "child", "children", "2", "3", "4"]):
        return "OCCUPANCY_CHECKED"

    # DATES_PROVIDED - Travel dates discussed
    if any(w in customer_text for w in [
        "night", "nights", "tomorrow", "monday", "tuesday", "wednesday",
        "thursday", "friday", "saturday", "sunday", "december", "january",
        "february", "march", "today", "next week", "this weekend"
    ]):
        return "DATES_PROVIDED"

    # RESORT_SELECTED - Resort choice made
    if any(w in customer_text for w in ["coorg", "kodai"]):
        return "RESORT_SELECTED"

    # PHONE_COLLECTED - Phone number provided
    if re.search(r"\d{5,}", customer_text.replace(" ", "")):
        return "PHONE_COLLECTED"

    # NAME_COLLECTED - Name has been provided
    if len(transcripts) > 3 and "name" in agent_text:
        # Check if there's substantial customer text after name was asked
        for i, t in enumerate(transcripts):
            if t["role"] == "agent" and "name" in t["content"].lower():
                # Check if customer responded after this
                if any(t2["role"] == "customer" and len(t2["content"]) > 3
                       for t2 in transcripts[i+1:]):
                    return "NAME_COLLECTED"

    return "GREETING"


def get_stage_progress(stage: str) -> Tuple[int, int]:
    """
    Get the progress of the conversation as (current_step, total_steps).

    Args:
        stage: The current conversation stage

    Returns:
        Tuple of (current_step, total_steps)
    """
    if stage in CONVERSATION_STEPS:
        return (CONVERSATION_STEPS.index(stage) + 1, len(CONVERSATION_STEPS))
    return (0, len(CONVERSATION_STEPS))


def get_failed_at_description(
    stage: str,
    transcripts: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    Get a human-readable description of where the conversation failed.
    Analyzes the actual conversation to provide meaningful context.

    Args:
        stage: The conversation stage where failure occurred
        transcripts: Optional list of conversation transcripts for detailed analysis

    Returns:
        Human-readable failure description based on what actually happened
    """
    if not transcripts or len(transcripts) < 2:
        return "Conversation ended prematurely - no meaningful interaction"

    # Analyze the conversation
    agent_messages = [t for t in transcripts if t["role"] == "agent"]
    customer_messages = [t for t in transcripts if t["role"] == "customer"]

    agent_text = " ".join(t["content"].lower() for t in agent_messages)
    last_agent = agent_messages[-1]["content"] if agent_messages else ""
    last_customer = customer_messages[-1]["content"] if customer_messages else ""

    # 1. Check for invalid booking number
    valid_booking_number = extract_booking_number(transcripts)
    raw_booking_number = extract_raw_booking_number(transcripts)
    if raw_booking_number and not valid_booking_number:
        # Special case: agent literally said "number" instead of a booking number
        if raw_booking_number.lower() == "number":
            return "Agent said 'number' instead of providing actual booking number"
        return f"Agent provided invalid booking number '{raw_booking_number}'"

    # 2. Check for technical/system issues
    technical_patterns = [
        ("technical issue", "Technical issue with booking system"),
        ("technical hitch", "Technical hitch encountered"),
        ("system issue", "System issue prevented booking"),
        ("unable to complete", "Agent unable to complete booking"),
        ("unable to finalize", "Agent unable to finalize booking"),
        ("cannot complete", "Agent could not complete booking"),
        ("cannot finalize", "Agent could not finalize booking"),
        ("preventing me from", "System preventing booking completion"),
        ("call us back", "Agent asked customer to call back later"),
        ("call back later", "Agent asked customer to call back later"),
    ]

    for pattern, message in technical_patterns:
        if pattern in agent_text:
            return message

    # 3. Check if agent went silent (no agent response after customer message)
    if customer_messages and agent_messages:
        # Find time gap or lack of response
        last_customer_idx = max(i for i, t in enumerate(transcripts) if t["role"] == "customer")
        last_agent_idx = max(i for i, t in enumerate(transcripts) if t["role"] == "agent")

        if last_customer_idx > last_agent_idx:
            # Customer spoke last, agent didn't respond
            return "Agent stopped responding after customer's last message"

    # 4. Check for customer declining or ending conversation
    customer_text = " ".join(t["content"].lower() for t in customer_messages)
    decline_patterns = [
        "no thank", "don't want", "not interested", "cancel", "never mind",
        "changed my mind", "not now", "maybe later", "let me think",
    ]

    if any(pattern in customer_text for pattern in decline_patterns):
        return "Customer declined to proceed with booking"

    # 5. Analyze what actually went wrong based on stage and last messages
    message_count = len(transcripts)

    # Very short conversations
    if message_count < 5:
        return f"Conversation ended after only {message_count} messages - agent or customer disconnected"

    # Check for repetitive patterns (agent stuck in loop)
    if len(agent_messages) >= 3:
        last_three = [t["content"].lower()[:50] for t in agent_messages[-3:]]
        if len(set(last_three)) == 1:
            return "Agent stuck repeating the same message"

    # 6. Provide context-aware descriptions based on stage
    stage_context = {
        "GREETING": f"Conversation stalled during initial greeting ({message_count} messages)",
        "NAME_COLLECTED": "Agent collected name but failed to ask for phone number",
        "PHONE_COLLECTED": "Agent collected phone but failed to ask which resort",
        "RESORT_SELECTED": "Agent confirmed resort but didn't ask for travel dates",
        "DATES_PROVIDED": "Agent got dates but didn't check guest count/occupancy",
        "OCCUPANCY_CHECKED": "Agent checked occupancy but didn't discuss experience preferences",
        "EXPERIENCE_INTENT": "Agent discussed preferences but didn't recommend a room",
        "ROOM_POSITIONED": "Agent positioned room but didn't provide pricing",
        "RATE_QUOTED": "Agent quoted price but conversation stalled before confirmation",
        "EXPERIENCE_SHAPED": "Agent discussed experiences but didn't collect email",
        "OCCASION_ASKED": "Agent asked about occasions but didn't collect email",
        "EMAIL_COLLECTED": "Agent collected email but didn't confirm the booking",
        "RECAP_DONE": "Agent recapped details but didn't ask for final confirmation",
        "CONFIRMATION_ASKED": "Agent asked for confirmation but customer didn't respond or declined",
    }

    return stage_context.get(stage, f"Conversation incomplete at {stage} stage ({message_count} messages)")


def is_call_ended(transcripts: List[Dict[str, str]]) -> bool:
    """
    Check if the call has naturally ended.

    Args:
        transcripts: List of conversation transcripts

    Returns:
        True if the call appears to have ended naturally
    """
    if len(transcripts) < 3:
        return False

    # Get the last few messages
    recent_messages = transcripts[-5:] if len(transcripts) >= 5 else transcripts
    recent_agent = " ".join(
        t["content"].lower() for t in recent_messages if t["role"] == "agent"
    )
    recent_customer = " ".join(
        t["content"].lower() for t in recent_messages if t["role"] == "customer"
    )

    # Customer explicitly ended the call
    customer_endings = [
        "goodbye", "bye", "good bye", "bye bye",
        "thank you for your help", "thanks for your help",
        "i'll call back", "call you back",
    ]

    # Agent politely ended or acknowledged ending
    agent_endings = [
        "have a wonderful", "have a great", "have a lovely",
        "thank you for calling", "goodbye", "take care",
        "enjoy your stay", "look forward to",
        "i understand", "i apologize",
        "email you all the details", "email you the details",
    ]

    # Check if customer said goodbye/ended call
    customer_ended = any(p in recent_customer for p in customer_endings)

    # If customer ended, consider it a natural ending
    if customer_ended:
        return True

    # Traditional ending: both parties exchanged pleasantries
    agent_acknowledged = any(p in recent_agent for p in agent_endings)
    return customer_ended or (agent_acknowledged and customer_ended)


def validate_stage_progression(transcripts: List[Dict[str, str]]) -> Tuple[bool, Optional[str]]:
    """
    Validate that conversation stages follow logical progression.
    Detects if stages skip or jump backwards unexpectedly.
    
    Args:
        transcripts: List of conversation transcripts
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if progression is valid
        - error_message: Description of the issue if invalid, None otherwise
    """
    if not transcripts:
        return True, None
    
    # Track conversation progression through stages
    current_stage_index = -1
    seen_stages = []
    
    # Sample the conversation at different points to track progression
    sample_points = [
        len(transcripts) // 4,
        len(transcripts) // 2,
        3 * len(transcripts) // 4,
        len(transcripts) - 1
    ]
    
    for i in sample_points:
        if i >= len(transcripts):
            continue
            
        # Get stage at this point
        sample_transcripts = transcripts[:i+1]
        stage = get_conversation_stage(sample_transcripts)
        seen_stages.append(stage)
        
        # Get stage index
        if stage in CONVERSATION_STEPS:
            stage_index = CONVERSATION_STEPS.index(stage)
            
            # Check for backwards progression (excluding BOOKING_CONFIRMED)
            if stage != "BOOKING_CONFIRMED" and stage_index < current_stage_index:
                return False, f"Stage regressed from {CONVERSATION_STEPS[current_stage_index]} to {stage}"
            
            # Check for unrealistic jumps (skipping more than 3 stages)
            if current_stage_index >= 0 and stage_index - current_stage_index > 4:
                skipped = CONVERSATION_STEPS[current_stage_index+1:stage_index]
                return False, f"Unrealistic jump from {CONVERSATION_STEPS[current_stage_index]} to {stage}, skipping {len(skipped)} stages"
            
            current_stage_index = max(current_stage_index, stage_index)
    
    # If we reached BOOKING_CONFIRMED, validate we went through key stages
    final_stage = seen_stages[-1] if seen_stages else "GREETING"
    
    if final_stage == "BOOKING_CONFIRMED":
        required_stages = ["NAME_COLLECTED", "PHONE_COLLECTED", "RESORT_SELECTED", "DATES_PROVIDED"]
        missing_required = []
        
        for required in required_stages:
            # Check if this stage appeared at any sample point or in final state
            if required not in seen_stages:
                # Double-check by getting stage for full conversation
                full_stage = get_conversation_stage(transcripts)
                if full_stage != "BOOKING_CONFIRMED":
                    missing_required.append(required)
        
        if missing_required:
            return False, f"Booking confirmed but missing required stages: {', '.join(missing_required)}"
    
    return True, None


def get_stage_with_validation(transcripts: List[Dict[str, str]]) -> Tuple[str, Optional[str]]:
    """
    Get conversation stage with progression validation.
    
    Args:
        transcripts: List of conversation transcripts
        
    Returns:
        Tuple of (stage, validation_warning)
        - stage: The detected conversation stage
        - validation_warning: Warning message if progression is suspicious, None otherwise
    """
    stage = get_conversation_stage(transcripts)
    is_valid, error_msg = validate_stage_progression(transcripts)
    
    warning = None
    if not is_valid:
        warning = f"Stage progression issue: {error_msg}"
    
    return stage, warning
