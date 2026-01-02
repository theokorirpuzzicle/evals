"""
Conversation sanity checks to detect anomalies and issues.
Validates conversation structure, message patterns, and overall health.
"""

from typing import List, Dict, Tuple, Optional
import re


def check_conversation_sanity(transcripts: List[Dict[str, str]]) -> Tuple[bool, List[str]]:
    """
    Perform sanity checks on conversation structure and content.
    
    Args:
        transcripts: List of conversation messages
        
    Returns:
        Tuple of (is_sane, warnings)
        - is_sane: True if conversation passes all critical checks
        - warnings: List of warning messages for issues found
    """
    warnings = []
    is_sane = True
    
    if not transcripts:
        return False, ["Conversation is empty - no messages"]
    
    # Check 1: Minimum message count
    if len(transcripts) < 4:
        warnings.append(f"Very short conversation ({len(transcripts)} messages) - may indicate early termination")
        is_sane = False
    
    # Check 2: Alternating turns
    turn_issues = check_turn_alternation(transcripts)
    if turn_issues:
        warnings.extend(turn_issues)
        is_sane = False
    
    # Check 3: Message content quality
    content_issues = check_message_content_quality(transcripts)
    if content_issues:
        warnings.extend(content_issues)
    
    # Check 4: Agent/customer balance
    balance_issues = check_speaker_balance(transcripts)
    if balance_issues:
        warnings.extend(balance_issues)
    
    # Check 5: Repetition detection
    repetition_issues = check_repetition(transcripts)
    if repetition_issues:
        warnings.extend(repetition_issues)
    
    # Check 6: Conversation length reasonableness
    length_issues = check_conversation_length(transcripts)
    if length_issues:
        warnings.extend(length_issues)
    
    return is_sane, warnings


def check_turn_alternation(transcripts: List[Dict[str, str]]) -> List[str]:
    """Check if speakers alternate properly."""
    issues = []
    consecutive_same_speaker = 0
    last_speaker = None
    
    for i, t in enumerate(transcripts):
        speaker = t.get("role", "unknown")
        
        if speaker == last_speaker:
            consecutive_same_speaker += 1
            if consecutive_same_speaker >= 3:
                issues.append(f"Speaker {speaker} spoke {consecutive_same_speaker + 1} times in a row")
        else:
            consecutive_same_speaker = 0
        
        last_speaker = speaker
    
    return issues


def check_message_content_quality(transcripts: List[Dict[str, str]]) -> List[str]:
    """Check for garbled, empty, or nonsensical messages."""
    issues = []
    
    for i, t in enumerate(transcripts):
        content = t.get("content", "")
        role = t.get("role", "unknown")
        
        if not content or len(content.strip()) == 0:
            issues.append(f"Empty message from {role}")
            continue
        
        if len(content.strip()) < 2:
            issues.append(f"Suspiciously short message from {role}")
    
    return issues


def check_speaker_balance(transcripts: List[Dict[str, str]]) -> List[str]:
    """Check if agent and customer have reasonable message balance."""
    issues = []
    
    agent_count = sum(1 for t in transcripts if t.get("role") == "agent")
    customer_count = sum(1 for t in transcripts if t.get("role") == "customer")
    
    if agent_count == 0:
        issues.append("No agent messages found")
    elif customer_count == 0:
        issues.append("No customer messages found")
    
    return issues


def check_repetition(transcripts: List[Dict[str, str]]) -> List[str]:
    """Detect if agent or customer is stuck repeating the same message."""
    issues = []
    
    agent_messages = [t["content"].lower()[:100] for t in transcripts if t.get("role") == "agent"]
    if len(agent_messages) >= 3:
        last_three = agent_messages[-3:]
        if len(set(last_three)) == 1:
            issues.append("Agent stuck repeating same message")
    
    return issues


def check_conversation_length(transcripts: List[Dict[str, str]]) -> List[str]:
    """Check if conversation length is reasonable for a booking flow."""
    issues = []
    
    message_count = len(transcripts)
    
    if message_count > 100:
        issues.append(f"Unusually long conversation ({message_count} messages)")
    elif message_count < 10:
        issues.append(f"Unusually short conversation ({message_count} messages)")
    
    return issues
