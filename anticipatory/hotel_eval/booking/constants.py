"""
Constants for booking detection and conversation flow tracking.
"""

# Agent conversation flow steps (from agent-prompt.txt)
# Maps to the 13-step agent conversation flow
CONVERSATION_STEPS = [
    "GREETING",           # Step 1: Initial greeting
    "NAME_COLLECTED",     # Step 1: Full name obtained
    "PHONE_COLLECTED",    # Step 2: Mobile number obtained
    "RESORT_SELECTED",    # Step 3: Coorg or Kodai chosen
    "DATES_PROVIDED",     # Step 4: Travel dates confirmed
    "OCCUPANCY_CHECKED",  # Step 5: Guest count and children checked
    "EXPERIENCE_INTENT",  # Step 6: Restful vs experiential preference
    "ROOM_POSITIONED",    # Step 7: Room type recommended
    "RATE_QUOTED",        # Step 9: Price quoted with value framing
    "EXPERIENCE_SHAPED",  # Step 10: Optional experience shaping
    "OCCASION_ASKED",     # Step 11: Special occasions checked
    "EMAIL_COLLECTED",    # Step 12: Email address obtained
    "RECAP_DONE",         # Step 13: Booking details recapped
    "CONFIRMATION_ASKED", # Step 13: "Shall I go ahead?" asked
    "BOOKING_CONFIRMED",  # Booking confirmed with number (SUCCESS)
]

# Stage descriptions for human-readable failure messages
STAGE_DESCRIPTIONS = {
    "GREETING": "Failed at initial greeting - conversation didn't start properly",
    "NAME_COLLECTED": "Failed after name collection - didn't progress to phone",
    "PHONE_COLLECTED": "Failed after phone collection - didn't select resort",
    "RESORT_SELECTED": "Failed after resort selection - didn't provide dates",
    "DATES_PROVIDED": "Failed after dates - didn't check occupancy",
    "OCCUPANCY_CHECKED": "Failed after occupancy check - didn't discuss experience intent",
    "EXPERIENCE_INTENT": "Failed after experience intent - didn't position room",
    "ROOM_POSITIONED": "Failed after room positioning - didn't quote rate",
    "RATE_QUOTED": "Failed after rate quote - didn't shape experience or proceed",
    "EXPERIENCE_SHAPED": "Failed after experience shaping - didn't ask about occasions",
    "OCCASION_ASKED": "Failed after occasion question - didn't collect email",
    "EMAIL_COLLECTED": "Failed after email - didn't recap booking",
    "RECAP_DONE": "Failed after recap - didn't ask for confirmation",
    "CONFIRMATION_ASKED": "Customer declined or didn't confirm - no booking made",
    "BOOKING_CONFIRMED": "Success - booking confirmed with number",
}
