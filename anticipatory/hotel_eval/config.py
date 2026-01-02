"""

Configuration constants for the Hotel Booking Evaluation System.

"""



import os



# ---------------- API CONFIG ----------------

BACKEND_URL = "https://agent.caller.anticipatory.com"



# Voice Agent WebSocket URL (for direct connection)

VOICE_AGENT_WS_URL = os.getenv("VOICE_AGENT_WS_URL", "wss://staging-caller.anticipatory.com/ws/booking")

# For local testing use: "ws://localhost:8000/ws/booking"



# Gemini settings

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

GEMINI_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"



# OpenAI settings

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

OPENAI_MODEL = "gpt-4o-realtime-preview"



# Default provider (gemini or openai)

DEFAULT_PROVIDER = "gemini"



# ---------------- TIMEOUTS ----------------

DEFAULT_TIMEOUT = 600  # 10 minutes

INACTIVITY_TIMEOUT = 45  # Detect stalls faster

AGENT_RESPONSE_TIMEOUT = 20  # Seconds to wait before customer prompts agent (keep-alive)

MAX_KEEPALIVE_ATTEMPTS = 3  # Number of times customer will try to re-engage before giving up



# ---------------- AUDIO SETTINGS ----------------



AGENT_SAMPLE_RATE = 16000

CUSTOMER_SAMPLE_RATE = 24000

OUTPUT_SAMPLE_RATE = 24000



# 20ms of silence at 16kHz = 320 samples = 640 bytes (for keeping connection alive)

SILENCE_20MS = bytes([0, 0]) * 320


# ---------------- FALSE POSITIVE WORDS ----------------

# Words that should NOT be considered booking numbers

FALSE_POSITIVE_WORDS = {

    # Common words

    "the", "a", "is", "your", "plus", "and", "for", "to", "of", "in", "on", "at",

    "that", "this", "with", "you", "are", "was", "been", "have", "has", "had",

    "will", "would", "could", "should", "may", "might", "must", "can", "do", "does",

    # Filler/polite words

    "correctly", "certainly", "absolutely", "definitely", "please", "kindly",

    "thank", "thanks", "sorry", "apologies", "welcome", "hello", "goodbye",

    # Contact info labels

    "phone", "mobile", "email", "address", "name", "guest", "guests",

    # Location names

    "coorg", "kodai", "tamara", "resort", "resorts", "cottage", "cottages", "room", "rooms",

    # Time words

    "january", "february", "march", "april", "may", "june", "july", "august",

    "september", "october", "november", "december",

    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",

    "today", "tomorrow", "yesterday", "nights", "night", "days", "day", "week",

    # Room types

    "luxury", "suite", "heritage", "superior", "deluxe", "premium",

    # Currency/price words

    "indian", "india", "inr", "rupees", "amount", "total", "price",

    # Generic words

    "integrated", "process", "system", "details", "information",

    "moment", "second", "minute", "shortly", "right", "away",

    "perfect", "wonderful", "lovely", "beautiful", "great", "good",

    "checking", "checkin", "checkout", "staying", "travel", "traveling",

}

