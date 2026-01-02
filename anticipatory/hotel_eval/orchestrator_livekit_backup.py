"""
Main orchestrator for hotel booking evaluation scenarios.
"""

import asyncio
import json
import base64
import random
import string
import re
import wave
import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

import aiohttp
import websockets
import numpy as np

from .config import (
    BACKEND_URL, GEMINI_API_KEY, GEMINI_MODEL,
    OPENAI_API_KEY, OPENAI_MODEL,
    DEFAULT_TIMEOUT, INACTIVITY_TIMEOUT,
    AGENT_RESPONSE_TIMEOUT, MAX_KEEPALIVE_ATTEMPTS,
    AGENT_SAMPLE_RATE, OUTPUT_SAMPLE_RATE
)
from .audio_mixer import AudioMixer
from .booking import (
    extract_booking_number, extract_raw_booking_number, is_booking_confirmed,
    get_conversation_stage, is_call_ended, is_valid_booking_number
)
from .prompt_builder import build_system_instruction
from .stt_corrections import clean_stt_errors
from .voice_selection import select_voice_for_customer

logger = logging.getLogger("eval-runner")


class HotelBookingOrchestrator:
    """Orchestrates a single hotel booking evaluation scenario."""

    def __init__(self, scenario: Dict[str, Any], audio_dir: str = "audio", transcript_dir: str = "transcripts", provider: str = "gemini"):
        self.scenario = scenario
        self.audio_dir = audio_dir
        self.transcript_dir = transcript_dir
        self.provider = provider
        self.room_name: Optional[str] = None
        self.identity: Optional[str] = None
        self.ws_url: Optional[str] = None
        self.token: Optional[str] = None

        self.gemini_ws: Optional[websockets.WebSocketClientProtocol] = None
        self.room = None
        self.audio_source = None

        self.agent_connected = asyncio.Event()
        self.gemini_ready = asyncio.Event()

        self.transcripts: List[Dict[str, str]] = []
        self.tasks = []

        self.agent_transcript_buffer = ""
        self.customer_transcript_buffer = ""

        self.last_agent_transcript_time = 0
        self.last_customer_transcript_time = 0
        self.last_activity_time = 0

        self.audio_mixer = AudioMixer(OUTPUT_SAMPLE_RATE)

        self.agent_audio_chunks = 0
        self.customer_audio_chunks = 0

        self.last_agent_question = ""
        self.conversation_stalled_count = 0

        # Track agent text responses (cleaner than STT transcription)
        self.agent_text_responses: List[str] = []
        self.last_agent_text_check = 0

        # Keep-alive tracking: prompt customer to re-engage when agent is silent
        self.keepalive_attempts = 0
        self.last_keepalive_time = 0
        self.waiting_for_agent_response = False

        # Manual VAD control (like bidirectional_test.py)
        self.is_listening = False
        self.last_speech_time = 0
        self.last_audio_to_va = 0
        self.silence_threshold = 2.0
        self.gemini_speaking = False
        self.gemini_done_time = 0

    # ---------------- AUDIO SAVING ----------------

    def save_audio_files(self, scenario_id: str, timestamp: str) -> Dict[str, str]:
        """Save combined conversation audio and transcript to separate folders."""
        Path(self.audio_dir).mkdir(parents=True, exist_ok=True)
        Path(self.transcript_dir).mkdir(parents=True, exist_ok=True)

        base_name = f"{timestamp}_{scenario_id}"
        saved_files = {}

        # Save combined conversation audio only
        combined_audio = self.audio_mixer.mix_audio()
        if combined_audio:
            combined_file = os.path.join(self.audio_dir, f"{base_name}_conversation.wav")
            self._save_wav(combined_file, combined_audio, OUTPUT_SAMPLE_RATE)
            logger.info(f"🔊 Combined audio saved: {combined_file}")
            saved_files["conversation"] = f"{base_name}_conversation.wav"

        # Save transcript to transcripts folder
        transcript_file = os.path.join(self.transcript_dir, f"{base_name}_transcript.txt")
        self._save_transcript(transcript_file)
        logger.info(f"📝 Transcript saved: {transcript_file}")
        saved_files["transcript"] = f"{base_name}_transcript.txt"

        return saved_files

    def _save_wav(self, filename: str, audio_data: bytes, sample_rate: int):
        try:
            with wave.open(filename, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data)
        except Exception as e:
            logger.error(f"Error saving WAV file {filename}: {e}")

    def _save_transcript(self, filename: str):
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"Scenario: {self.scenario.get('name', 'Unknown')}\n")
                f.write(f"Scenario ID: {self.scenario.get('id', 'Unknown')}\n")
                f.write(f"Customer: {self.scenario.get('customer', {}).get('name', 'Unknown')}\n")
                f.write(f"Date: {datetime.now().isoformat()}\n")
                f.write("=" * 60 + "\n\n")

                for i, t in enumerate(self.transcripts, 1):
                    role = "CUSTOMER" if t["role"] == "customer" else "AGENT"
                    f.write(f"[{i}] {role}:\n{t['content']}\n\n")
        except Exception as e:
            logger.error(f"Error saving transcript {filename}: {e}")

    # ---------------- BACKEND API ----------------

    async def create_room_and_token(self):
        """Create LiveKit room and get connection token."""
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        self.room_name = f"deepgram-{suffix}"
        self.identity = f"gemini-customer-{suffix}"

        payload = {
            "room_name": self.room_name,
            "user_name": self.identity,
            "is_publisher": True,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BACKEND_URL}/api/voiceagent/livekit/token/",
                json=payload,
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(await resp.text())

                data = await resp.json()
                self.ws_url = data["ws_url"]
                self.token = data["token"]

    async def _poll_agent_transcript(self):
        """Poll backend for agent's text responses (cleaner than STT)."""
        try:
            async with aiohttp.ClientSession() as session:
                while True:
                    await asyncio.sleep(0.5)  # Poll every 500ms

                    try:
                        # Request agent's conversation transcript from backend
                        async with session.get(
                            f"{BACKEND_URL}/api/voiceagent/transcript/{self.room_name}/",
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                messages = data.get("messages", [])

                                # Extract new agent messages
                                for msg in messages:
                                    if msg.get("role") == "assistant" and msg.get("content"):
                                        text = msg["content"].strip()
                                        if text and text not in self.agent_text_responses:
                                            self.agent_text_responses.append(text)
                                            logger.debug(f"📝 Captured agent text: {text[:80]}...")

                    except asyncio.TimeoutError:
                        pass  # Backend might not respond, that's okay
                    except Exception as e:
                        logger.debug(f"Agent transcript poll error: {e}")

        except asyncio.CancelledError:
            pass

    # ---------------- PROVIDER CONNECTION ----------------

    async def connect_provider(self):
        """Connect to the configured AI provider."""
        if self.provider == "openai":
            await self.connect_openai()
        else:
            await self.connect_gemini()

    # ---------------- OPENAI CONNECTION ----------------

    async def connect_openai(self):
        """Connect to OpenAI Realtime API."""
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY not set")

        # Import config module to get the current (possibly overridden) model
        from . import config
        model = config.OPENAI_MODEL

        ws_url = f"wss://api.openai.com/v1/realtime?model={model}"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1"
        }
        self.gemini_ws = await websockets.connect(ws_url, additional_headers=headers)

        system_instruction = build_system_instruction(self.scenario)

        # Select voice for OpenAI Realtime API
        # Supported: alloy, ash, ballad, coral, echo, sage, shimmer, verse, marin, cedar
        openai_voices = ["alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse"]
        scenario_id = self.scenario.get("id", "")
        selected_voice = openai_voices[hash(scenario_id) % len(openai_voices)]
        logger.info(f"Selected voice: {selected_voice} for customer {self.scenario.get('customer', {}).get('name', 'Unknown')}")

        # OpenAI session update message
        setup_message = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": system_instruction,
                "voice": selected_voice,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.3,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 800
                }
            }
        }

        await self.gemini_ws.send(json.dumps(setup_message))
        self.tasks.append(asyncio.create_task(self._listen_openai()))
        self.tasks.append(asyncio.create_task(self._keep_alive_loop()))
        self.tasks.append(asyncio.create_task(self._flush_buffers_loop()))

        try:
            await asyncio.wait_for(self.gemini_ready.wait(), timeout=10)
        except asyncio.TimeoutError:
            raise RuntimeError("OpenAI setup failed")

    async def _listen_openai(self):
        """Listen for OpenAI Realtime API messages."""
        try:
            async for raw in self.gemini_ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type", "")

                # Log important events for debugging
                if msg_type not in ("response.audio.delta", "input_audio_buffer.speech_started", "input_audio_buffer.committed"):
                    if msg_type == "error":
                        logger.error(f"OpenAI error: {msg.get('error', {})}")
                    elif msg_type in ("session.created", "session.updated", "response.created",
                                      "response.done", "input_audio_buffer.speech_stopped",
                                      "conversation.item.created"):
                        logger.info(f"OpenAI event: {msg_type}")

                if msg_type == "session.created" or msg_type == "session.updated":
                    self.gemini_ready.set()

                elif msg_type == "input_audio_buffer.speech_started":
                    self.last_activity_time = asyncio.get_event_loop().time()
                    logger.info("🎤 OpenAI detected speech start")

                elif msg_type == "input_audio_buffer.speech_stopped":
                    self.last_activity_time = asyncio.get_event_loop().time()
                    logger.info("🎤 OpenAI detected speech stop")

                elif msg_type == "response.audio_transcript.delta":
                    # Customer speaking (model output)
                    transcript = msg.get("delta", "")
                    if transcript:
                        current_time = asyncio.get_event_loop().time()
                        if self.agent_transcript_buffer.strip():
                            self._flush_agent_buffer()
                        self.customer_transcript_buffer += transcript
                        self.last_customer_transcript_time = current_time

                elif msg_type == "conversation.item.input_audio_transcription.completed":
                    # Agent speaking (input transcription)
                    transcript = msg.get("transcript", "")
                    if transcript:
                        current_time = asyncio.get_event_loop().time()
                        if self.customer_transcript_buffer.strip():
                            self._flush_customer_buffer()
                        self.agent_transcript_buffer += transcript
                        self.last_agent_transcript_time = current_time

                elif msg_type == "response.audio.delta":
                    # Audio output from model
                    audio_b64 = msg.get("delta", "")
                    if audio_b64:
                        current_time = asyncio.get_event_loop().time()
                        audio_bytes = base64.b64decode(audio_b64)
                        self.audio_mixer.add_customer_audio(audio_bytes, current_time)
                        self.customer_audio_chunks += 1

                        if self.audio_source:
                            await self._forward_audio_to_livekit(audio_b64)

                elif msg_type == "response.done":
                    self._flush_customer_buffer()

        except asyncio.CancelledError:
            self._flush_agent_buffer()
            self._flush_customer_buffer()
        except websockets.exceptions.ConnectionClosed:
            self._flush_agent_buffer()
            self._flush_customer_buffer()
        except Exception as e:
            logger.error(f"Error in listen_openai: {e}")

    async def _send_audio_to_openai(self, audio_b64: str):
        """Send audio to OpenAI Realtime API."""
        if not self.gemini_ws:
            return
        try:
            await self.gemini_ws.send(json.dumps({
                "type": "input_audio_buffer.append",
                "audio": audio_b64
            }))
        except:
            pass

    # ---------------- GEMINI CONNECTION ----------------

    async def connect_gemini(self):
        """Connect to Gemini WebSocket API."""
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY not set")

        ws_url = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key={GEMINI_API_KEY}"
        self.gemini_ws = await websockets.connect(ws_url)

        system_instruction = build_system_instruction(self.scenario)

        # Select voice dynamically based on customer persona
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
                    "automatic_activity_detection": {
                        "disabled": True
                    }
                },
                "output_audio_transcription": {},
                "input_audio_transcription": {},
                "system_instruction": {"parts": [{"text": system_instruction}]},
            }
        }

        await self.gemini_ws.send(json.dumps(setup_message))
        self.tasks.append(asyncio.create_task(self._listen_gemini()))
        self.tasks.append(asyncio.create_task(self._keep_alive_loop()))
        self.tasks.append(asyncio.create_task(self._flush_buffers_loop()))

        try:
            await asyncio.wait_for(self.gemini_ready.wait(), timeout=10)
        except asyncio.TimeoutError:
            raise RuntimeError("Gemini setup failed")

    async def _keep_alive_loop(self):
        """Keep WebSocket connection alive."""
        try:
            while True:
                await asyncio.sleep(15)
                try:
                    await self.gemini_ws.ping()
                except:
                    break
        except asyncio.CancelledError:
            pass

    async def _flush_buffers_loop(self):
        """Periodically flush transcript buffers."""
        try:
            while True:
                await asyncio.sleep(0.5)
                current_time = asyncio.get_event_loop().time()

                if (self.agent_transcript_buffer.strip()
                    and self.last_agent_transcript_time > 0
                    and current_time - self.last_agent_transcript_time > 1.5):
                    self._flush_agent_buffer()

                if (self.customer_transcript_buffer.strip()
                    and self.last_customer_transcript_time > 0
                    and current_time - self.last_customer_transcript_time > 1.5):
                    self._flush_customer_buffer()

        except asyncio.CancelledError:
            pass

    def _flush_agent_buffer(self):
        """Flush agent transcript buffer, preferring clean text from backend."""
        if self.agent_transcript_buffer.strip():
            stt_text = re.sub(r"\s+", " ", self.agent_transcript_buffer.strip())

            # Try to find matching clean text from backend
            clean_text = None
            best_match_score = 0

            for backend_text in self.agent_text_responses:
                # Check if this backend text hasn't been used yet
                if any(t.get("role") == "agent" and t.get("content") == backend_text
                       for t in self.transcripts):
                    continue

                # Calculate similarity score
                stt_lower = stt_text.lower()
                backend_lower = backend_text.lower()

                # Score based on matching first words
                stt_words = stt_lower.split()[:5]
                backend_words = backend_lower.split()[:5]
                word_matches = sum(1 for w in stt_words if w in backend_lower)

                # Score based on substring matching
                if len(backend_text) >= 15:
                    start_match = backend_lower[:15] in stt_lower or stt_lower[:15] in backend_lower
                else:
                    start_match = False

                match_score = word_matches + (3 if start_match else 0)

                if match_score > best_match_score and match_score >= 2:
                    best_match_score = match_score
                    clean_text = backend_text

            # Use clean text if found, otherwise fall back to STT (with STT error cleanup)
            final_text = clean_text if clean_text else clean_stt_errors(stt_text)

            logger.info(f"🏨 AGENT: {final_text}")

            self.transcripts.append({"role": "agent", "content": final_text})
            self.last_agent_question = final_text
            self.agent_transcript_buffer = ""
            self.last_agent_transcript_time = 0
            self.last_activity_time = asyncio.get_event_loop().time()
            # Agent responded, reset keep-alive state
            self.waiting_for_agent_response = False
            self.keepalive_attempts = 0

    def _flush_customer_buffer(self):
        """Flush customer transcript buffer."""
        if self.customer_transcript_buffer.strip():
            text = re.sub(r"\s+", " ", self.customer_transcript_buffer.strip())

            # Safety check: Strip any "Agent:" prefix if Gemini got confused about its role
            # This indicates a role confusion issue in Gemini
            if text.lower().startswith("agent:"):
                logger.warning(f"⚠️ Gemini role confusion detected - customer said: {text[:50]}...")
                # Strip the "Agent:" prefix and log as warning but still record it
                text = re.sub(r"^agent:\s*", "", text, flags=re.IGNORECASE).strip()

            # Clean up common STT transcription errors
            text = clean_stt_errors(text)

            if text:  # Only add if there's still content after cleanup
                self.transcripts.append({"role": "customer", "content": text})
                logger.info(f"👤 CUSTOMER: {text}")

            self.customer_transcript_buffer = ""
            self.last_customer_transcript_time = 0
            self.last_activity_time = asyncio.get_event_loop().time()
            # Customer spoke, so we're now waiting for agent response
            self.waiting_for_agent_response = True

    def _is_conversation_ending(self) -> bool:
        """
        Check if the conversation appears to be ending naturally.
        Used to prevent sending keep-alive prompts after goodbyes or when agent can't proceed.
        """
        if len(self.transcripts) < 3:
            return False

        # Check if booking was confirmed
        if is_booking_confirmed(self.transcripts):
            return True

        # Check recent messages for farewell indicators
        recent = self.transcripts[-5:] if len(self.transcripts) >= 5 else self.transcripts
        recent_text = " ".join(t["content"].lower() for t in recent)

        # Strong farewell phrases - if ANY of these appear, conversation is ending
        strong_farewells = ["goodbye", "bye bye", "take care"]

        # If customer said a strong farewell, don't send more prompts
        recent_customer = " ".join(t["content"].lower() for t in recent if t["role"] == "customer")
        if any(phrase in recent_customer for phrase in strong_farewells):
            return True

        # Check if agent is indicating they CANNOT proceed (technical issues, policy, etc.)
        recent_agent = " ".join(t["content"].lower() for t in recent if t["role"] == "agent")
        cannot_proceed_phrases = [
            "unable to complete", "cannot complete", "can't complete",
            "unable to finalize", "cannot finalize", "can't finalize",
            "unable to proceed", "cannot proceed", "can't proceed",
            "preventing me from", "not able to", "not permitted",
            "call us back", "call back later", "try again later",
            "technical issue", "system issue", "technical difficulty",
            "i'm unable to", "i am unable to", "unable to book",
        ]
        if any(phrase in recent_agent for phrase in cannot_proceed_phrases):
            return True

        # Farewell phrases that indicate conversation is ending
        farewell_phrases = [
            "goodbye", "bye", "bye bye", "take care",
            "have a wonderful", "have a great", "have a lovely",
            "thank you for calling", "thanks for calling",
            "enjoy your stay", "look forward to hosting",
            "looking forward to", "see you soon",
        ]

        # Check for multiple farewell phrases in recent messages
        farewell_count = sum(1 for phrase in farewell_phrases if phrase in recent_text)
        if farewell_count >= 2:
            return True

        # Check if both parties said goodbye-like things
        agent_farewell = any(p in recent_agent for p in ["goodbye", "bye", "take care", "have a wonderful", "have a great"])
        customer_farewell = any(p in recent_customer for p in ["goodbye", "bye", "thank you so much"])

        return agent_farewell and customer_farewell

    async def _send_keepalive_prompt(self):
        """Send a keep-alive prompt to re-engage the conversation when agent is silent."""
        if not self.gemini_ws:
            return

        # Check one more time if conversation is ending
        if self._is_conversation_ending():
            logger.info("🔄 Skipping keep-alive - conversation is ending")
            return

        # Use conversation context for smarter prompts
        stage = get_conversation_stage(self.transcripts)

        if stage in ["RATE_QUOTED", "EXPERIENCE_SHAPED", "RECAP_DONE", "CONFIRMATION_ASKED"]:
            keepalive_prompts = [
                "Yes, please proceed with the booking.",
                "Can you confirm the reservation please?",
                "I'm ready to book. Can we finalize this?",
            ]
        elif stage in ["GREETING", "NAME_COLLECTED", "PHONE_COLLECTED"]:
            keepalive_prompts = [
                "Hello?",
                "Are you still there?",
                "I'm still on the line.",
            ]
        else:
            keepalive_prompts = [
                "Yes?",
                "Should we continue?",
                "I'm still here.",
            ]

        prompt_idx = min(self.keepalive_attempts, len(keepalive_prompts) - 1)
        prompt = keepalive_prompts[prompt_idx]

        logger.info(f"🔄 Sending keep-alive prompt (attempt {self.keepalive_attempts + 1}/{MAX_KEEPALIVE_ATTEMPTS}): {prompt}")

        try:
            # Instruction to speak the prompt exactly once
            instruction = f"[Say this ONCE, then wait for the agent to respond]: {prompt}"

            if self.provider == "openai":
                # For OpenAI, send a text message that triggers a response
                await self.gemini_ws.send(json.dumps({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": instruction}]
                    }
                }))
                # Trigger a response
                await self.gemini_ws.send(json.dumps({"type": "response.create"}))
            else:
                # For Gemini, send a text prompt
                await self.gemini_ws.send(json.dumps({
                    "clientContent": {
                        "turns": [{"role": "user", "parts": [{"text": instruction}]}],
                        "turnComplete": True
                    }
                }))

            self.keepalive_attempts += 1
            self.last_keepalive_time = asyncio.get_event_loop().time()
            self.last_activity_time = self.last_keepalive_time

        except Exception as e:
            logger.error(f"Error sending keep-alive prompt: {e}")

    async def _listen_gemini(self):
        """Listen for Gemini WebSocket messages."""
        try:
            async for raw in self.gemini_ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if "setupComplete" in msg:
                    self.gemini_ready.set()

                elif "serverContent" in msg:
                    server_content = msg["serverContent"]
                    current_time = asyncio.get_event_loop().time()

                    if server_content.get("turnComplete") or server_content.get("interrupted"):
                        self._flush_customer_buffer()

                    # Customer speaking (output transcription)
                    if "outputTranscription" in server_content:
                        transcript = server_content["outputTranscription"].get("text", "")
                        if transcript:
                            if self.agent_transcript_buffer.strip():
                                self._flush_agent_buffer()
                            self.customer_transcript_buffer += transcript
                            self.last_customer_transcript_time = current_time

                    # Agent speaking (input transcription)
                    if "inputTranscription" in server_content:
                        transcript = server_content["inputTranscription"].get("text", "")
                        if transcript:
                            if self.customer_transcript_buffer.strip():
                                self._flush_customer_buffer()
                            self.agent_transcript_buffer += transcript
                            self.last_agent_transcript_time = current_time

                    # Handle audio output
                    model_turn = server_content.get("modelTurn", {})
                    for part in model_turn.get("parts", []):
                        if "inlineData" in part:
                            inline_data = part["inlineData"]
                            if "audio" in inline_data.get("mimeType", ""):
                                audio_b64 = inline_data.get("data", "")
                                if audio_b64:
                                    audio_bytes = base64.b64decode(audio_b64)
                                    self.audio_mixer.add_customer_audio(audio_bytes, current_time)
                                    self.customer_audio_chunks += 1

                                    if self.audio_source:
                                        await self._forward_audio_to_livekit(audio_b64)

        except asyncio.CancelledError:
            self._flush_agent_buffer()
            self._flush_customer_buffer()
        except websockets.exceptions.ConnectionClosed:
            self._flush_agent_buffer()
            self._flush_customer_buffer()
        except Exception as e:
            logger.error(f"Error in listen_gemini: {e}")

    async def _send_audio_to_gemini(self, audio_b64: str):
        """Send audio to Gemini."""
        if not self.gemini_ws:
            return
        try:
            await self.gemini_ws.send(json.dumps({
                "realtimeInput": {
                    "mediaChunks": [
                        {"mimeType": "audio/pcm;rate=16000", "data": audio_b64}
                    ]
                }
            }))
        except:
            pass

    # ---------------- LIVEKIT CONNECTION ----------------

    async def connect_livekit(self):
        """Connect to LiveKit room."""
        from livekit import rtc
        from livekit.rtc import Room, RoomOptions

        self.room = Room()

        @self.room.on("track_subscribed")
        def on_track(track, pub, participant):
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                if "agent" in participant.identity.lower():
                    self.agent_connected.set()
                    self.tasks.append(
                        asyncio.create_task(self._forward_agent_audio_to_gemini(track))
                    )

        @self.room.on("participant_connected")
        def on_participant(p):
            if "agent" in p.identity.lower():
                self.agent_connected.set()

        await self.room.connect(
            self.ws_url, self.token, options=RoomOptions(auto_subscribe=True)
        )

        self.audio_source = rtc.AudioSource(sample_rate=24000, num_channels=1)
        audio_track = rtc.LocalAudioTrack.create_audio_track("gemini_audio", self.audio_source)
        await self.room.local_participant.publish_track(audio_track)

    async def _forward_agent_audio_to_gemini(self, track):
        """Forward agent audio to the AI provider."""
        from livekit import rtc

        await self.gemini_ready.wait()

        try:
            audio_stream = rtc.AudioStream(track, sample_rate=16000, num_channels=1)

            async for event in audio_stream:
                if isinstance(event, rtc.AudioFrameEvent):
                    current_time = asyncio.get_event_loop().time()

                    self.audio_mixer.add_agent_audio(bytes(event.frame.data), current_time)
                    self.agent_audio_chunks += 1

                    audio_b64 = base64.b64encode(event.frame.data).decode()
                    await self._send_audio_to_provider(audio_b64)

        except Exception:
            pass

    async def _send_audio_to_provider(self, audio_b64: str):
        """Send audio to the configured AI provider."""
        if self.provider == "openai":
            await self._send_audio_to_openai(audio_b64)
        else:
            await self._send_audio_to_gemini(audio_b64)

    async def _forward_audio_to_livekit(self, audio_b64: str):
        """Forward customer audio to LiveKit."""
        from livekit import rtc

        try:
            audio = base64.b64decode(audio_b64)
            samples = len(audio) // 2
            frame = rtc.AudioFrame.create(24000, 1, samples)
            np.copyto(
                np.frombuffer(frame.data, dtype=np.int16),
                np.frombuffer(audio, dtype=np.int16),
            )
            await self.audio_source.capture_frame(frame)
        except:
            pass

    # ---------------- SUCCESS CRITERIA ----------------

    def check_success_criteria(self) -> Dict[str, Any]:
        """
        Check if scenario success criteria are met.
        Evaluates against the 13-step agent conversation flow.
        """
        criteria = self.scenario.get("success_criteria", {})
        results = {}

        full_text = " ".join(t["content"].lower() for t in self.transcripts)
        customer_text = " ".join(
            t["content"].lower() for t in self.transcripts if t["role"] == "customer"
        )
        agent_text = " ".join(
            t["content"].lower() for t in self.transcripts if t["role"] == "agent"
        )

        # Core booking status
        valid_booking_number = extract_booking_number(self.transcripts)
        raw_booking_number = extract_raw_booking_number(self.transcripts)
        confirmation_detected = is_booking_confirmed(self.transcripts)

        # Check if agent provided a booking number (valid or invalid)
        results["booking_number"] = valid_booking_number or raw_booking_number
        results["raw_booking_number"] = raw_booking_number

        # Booking is confirmed if the agent confirmed it (even if number format is invalid)
        # The goal is to test if the agent completed the booking flow, not validate the number format
        results["booking_confirmed"] = confirmation_detected

        # Flag invalid booking numbers as warnings (but still count as success)
        if raw_booking_number and not valid_booking_number:
            results["invalid_booking_number"] = True
            results["invalid_booking_number_value"] = raw_booking_number
            logger.warning(f"⚠️ Booking confirmed but number format invalid: '{raw_booking_number}'")
        else:
            results["invalid_booking_number"] = False

        results["conversation_stage"] = get_conversation_stage(self.transcripts)

        # Check if correct hotel was selected (for redirect scenarios)
        if "correct_hotel" in criteria:
            expected_hotel = criteria["correct_hotel"].lower()
            # Check both customer mention and agent confirmation
            customer_mentioned = expected_hotel in customer_text
            agent_confirmed = expected_hotel in agent_text
            results["correct_hotel"] = customer_mentioned or agent_confirmed

        # Track what information was successfully provided
        # Always check name, phone, and email since they're always displayed in Excel
        results["provided_info"] = {}
        info_to_check = ["name", "phone", "email"]

        for info in info_to_check:
            if info == "name":
                name = self.scenario["customer"]["name"]
                name_parts = name.lower().split()
                # Check if any part of the name was mentioned
                results["provided_info"]["name"] = any(p in customer_text for p in name_parts if len(p) > 2)
            elif info == "phone":
                phone = self.scenario["customer"]["phone"].replace(" ", "").replace("+", "").replace("-", "")
                cust_phone = customer_text.replace(" ", "").replace("+", "").replace("-", "")
                # Check for phone number (full, last 10 digits, or last 4 digits)
                results["provided_info"]["phone"] = any(
                    p in cust_phone for p in [phone, phone[-10:], phone[-4:]] if len(p) >= 4
                )
            elif info == "email":
                email = self.scenario["customer"].get("email", "")
                # Check for @ symbol or actual email domain
                results["provided_info"]["email"] = "@" in customer_text or (
                    email and email.split("@")[-1].lower() in customer_text
                )

        # Check for must-contain keywords (anniversaries, honeymoon, etc.)
        if "must_contain" in criteria:
            results["must_contain"] = {
                kw: kw.lower() in full_text for kw in criteria["must_contain"]
            }

        # Scenario-specific criteria validation
        # For non-booking scenarios (cancellation, inquiry)
        if criteria.get("booking_confirmed") is False:
            # Scenario expects NO booking - success if no booking was made
            results["expected_no_booking"] = not results["booking_confirmed"]

        if criteria.get("cancellation_requested"):
            results["cancellation_requested"] = any(
                p in customer_text for p in ["cancel", "cancellation", "cancel my"]
            )

        if criteria.get("booking_inquiry"):
            results["booking_inquiry"] = any(
                p in customer_text for p in ["confirm", "verify", "check my booking", "existing booking"]
            )

        if criteria.get("email_requested"):
            results["email_requested"] = "email" in customer_text and any(
                p in customer_text for p in ["send me", "email me", "details"]
            )

        return results

    # ---------------- TEXT MODE ----------------

    async def _run_text_mode(self, timeout: int, start_time: datetime):
        """Run conversation in text-only mode without audio."""
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            # Fallback to old package
            import google.generativeai as genai
            types = None

        if types:
            # New API - try different models based on quota
            client = genai.Client(api_key=GEMINI_API_KEY)
            system_instruction = build_system_instruction(self.scenario)

            # Try models in order of preference (cheapest/fastest first)
            model_names = [
                "gemini-2.0-flash-lite",  # Cheapest, best quota
                "gemini-flash-lite-latest",  # Alias to latest lite
                "gemini-2.0-flash",  # Standard 2.0
                "gemini-flash-latest",  # Latest stable
                "gemini-2.5-flash",  # Most capable but higher cost
            ]
            chat_history = []
        else:
            # Old API (deprecated)
            genai.configure(api_key=GEMINI_API_KEY)
            system_instruction = build_system_instruction(self.scenario)

            # Use stable model with better quota
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=system_instruction
            )
            chat = model.start_chat(history=[])

        # Get agent's backend URL for text API
        async with aiohttp.ClientSession() as session:
            # Send initial connection to agent (text mode)
            agent_url = f"{BACKEND_URL}/api/voiceagent/text/"

            # Log voice selection (for reference in text mode)
            selected_voice = select_voice_for_customer(self.scenario)
            logger.info(f"Voice would be: {selected_voice} (text mode - no audio)")

            # Simulate conversation loop
            logger.info("Starting text conversation...")

            # Initial customer greeting based on conversation style
            style = self.scenario.get("conversation_style", {})
            opening = style.get("opening", "direct_request")

            # Customer starts the conversation
            if opening == "direct_request":
                customer_msg = f"Hello. I'd like to book a room, please."
            elif opening == "calm_request":
                customer_msg = f"Hello. I'm looking for a quiet place to spend a few days alone... for some peace and reflection. I'd like to book a room please."
            else:
                customer_msg = "Hello, I'd like to make a booking."

            max_turns = 50  # Prevent infinite loops
            turn_count = 0

            while turn_count < max_turns:
                turn_count += 1

                # Check timeout
                if (datetime.now() - start_time).seconds >= timeout:
                    logger.info(f"⏰ Timeout reached: {timeout}s")
                    break

                # Agent speaks (via backend API)
                try:
                    async with session.post(
                        agent_url,
                        json={"message": customer_msg, "room_name": f"text-{self.scenario.get('id', 'test')}"},
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as resp:
                        if resp.status == 200:
                            agent_response = await resp.json()
                            agent_text = agent_response.get("response", "")

                            if agent_text:
                                self.transcripts.append({"role": "agent", "content": agent_text})
                                logger.info(f"🏨 AGENT: {agent_text}")
                        else:
                            # Fallback: simulate agent response
                            agent_text = "Welcome to Tamara Resorts. How may I assist you today?"
                            self.transcripts.append({"role": "agent", "content": agent_text})
                            logger.info(f"🏨 AGENT (fallback): {agent_text}")
                except Exception as e:
                    logger.warning(f"Agent API error: {e}, using fallback")
                    agent_text = "Hello, how can I help you with your booking?"
                    self.transcripts.append({"role": "agent", "content": agent_text})
                    logger.info(f"🏨 AGENT (fallback): {agent_text}")

                # Check if conversation should end
                if is_booking_confirmed(self.transcripts):
                    logger.info("✅ BOOKING CONFIRMED!")
                    break

                if is_call_ended(self.transcripts):
                    logger.info("📞 Call ended")
                    break

                # Customer responds (via Gemini)
                try:
                    if types:
                        # New API - try models until one works
                        customer_text = None
                        last_error = None

                        for model_name in model_names:
                            try:
                                response = client.models.generate_content(
                                    model=model_name,
                                    contents=agent_text,
                                    config=types.GenerateContentConfig(
                                        system_instruction=system_instruction
                                    )
                                )
                                customer_text = response.text.strip()
                                break  # Success, exit loop
                            except Exception as model_error:
                                last_error = model_error
                                if "429" in str(model_error) or "quota" in str(model_error).lower():
                                    logger.warning(f"Quota exceeded for {model_name}, trying next model...")
                                    continue
                                else:
                                    raise  # Re-raise non-quota errors

                        if customer_text is None and last_error:
                            raise last_error
                    else:
                        # Old API
                        response = chat.send_message(agent_text)
                        customer_text = response.text.strip()

                    if customer_text:
                        self.transcripts.append({"role": "customer", "content": customer_text})
                        logger.info(f"👤 CUSTOMER: {customer_text}")
                        customer_msg = customer_text
                except Exception as e:
                    logger.error(f"Gemini error: {e}")
                    break

                # Small delay between turns
                await asyncio.sleep(1)

    # ---------------- MAIN RUN ----------------

    async def run(self, timeout: int = DEFAULT_TIMEOUT, text_mode: bool = False) -> Dict[str, Any]:
        """Run the evaluation scenario."""
        start_time = datetime.now()
        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        self.last_activity_time = asyncio.get_event_loop().time()
        self.audio_mixer.set_start_time(self.last_activity_time)
        error = None
        saved_files = {}

        try:
            if text_mode:
                logger.info("🔤 Running in TEXT-ONLY mode (no audio/LiveKit)")
                await self._run_text_mode(timeout, start_time)
                return {
                    "scenario_id": self.scenario.get("id", "unknown"),
                    "scenario_name": self.scenario.get("name", "unnamed"),
                    "duration_seconds": (datetime.now() - start_time).seconds,
                    "transcript_count": len(self.transcripts),
                    "transcripts": self.transcripts,
                    "success_results": self.check_success_criteria(),
                    "error": error,
                    "audio_files": {},
                }

            await self.create_room_and_token()
            await self.connect_provider()
            await self.connect_livekit()

            try:
                await asyncio.wait_for(self.agent_connected.wait(), timeout=30)
            except asyncio.TimeoutError:
                raise RuntimeError("Agent did not join within 30 seconds")

            # Start polling for clean agent transcripts
            self.tasks.append(asyncio.create_task(self._poll_agent_transcript()))

            await asyncio.sleep(2)
            self.last_activity_time = asyncio.get_event_loop().time()

            last_count = 0
            last_stage = "GREETING"

            while True:
                await asyncio.sleep(3)

                current_count = len(self.transcripts)
                current_time = asyncio.get_event_loop().time()
                current_stage = get_conversation_stage(self.transcripts)

                if current_count > last_count:
                    last_count = current_count
                    self.conversation_stalled_count = 0

                    if current_stage != last_stage:
                        logger.info(f"📍 Stage: {current_stage} ({current_count} messages)")
                        last_stage = current_stage
                    elif current_count % 10 == 0:
                        logger.info(f"📍 Progress: {current_count} messages")

                if is_booking_confirmed(self.transcripts):
                    booking_num = extract_booking_number(self.transcripts)
                    logger.info(f"✅ BOOKING CONFIRMED! Number: {booking_num}")
                    await asyncio.sleep(5)
                    break

                if is_call_ended(self.transcripts) and len(self.transcripts) > 15:
                    logger.info("📞 Call ended naturally")
                    await asyncio.sleep(2)
                    break

                time_since_activity = current_time - self.last_activity_time

                # Check if conversation is winding down (goodbyes exchanged) - don't send keep-alive
                conversation_ending = self._is_conversation_ending()

                # Check if agent has been silent and we should send a keep-alive prompt
                # Only send if: enough time has passed, we haven't exceeded max attempts,
                # enough time since last keep-alive attempt, and conversation isn't ending
                time_since_keepalive = current_time - self.last_keepalive_time if self.last_keepalive_time > 0 else float('inf')

                if (time_since_activity >= AGENT_RESPONSE_TIMEOUT
                    and self.keepalive_attempts < MAX_KEEPALIVE_ATTEMPTS
                    and time_since_keepalive >= AGENT_RESPONSE_TIMEOUT
                    and not conversation_ending):
                    # Agent has been silent, send a keep-alive prompt from the customer
                    await self._send_keepalive_prompt()
                    continue  # Give the agent time to respond

                # Only end due to inactivity if we've exhausted keep-alive attempts
                if time_since_activity >= INACTIVITY_TIMEOUT:
                    if self.keepalive_attempts >= MAX_KEEPALIVE_ATTEMPTS:
                        logger.info(f"⏰ Inactivity timeout after {MAX_KEEPALIVE_ATTEMPTS} keep-alive attempts (Stage: {current_stage})")
                    else:
                        logger.info(f"⏰ Inactivity timeout: {INACTIVITY_TIMEOUT}s (Stage: {current_stage})")
                    break

                elapsed = (datetime.now() - start_time).seconds
                if elapsed >= timeout:
                    logger.info(f"⏰ Overall timeout: {timeout}s (Stage: {current_stage})")
                    break

        except Exception as e:
            error = str(e)
            logger.error(f"❌ Error: {e}")
        finally:
            self._flush_agent_buffer()
            self._flush_customer_buffer()

            scenario_id = self.scenario.get("id", "unknown")
            saved_files = self.save_audio_files(scenario_id, timestamp)

            for task in self.tasks:
                task.cancel()

            if self.gemini_ws:
                try:
                    await self.gemini_ws.close()
                except:
                    pass
            if self.room:
                try:
                    await self.room.disconnect()
                except:
                    pass

        duration = (datetime.now() - start_time).seconds
        success_results = self.check_success_criteria()

        return {
            "scenario_id": scenario_id,
            "scenario_name": self.scenario.get("name", "unnamed"),
            "duration_seconds": duration,
            "transcript_count": len(self.transcripts),
            "transcripts": self.transcripts,
            "success_results": success_results,
            "error": error,
            "audio_files": saved_files,
        }
