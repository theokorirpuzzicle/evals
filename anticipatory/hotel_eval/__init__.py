"""
Hotel Booking Voice Agent Evaluation System

A modular system for evaluating hotel booking voice agents using
Gemini Live API to simulate customer calls.
"""

# Configuration
from .config import (
    BACKEND_URL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    DEFAULT_TIMEOUT,
    INACTIVITY_TIMEOUT,
)

# Audio processing
from .audio_mixer import AudioMixer

# Booking detection (backward compatible imports)
from .booking import (
    CONVERSATION_STEPS,
    is_valid_booking_number,
    extract_booking_number,
    is_booking_confirmed,
    get_conversation_stage,
    get_stage_progress,
    get_failed_at_description,
    is_call_ended,
)

# Prompt building
from .prompt_builder import build_system_instruction

# STT corrections
from .stt_corrections import clean_stt_errors

# Voice selection
from .voice_selection import select_voice_for_customer

# Orchestrator
# from .orchestrator import  # Commented out - using scenario runner instead HotelBookingOrchestrator

# Evaluation runner
from .evaluation import run_evaluation, list_scenarios

# Results tracking (backward compatible imports)
from .results_tracker import (
    update_results_excel,
    get_historical_stats,
    print_historical_summary,
)

__all__ = [
    # Config
    "BACKEND_URL",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "DEFAULT_TIMEOUT",
    "INACTIVITY_TIMEOUT",
    # Classes
    "AudioMixer",
    "HotelBookingOrchestrator",
    # Conversation flow
    "CONVERSATION_STEPS",
    # Booking detection functions
    "is_valid_booking_number",
    "extract_booking_number",
    "is_booking_confirmed",
    "get_conversation_stage",
    "get_stage_progress",
    "get_failed_at_description",
    "is_call_ended",
    # Prompt building
    "build_system_instruction",
    # STT corrections
    "clean_stt_errors",
    # Voice selection
    "select_voice_for_customer",
    # Evaluation
    "run_evaluation",
    "list_scenarios",
    # Results tracking
    "update_results_excel",
    "get_historical_stats",
    "print_historical_summary",
]
