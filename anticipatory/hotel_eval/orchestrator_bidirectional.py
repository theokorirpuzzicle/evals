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
import wave
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path

from anticipatory.hotel_eval.config import (
    GEMINI_API_KEY, GEMINI_MODEL,
    VOICE_AGENT_WS_URL, SILENCE_20MS,
    DEFAULT_TIMEOUT, INACTIVITY_TIMEOUT
)
from anticipatory.hotel_eval.audio_mixer import AudioMixer
from anticipatory.hotel_eval.booking import (
    extract_booking_number, is_booking_confirmed,
    get_conversation_stage, is_call_ended
)
from anticipatory.hotel_eval.prompt_builder import build_system_instruction
from anticipatory.hotel_eval.voice_selection import select_voice_for_customer

# Keep these for compatibility
GEMINI_API_KEY = GEMINI_API_KEY
# GEMINI_MODEL from config
GEMINI_URL = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key={GEMINI_API_KEY}"

# VOICE_AGENT_WS_URL from config


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


class HotelBookingOrchestrator:
    def __init__(self, scenario, audio_dir="audio", transcript_dir="transcripts", provider="gemini"):
        self.scenario = scenario
        self.audio_dir = audio_dir
        self.transcript_dir = transcript_dir
        self.provider = provider
        self.voice_ws = None
        self.gemini_ws = None
        self.transcripts = []
        self.audio_mixer = AudioMixer(24000)
        self.tasks = []
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
        self.silence_threshold = 2.0  # Seconds of silence before ending turn
        # Track when we last received AGENT transcription (VA speaking)
        self.last_agent_transcript_time = 0
        # Track conversation progress
        self.booking_confirmed = False

    async def send_activity_start(self):
        """Tell Gemini to start listening for input."""
        if not self.is_listening:
            try:
                # Activity signals are wrapped in realtimeInput
                await self.gemini_ws.send(
                    json.dumps({"realtimeInput": {"activityStart": {}}})
                )
                self.is_listening = True
                logger.info(">>> Sent activity_start - Gemini listening")
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
                logger.info(">>> Sent activity_end - Gemini processing")
            except Exception as e:
                logger.error(f"Failed to send activity_end: {e}")

    async def connect(self):
        # Connect to voice agent
        self.voice_ws = await websockets.connect(VOICE_AGENT_WS_URL)
        logger.info(f"Connected to voice agent at {VOICE_AGENT_WS_URL}")
        
        # Connect to Gemini
        
        self.gemini_ws = await websockets.connect(GEMINI_URL)

        # Build system instruction from scenario
        system_instruction = build_system_instruction(self.scenario)
        
        # Select voice dynamically
        selected_voice = select_voice_for_customer(self.scenario)
        logger.info(f"Selected voice: {selected_voice} for customer {self.scenario.get('customer', {}).get('name', 'Unknown')}")

        setup_message = {
            "setup": {
                "model": f"models/{GEMINI_MODEL}",
                "generation_config": {
                    "response_modalities": ["AUDIO"],
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {"voice_name": selected_voice}
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
                    "parts": [{"text": system_instruction}]
                },
            }
        }

        await self.gemini_ws.send(json.dumps(setup_message))
        logger.info("Waiting for Gemini setup...")

        try:

            async def wait_for_setup():
                async for raw in self.gemini_ws:
                    try:
                        data = json.loads(raw)
                        logger.info(f"Gemini msg: {list(data.keys())}")
                        if "setupComplete" in data:
                            self.gemini_ready.set()
                            return
                    except json.JSONDecodeError:
                        continue

            await asyncio.wait_for(wait_for_setup(), timeout=10)
            logger.info("Connected to Gemini")
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
                        logger.info(
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
                        logger.info(f"VA event: {event_type}")

                        # "clear" event means VA detected user speaking (Gemini's audio arrived)
                        if event_type == "clear":
                            logger.info("VA received our audio (clear event)")

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
                        logger.info("Gemini turn complete")
                        self.gemini_speaking = False
                        self.gemini_done_time = time.monotonic()

                    if server_content.get("interrupted"):
                        logger.info("Gemini interrupted")
                        self.gemini_speaking = False
                        self.gemini_done_time = time.monotonic()

                    if "outputTranscription" in server_content:
                        tx = server_content["outputTranscription"].get("text", "")
                        if tx:
                            logger.info(f"CUSTOMER: {tx}")
                            self.transcripts.append(("customer", tx))

                    if "inputTranscription" in server_content:
                        tx = server_content["inputTranscription"].get("text", "")
                        if tx:
                            logger.info(f"AGENT: {tx}")
                            self.transcripts.append(("agent", tx))
                            # Track when VA is speaking (for silence detection)
                            self.last_agent_transcript_time = time.monotonic()

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
                                        logger.info(
                                            f"Gemini audio {self.response_count}"
                                        )
                                    audio_24k = base64.b64decode(audio_b64)
                                    # Record customer audio
                                    self.audio_mixer.add_customer_audio(audio_24k, time.monotonic())
                                    
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
                    logger.info(
                        f"Detected {silence_duration:.1f}s silence (transcript: {time_since_transcript:.1f}s) - sending activity_end"
                    )
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
                    logger.info("Echo cleared - restarting listening")
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

    async def watchdog(self):
        """Monitor for timeout and booking confirmation."""
        while not self.va_disconnected:
            await asyncio.sleep(2)

            if time.monotonic() - self.last_activity_time > 90:
                logger.info("Timeout - no activity for 90s")
                return

            # Check for booking confirmation in transcripts
            full_text = " ".join(t[1].lower() for t in self.transcripts)

            # Look for confirmation indicators (English and Hindi/Hinglish)
            if any(
                phrase in full_text
                for phrase in [
                    "booking is confirmed",
                    "reservation is confirmed",
                    "booking has been confirmed",
                    "successfully booked",
                    "booking reference",
                    "confirmation number",
                    "booking number",
                    "your booking",
                    "confirm your booking",
                    "proceed with the booking",
                    "finalize",
                    "bk-",  # Booking ID prefix
                ]
            ):
                logger.info("🎉 BOOKING CONFIRMED!")
                self.booking_confirmed = True
                await asyncio.sleep(5)
                return

    def save_audio_files(self, scenario_id, timestamp):
        Path(self.audio_dir).mkdir(parents=True, exist_ok=True)
        Path(self.transcript_dir).mkdir(parents=True, exist_ok=True)
        base_name = f'{timestamp}_{scenario_id}'
        saved_files = {}
        combined_audio = self.audio_mixer.mix_audio()
        if combined_audio:
            audio_file = os.path.join(self.audio_dir, f'{base_name}_conversation.wav')
            with wave.open(audio_file, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(combined_audio)
            saved_files['conversation'] = f'{base_name}_conversation.wav'
        transcript_file = os.path.join(self.transcript_dir, f'{base_name}_transcript.txt')
        with open(transcript_file, 'w', encoding='utf-8') as tf:
            tf.write('Scenario: ' + self.scenario.get('name', 'Unknown') + chr(10))
            tf.write('Date: ' + datetime.now().isoformat() + chr(10) + chr(10))
            for idx, (role, text) in enumerate(self.transcripts, 1):
                prefix = 'CUSTOMER' if role == 'customer' else 'AGENT'
                tf.write(f'[{idx}] {prefix}: {text}' + chr(10))
        saved_files['transcript'] = f'{base_name}_transcript.txt'
        return saved_files

    def check_success_criteria(self):
        """Check if scenario success criteria are met."""
        # Convert transcripts to dict format
        transcript_dicts = [{'role': role, 'content': text} for role, text in self.transcripts]
        return {
            'booking_confirmed': is_booking_confirmed(transcript_dicts),
            'booking_number': extract_booking_number(transcript_dicts),
            'conversation_stage': get_conversation_stage(transcript_dicts),
            'call_ended': is_call_ended(transcript_dicts),
        }

    async def run(self, timeout=DEFAULT_TIMEOUT, text_mode=False):
        """Run the evaluation scenario."""
        start_time = datetime.now()
        timestamp = start_time.strftime('%Y%m%d_%H%M%S')
        scenario_id = self.scenario.get('id', 'unknown')
        error = None
        saved_files = {}

        try:
            if text_mode:
                raise NotImplementedError('Text mode not supported in WebSocket orchestrator')

            # Set start time for audio mixer
            self.audio_mixer.set_start_time(time.monotonic())

            # Run the bidirectional connection
        await self.connect()

        except Exception as e:
            error = str(e)
            logger.error(f'❌ Error: {e}')
        finally:
            # Save files
            saved_files = self.save_audio_files(scenario_id, timestamp)

        duration = (datetime.now() - start_time).seconds
        success_results = self.check_success_criteria()

        return {
            'scenario_id': scenario_id,
            'scenario_name': self.scenario.get('name', 'unnamed'),
            'duration_seconds': duration,
            'transcript_count': len(self.transcripts),
            'transcripts': [{'role': role, 'content': text} for role, text in self.transcripts],
            'success_results': success_results,
            'error': error,
            'audio_files': saved_files,
        }


    if not GEMINI_API_KEY:
        print("Set GEMINI_API_KEY or GOOGLE_API_KEY")
    else:
        asyncio.run(VoiceBridge().run())
