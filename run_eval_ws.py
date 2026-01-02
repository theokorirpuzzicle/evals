#!/usr/bin/env python3
"""
Simple eval runner using bidirectional WebSocket pattern.
"""
import asyncio
import json
import logging
import sys

# Add the bidirectional test logic
import bidirectional_test

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

async def run_test():
    """Run a test with bidirectional pattern."""
    bridge = bidirectional_test.VoiceBridge()
    await bridge.run()
    
    # Show results
    print("\n" + "="*60)
    print("EVAL RESULTS")
    print("="*60)
    print(f"Total messages: {len(bridge.transcripts)}")
    print(f"Booking confirmed: {bridge.booking_confirmed}")
    print("\nTranscript:")
    for role, text in bridge.transcripts:
        prefix = "AGENT" if role == "agent" else "CUSTOMER"
        print(f"  {prefix}: {text}")

if __name__ == "__main__":
    asyncio.run(run_test())
