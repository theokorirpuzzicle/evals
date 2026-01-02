#!/usr/bin/env python3
"""Voice-to-voice test using Gemini - real-time streaming with manual VAD control."""

import asyncio
import json
import logging
import os
import base64
import time
import struct
import websockets

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
GEMINI_URL = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key={GEMINI_API_KEY}"

VOICE_AGENT_URL = "wss://staging-caller.anticipatory.com/ws/booking"
# VOICE_AGENT_URL = "wss://caller.anticipatory.com/ws/booking"
# VOICE_AGENT_URL = "ws://localhost:8000/ws/booking"
# 20ms of silence at 16kHz = 320 samples = 640 bytes
SILENCE_20MS = b"\x00\x00" * 320

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


def resample_24k_to_16k(audio_24k: bytes) -> bytes:
    """Downsample 24kHz to 16kHz for VA."""
    samples = struct.unpack(f"<{len(audio_24k) // 2}h", audio_24k)
    result = []
    for i in range(0, len(samples) - 2, 3):
        result.append(samples[i])
        result.append(samples[i + 1])
    return struct.pack(f"<{len(result)}h", *result)


def is_speech(audio_data: bytes) -> bool:
    """Check if audio contains speech (not silence)."""
    if len(audio_data) < 4:
        return False
    samples = struct.unpack(f"<{len(audio_data) // 2}h", audio_data)
    # Check RMS energy - speech has higher energy than silence
    energy = sum(abs(s) for s in samples[:100]) / 100
    return energy > 200  # Lower threshold to catch quieter speech


def normalize_text(text: str) -> str:
    """Normalize text capitalization - capitalize first letter of each sentence."""
    if not text:
        return text
    # Split by periods, capitalize each sentence
    sentences = text.split('. ')
    normalized = '. '.join(s.strip().capitalize() for s in sentences if s.strip())
    return normalized


class VoiceBridge:
    def __init__(self):
        self.voice_ws = None
        self.gemini_ws = None
        self.transcripts = []
        self.last_activity_time = time.monotonic()
        self.va_disconnected = False
        self.gemini_ready = asyncio.Event()
        self.response_count = 0
        self.gemini_speaking = False
        self.gemini_done_time = 0
        # Manual VAD control
        self.is_listening = False
        self.last_speech_time = 0
        self.last_audio_to_va = 0
        self.silence_threshold = 3.5  # Seconds of silence before ending turn (increased for patience)
        # Track when we last received AGENT transcription (VA speaking)
        self.last_agent_transcript_time = 0
        # Track conversation progress
        self.booking_confirmed = False
        # Keep-alive tracking
        self.last_agent_activity = time.monotonic()
        self.keepalive_attempts = 0
        self.max_keepalive_attempts = 2
        self.keepalive_timeout = 15  # seconds before first prompt
        self.keepalive_retry_timeout = 10  # seconds between retries
        # Transcript buffering for cleaner logging
        self.customer_buffer = ""
        self.agent_buffer = ""

    async def send_activity_start(self):
        """Tell Gemini to start listening for input."""
        if not self.is_listening:
            try:
                # Activity signals are wrapped in realtimeInput
                await self.gemini_ws.send(
                    json.dumps({"realtimeInput": {"activityStart": {}}})
                )
                self.is_listening = True
                logger.debug(">>> Sent activity_start - Gemini listening")
            except Exception as e:
                logger.error(f"Failed to send activity_start: {e}")

    async def send_activity_end(self):
        """Tell Gemini to stop listening and process input."""
        if self.is_listening:
            try:
                await self.gemini_ws.send(
                    json.dumps({"realtimeInput": {"activityEnd": {}}})
                )
                self.is_listening = False
                logger.debug(">>> Sent activity_end - Gemini processing")
            except Exception as e:
                logger.error(f"Failed to send activity_end: {e}")

    async def send_keepalive_prompt(self):
        """Send a text prompt to make customer say 'Hello?' to re-engage agent."""
        try:
            # Send text input to trigger Gemini to speak
            await self.gemini_ws.send(
                json.dumps({
                    "clientContent": {
                        "turns": [{
                            "role": "user",
                            "parts": [{"text": "Say 'Hello?' to check if the agent is still there."}]
                        }],
                        "turnComplete": True
                    }
                })
            )
            logger.info("🔔 Sent keep-alive prompt - customer will say 'Hello?'")
        except Exception as e:
            logger.error(f"Failed to send keep-alive prompt: {e}")

    async def connect(self):
        # Production requires "media" subprotocol, staging doesn't
        if "caller.anticipatory.com" in VOICE_AGENT_URL:
            self.voice_ws = await websockets.connect(VOICE_AGENT_URL, subprotocols=["media"])
        else:
            self.voice_ws = await websockets.connect(VOICE_AGENT_URL)
        self.gemini_ws = await websockets.connect(GEMINI_URL)

        setup_message = {
            "setup": {
                "model": f"models/{GEMINI_MODEL}",
                "generation_config": {
                    "response_modalities": ["AUDIO"],
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {"voice_name": "Kore"}
                        }
                    },
                    "thinking_config": {"thinking_budget": 0},
                },
                # Disable automatic VAD - we control turn-taking manually
                "realtime_input_config": {
                    "automatic_activity_detection": {"disabled": True}
                },
                "output_audio_transcription": {},
                "input_audio_transcription": {},
                "system_instruction": {
                    "parts": [
                        {
                            "text": """You are Rajesh Kumar calling to book a hotel room.
Answer ONE question at a time. Keep responses SHORT (1-2 sentences).

Your info (give only when asked):
- Name: Rajesh Kumar
- Phone: 9876543210
- Check-in: Tomorrow
- Nights: 3
- Guests: 2 adults
- Room: Deluxe
- Hotel: Tamara Coorg

Listen to the hotel agent and respond naturally."""
                        }
                    ]
                },
            }
        }

        await self.gemini_ws.send(json.dumps(setup_message))
        logger.debug("Waiting for Gemini setup...")

        try:

            async def wait_for_setup():
                async for raw in self.gemini_ws:
                    try:
                        data = json.loads(raw)
                        logger.debug(f"Gemini msg: {list(data.keys())}")
                        if "setupComplete" in data:
                            self.gemini_ready.set()
                            return
                    except json.JSONDecodeError:
                        continue

            await asyncio.wait_for(wait_for_setup(), timeout=10)
            logger.debug("Connected to Gemini")
        except asyncio.TimeoutError:
            raise RuntimeError("Gemini setup timed out")

    async def handle_voice_agent(self):
        """Forward VA audio to Gemini in real-time."""
        chunk_count = 0

        # Start listening immediately for VA greeting
        await self.send_activity_start()

        try:
            async for msg in self.voice_ws:
                self.last_activity_time = time.monotonic()
                current_time = time.monotonic()

                if isinstance(msg, bytes):
                    chunk_count += 1

                    # Check if this is actual speech
                    has_speech = is_speech(msg)
                    if has_speech:
                        self.last_speech_time = current_time

                    # Only forward audio when we're in listening mode
                    if not self.is_listening:
                        continue

                    # Skip during echo window (after we sent audio to VA)
                    if (
                        self.last_audio_to_va > 0
                        and current_time - self.last_audio_to_va < 0.3
                    ):
                        continue

                    if chunk_count % 20 == 1:
                        logger.debug(
                            f"VA chunk {chunk_count} -> Gemini (speech={has_speech})"
                        )

                    # Forward audio to Gemini
                    audio_b64 = base64.b64encode(msg).decode()
                    try:
                        await self.gemini_ws.send(
                            json.dumps(
                                {
                                    "realtimeInput": {
                                        "mediaChunks": [
                                            {
                                                "mimeType": "audio/pcm;rate=16000",
                                                "data": audio_b64,
                                            }
                                        ]
                                    }
                                }
                            )
                        )
                    except:
                        pass
                else:
                    # Handle VA events (JSON messages)
                    try:
                        data = json.loads(msg)
                        event_type = data.get("type", data.get("event", "unknown"))
                        logger.debug(f"VA event: {event_type}")

                        # "clear" event means VA detected user speaking (Gemini's audio arrived)
                        if event_type == "clear":
                            logger.debug("VA received our audio (clear event)")

                    except:
                        pass

        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"VA disconnected: {e}")
            self.va_disconnected = True

    async def handle_gemini(self):
        """Handle Gemini events and forward audio to VA."""
        try:
            async for raw in self.gemini_ws:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                self.last_activity_time = time.monotonic()

                if "setupComplete" in data:
                    self.gemini_ready.set()
                    continue

                if "serverContent" in data:
                    server_content = data["serverContent"]

                    if server_content.get("turnComplete"):
                        # Log complete customer response and save to transcripts
                        if self.customer_buffer.strip():
                            # Remove Hindi/Unicode characters for cleaner logs
                            clean_text = ''.join(c for c in self.customer_buffer if ord(c) < 128 or c.isspace())
                            if clean_text.strip():
                                normalized = normalize_text(clean_text.strip())
                                logger.info(f"CUSTOMER: {normalized}")
                                # Save complete turn to transcripts (not chunks)
                                self.transcripts.append(("customer", normalized))
                            self.customer_buffer = ""
                        self.gemini_speaking = False
                        self.gemini_done_time = time.monotonic()

                    if server_content.get("interrupted"):
                        # Log any buffered customer speech before interruption
                        if self.customer_buffer.strip():
                            clean_text = ''.join(c for c in self.customer_buffer if ord(c) < 128 or c.isspace())
                            if clean_text.strip():
                                normalized = normalize_text(clean_text.strip())
                                logger.info(f"CUSTOMER (interrupted): {normalized}")
                                # Save interrupted turn to transcripts
                                self.transcripts.append(("customer", normalized))
                            self.customer_buffer = ""
                        self.gemini_speaking = False
                        self.gemini_done_time = time.monotonic()

                    if "outputTranscription" in server_content:
                        tx = server_content["outputTranscription"].get("text", "")
                        if tx:
                            self.customer_buffer += tx
                            # Don't append chunks - wait for turnComplete

                    if "inputTranscription" in server_content:
                        tx = server_content["inputTranscription"].get("text", "")
                        if tx:
                            self.agent_buffer += tx
                            # Don't append chunks - we'll save complete sentences
                            # Track when VA is speaking (for silence detection)
                            self.last_agent_transcript_time = time.monotonic()
                            # Reset keep-alive tracking when agent speaks
                            self.last_agent_activity = time.monotonic()
                            self.keepalive_attempts = 0

                    model_turn = server_content.get("modelTurn", {})
                    for part in model_turn.get("parts", []):
                        if "inlineData" in part:
                            inline_data = part["inlineData"]
                            if "audio" in inline_data.get("mimeType", ""):
                                audio_b64 = inline_data.get("data", "")
                                if audio_b64:
                                    self.gemini_speaking = True
                                    self.gemini_done_time = 0
                                    self.response_count += 1
                                    if self.response_count % 10 == 1:
                                        logger.debug(
                                            "Gemini audio chunk"
                                        )
                                    audio_24k = base64.b64decode(audio_b64)
                                    audio_16k = resample_24k_to_16k(audio_24k)
                                    try:
                                        await self.voice_ws.send(audio_16k)
                                        self.last_audio_to_va = time.monotonic()
                                    except:
                                        pass

        except websockets.exceptions.ConnectionClosed:
            pass

    async def silence_monitor(self):
        """Monitor for silence and send activity_end when VA stops speaking."""
        listening_start_time = 0

        while not self.va_disconnected:
            await asyncio.sleep(0.1)

            current_time = time.monotonic()

            # Track when we started listening
            if self.is_listening and listening_start_time == 0:
                listening_start_time = current_time
            elif not self.is_listening:
                listening_start_time = 0

            # If we're listening and there's been silence for threshold duration
            if self.is_listening and self.last_speech_time > 0:
                silence_duration = current_time - self.last_speech_time

                # Also check if we recently received agent transcription
                # (VA might still be speaking even if audio energy is low)
                time_since_transcript = current_time - self.last_agent_transcript_time

                # Only end if both audio AND transcription have been silent
                if (
                    silence_duration > self.silence_threshold
                    and time_since_transcript > self.silence_threshold
                ):
                    # Log complete agent response before ending activity
                    if self.agent_buffer.strip():
                        clean_text = ''.join(c for c in self.agent_buffer if ord(c) < 128 or c.isspace())
                        if clean_text.strip():
                            normalized = normalize_text(clean_text.strip())
                            logger.info(f"AGENT: {normalized}")
                            # Save complete turn to transcripts
                            self.transcripts.append(("agent", normalized))
                        self.agent_buffer = ""
                    await self.send_activity_end()
                    self.last_speech_time = 0

            # Fallback: if we've been listening for 5s without detecting ANY speech, send activity_end anyway
            # This handles cases where is_speech() fails to detect the VA's audio
            elif (
                self.is_listening
                and self.last_speech_time == 0
                and listening_start_time > 0
            ):
                listening_duration = current_time - listening_start_time
                time_since_transcript = current_time - self.last_agent_transcript_time

                if (
                    listening_duration > 5.0
                    and time_since_transcript > self.silence_threshold
                ):
                    logger.info(
                        f"Fallback: listening {listening_duration:.1f}s without speech detection - sending activity_end"
                    )
                    await self.send_activity_end()

    async def restart_listening_after_gemini(self):
        """Restart listening after Gemini finishes speaking and echo clears."""
        while not self.va_disconnected:
            await asyncio.sleep(0.1)

            # If Gemini finished speaking and we're not listening
            if self.gemini_done_time > 0 and not self.is_listening:
                current_time = time.monotonic()
                time_since_done = current_time - self.gemini_done_time
                time_since_audio = current_time - self.last_audio_to_va

                # Wait 0.5s after last audio sent for echo to clear
                if time_since_audio > 0.5 and time_since_done > 0.3:
                    logger.debug("Echo cleared - restarting listening")
                    # CRITICAL: Reset last_speech_time to prevent immediate activity_end
                    # from silence_monitor using stale timestamp
                    self.last_speech_time = 0
                    await self.send_activity_start()
                    self.gemini_done_time = 0

    async def silence_sender(self):
        """Send silence to VA to keep connection alive (only when not sending Gemini audio)."""
        while not self.va_disconnected:
            await asyncio.sleep(0.02)
            # Don't send silence while Gemini is speaking
            if not self.gemini_speaking:
                try:
                    await self.voice_ws.send(SILENCE_20MS)
                except:
                    break

    async def keep_alive_loop(self):
        """Keep Gemini WebSocket alive."""
        try:
            while not self.va_disconnected:
                await asyncio.sleep(15)
                try:
                    await self.gemini_ws.ping()
                except:
                    break
        except asyncio.CancelledError:
            pass

    async def agent_keepalive_monitor(self):
        """Monitor for agent inactivity and prompt with 'Hello?' if needed."""
        while not self.va_disconnected:
            await asyncio.sleep(1)

            current_time = time.monotonic()
            time_since_agent = current_time - self.last_agent_activity

            # Don't prompt if Gemini is currently speaking
            if self.gemini_speaking:
                continue

            # First keep-alive attempt after 15 seconds
            if self.keepalive_attempts == 0 and time_since_agent >= self.keepalive_timeout:
                logger.info(f"⏰ No agent activity for {time_since_agent:.1f}s - sending first keep-alive")
                await self.send_keepalive_prompt()
                self.keepalive_attempts = 1
                self.last_agent_activity = current_time  # Reset timer for retry

            # Second keep-alive attempt after another 10 seconds
            elif self.keepalive_attempts == 1 and time_since_agent >= self.keepalive_retry_timeout:
                logger.info(f"⏰ Still no agent activity after {time_since_agent:.1f}s - sending second keep-alive")
                await self.send_keepalive_prompt()
                self.keepalive_attempts = 2
                self.last_agent_activity = current_time  # Reset timer for final timeout

            # Give up after third timeout (10s after second attempt)
            elif self.keepalive_attempts >= self.max_keepalive_attempts and time_since_agent >= self.keepalive_retry_timeout:
                logger.info(f"❌ No agent response after {self.max_keepalive_attempts} keep-alive attempts - ending call")
                self.va_disconnected = True
                return

    async def watchdog(self):
        """Monitor for timeout and booking confirmation."""
        while not self.va_disconnected:
            await asyncio.sleep(2)

            if time.monotonic() - self.last_activity_time > 120:
                logger.warning("Timeout - no activity for 120s")
                return

            # Check for booking confirmation in transcripts
            full_text = " ".join(t[1].lower() for t in self.transcripts)

            # Look for confirmation indicators (English and Hindi/Hinglish)
            # Only confirm if there are strong confirmation phrases, not vague mentions
            if any(
                phrase in full_text
                for phrase in [
                    "booking is confirmed",
                    "reservation is confirmed",
                    "booking has been confirmed",
                    "reservation has been confirmed",
                    "successfully booked",
                    "i have confirmed your booking",
                    "your booking is confirmed",
                    "your reservation is confirmed",
                    "booking reference is",
                    "booking reference number",
                    "confirmation number is",
                    "booking number is",
                    "your booking number",
                    "bk-",  # Booking ID prefix
                ]
            ):
                logger.info("🎉 BOOKING CONFIRMED!")
                self.booking_confirmed = True
                await asyncio.sleep(5)
                return

    async def run(self):
        await self.connect()
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    self.handle_voice_agent(),
                    self.handle_gemini(),
                    self.silence_monitor(),
                    self.restart_listening_after_gemini(),
                    self.silence_sender(),
                    self.keep_alive_loop(),
                    self.agent_keepalive_monitor(),
                    self.watchdog(),
                ),
                timeout=300,
            )
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass

        #         logger.info(f"\nTRANSCRIPT ({len(self.transcripts)} messages):")
        #         for role, text in self.transcripts:
        #             prefix = "AGENT" if role == "agent" else "CUSTOMER"
        #             logger.info(f"  {prefix}: {text}")


if __name__ == "__main__":
    if not GEMINI_API_KEY:
        print("Set GEMINI_API_KEY or GOOGLE_API_KEY")
    else:
        asyncio.run(VoiceBridge().run())
