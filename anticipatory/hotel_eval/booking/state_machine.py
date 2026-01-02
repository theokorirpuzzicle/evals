"""
State machine for validating conversation flow transitions.
Ensures conversation follows expected booking flow pattern.
"""

from typing import List, Dict, Optional, Tuple
from enum import Enum
from .constants import CONVERSATION_STEPS


class ConversationState(Enum):
    """Enumeration of conversation states."""
    GREETING = "GREETING"
    NAME_COLLECTED = "NAME_COLLECTED"
    PHONE_COLLECTED = "PHONE_COLLECTED"
    RESORT_SELECTED = "RESORT_SELECTED"
    DATES_PROVIDED = "DATES_PROVIDED"
    OCCUPANCY_CHECKED = "OCCUPANCY_CHECKED"
    EXPERIENCE_INTENT = "EXPERIENCE_INTENT"
    ROOM_POSITIONED = "ROOM_POSITIONED"
    RATE_QUOTED = "RATE_QUOTED"
    EXPERIENCE_SHAPED = "EXPERIENCE_SHAPED"
    OCCASION_ASKED = "OCCASION_ASKED"
    EMAIL_COLLECTED = "EMAIL_COLLECTED"
    RECAP_DONE = "RECAP_DONE"
    CONFIRMATION_ASKED = "CONFIRMATION_ASKED"
    BOOKING_CONFIRMED = "BOOKING_CONFIRMED"


# Define valid state transitions
STATE_TRANSITIONS = {
    ConversationState.GREETING: [
        ConversationState.NAME_COLLECTED,
        ConversationState.PHONE_COLLECTED,  # Can skip name
    ],
    ConversationState.NAME_COLLECTED: [
        ConversationState.PHONE_COLLECTED,
    ],
    ConversationState.PHONE_COLLECTED: [
        ConversationState.RESORT_SELECTED,
    ],
    ConversationState.RESORT_SELECTED: [
        ConversationState.DATES_PROVIDED,
    ],
    ConversationState.DATES_PROVIDED: [
        ConversationState.OCCUPANCY_CHECKED,
        ConversationState.ROOM_POSITIONED,  # Can skip occupancy check
    ],
    ConversationState.OCCUPANCY_CHECKED: [
        ConversationState.EXPERIENCE_INTENT,
        ConversationState.ROOM_POSITIONED,  # Can skip experience intent
    ],
    ConversationState.EXPERIENCE_INTENT: [
        ConversationState.ROOM_POSITIONED,
    ],
    ConversationState.ROOM_POSITIONED: [
        ConversationState.RATE_QUOTED,
        ConversationState.EXPERIENCE_SHAPED,  # Can go directly to shaping
    ],
    ConversationState.RATE_QUOTED: [
        ConversationState.EXPERIENCE_SHAPED,
        ConversationState.OCCASION_ASKED,  # Can skip experience shaping
        ConversationState.EMAIL_COLLECTED,  # Can skip to email
    ],
    ConversationState.EXPERIENCE_SHAPED: [
        ConversationState.OCCASION_ASKED,
        ConversationState.EMAIL_COLLECTED,  # Can skip occasion
    ],
    ConversationState.OCCASION_ASKED: [
        ConversationState.EMAIL_COLLECTED,
    ],
    ConversationState.EMAIL_COLLECTED: [
        ConversationState.RECAP_DONE,
        ConversationState.CONFIRMATION_ASKED,  # Can skip recap
    ],
    ConversationState.RECAP_DONE: [
        ConversationState.CONFIRMATION_ASKED,
    ],
    ConversationState.CONFIRMATION_ASKED: [
        ConversationState.BOOKING_CONFIRMED,
    ],
    ConversationState.BOOKING_CONFIRMED: [],  # Terminal state
}


class ConversationStateMachine:
    """State machine for tracking and validating conversation flow."""
    
    def __init__(self):
        self.current_state = ConversationState.GREETING
        self.state_history = [ConversationState.GREETING]
        self.invalid_transitions = []
    
    def transition(self, new_state: ConversationState) -> bool:
        """
        Attempt to transition to a new state.
        
        Args:
            new_state: The state to transition to
            
        Returns:
            True if transition is valid, False otherwise
        """
        # Allow staying in same state
        if new_state == self.current_state:
            return True
        
        # Check if transition is valid
        valid_next_states = STATE_TRANSITIONS.get(self.current_state, [])
        
        if new_state in valid_next_states:
            self.current_state = new_state
            self.state_history.append(new_state)
            return True
        else:
            self.invalid_transitions.append((self.current_state, new_state))
            return False
    
    def validate_conversation_flow(self, stage_sequence: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate a sequence of conversation stages.
        
        Args:
            stage_sequence: List of stage names in order
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        for i, stage_name in enumerate(stage_sequence):
            try:
                state = ConversationState[stage_name]
            except KeyError:
                errors.append(f"Unknown stage '{stage_name}' at position {i}")
                continue
            
            if not self.transition(state):
                errors.append(
                    f"Invalid transition from {self.current_state.value} to {state.value} at position {i}"
                )
        
        return len(errors) == 0, errors
    
    def get_expected_next_states(self) -> List[ConversationState]:
        """Get list of valid next states from current state."""
        return STATE_TRANSITIONS.get(self.current_state, [])
    
    def is_terminal_state(self) -> bool:
        """Check if current state is terminal (conversation should end)."""
        return self.current_state == ConversationState.BOOKING_CONFIRMED
    
    def get_progress_percentage(self) -> float:
        """Calculate conversation progress as percentage."""
        try:
            current_index = CONVERSATION_STEPS.index(self.current_state.value)
            total_steps = len(CONVERSATION_STEPS)
            return (current_index + 1) / total_steps * 100
        except ValueError:
            return 0.0


def validate_conversation_with_state_machine(stages: List[str]) -> Dict[str, any]:
    """
    Validate conversation stages using state machine.
    
    Args:
        stages: List of stage names tracked through conversation
        
    Returns:
        Validation result with state machine analysis
    """
    machine = ConversationStateMachine()
    is_valid, errors = machine.validate_conversation_flow(stages)
    
    return {
        "is_valid": is_valid,
        "errors": errors,
        "final_state": machine.current_state.value,
        "progress_percentage": machine.get_progress_percentage(),
        "is_complete": machine.is_terminal_state(),
        "state_history": [s.value for s in machine.state_history],
        "invalid_transitions": [(s1.value, s2.value) for s1, s2 in machine.invalid_transitions]
    }
