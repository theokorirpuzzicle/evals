"""
OpenAI Realtime API provider integration.
"""

import asyncio
import json
import logging
from typing import Optional, Callable, Awaitable

import websockets

from ..config import OPENAI_API_KEY
from .base import BaseProvider

logger = logging.getLogger("eval-runner")


class OpenAIProvider(BaseProvider):
    """OpenAI Realtime API provider for real-time audio conversations."""

    WEBSOCKET_BASE_URL = "wss://api.openai.com/v1/realtime"

    def __init__(
        self,
        model: str = "gpt-4o-realtime-preview",
        on_audio_output: Optional[Callable[[str, float], Awaitable[None]]] = None,
        on_transcript_output: Optional[Callable[[str, float], None]] = None,
        on_transcript_input: Optional[Callable[[str, float], None]] = None,
        on_ready: Optional[Callable[[], None]] = None,
        on_response_done: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize OpenAI provider.

        Args:
            model: OpenAI model to use
            on_audio_output: Callback for audio output (base64, timestamp)
            on_transcript_output: Callback for customer transcription (text, timestamp)
            on_transcript_input: Callback for agent transcription (text, timestamp)
            on_ready: Callback when provider is ready
            on_response_done: Callback when a response is complete
        """
        super().__init__(
            on_audio_output=on_audio_output,
            on_transcript_output=on_transcript_output,
            on_transcript_input=on_transcript_input,
            on_ready=on_ready,
        )
        self.model = model
        self._on_response_done = on_response_done

    async def connect(self, system_instruction: str, voice: str) -> None:
        """
        Connect to OpenAI Realtime API.

        Args:
            system_instruction: System prompt for the conversation
            voice: OpenAI voice name (alloy, ash, ballad, coral, echo, sage, shimmer, verse)
        """
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY not set")

        ws_url = f"{self.WEBSOCKET_BASE_URL}?model={self.model}"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1"
        }
        self.ws = await websockets.connect(ws_url, additional_headers=headers)

        # OpenAI session update message
        setup_message = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": system_instruction,
                "voice": voice,
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

        await self.ws.send(json.dumps(setup_message))
        logger.info(f"OpenAI: Connected with voice {voice}")

    async def send_audio(self, audio_b64: str) -> None:
        """
        Send audio to OpenAI Realtime API.

        Args:
            audio_b64: Base64 encoded PCM16 audio at 16kHz
        """
        if not self.ws:
            return
        try:
            await self.ws.send(json.dumps({
                "type": "input_audio_buffer.append",
                "audio": audio_b64
            }))
        except Exception:
            pass

    async def send_text(self, text: str) -> None:
        """
        Send text message to OpenAI and trigger a response.

        Args:
            text: Text message to send
        """
        if not self.ws:
            return
        try:
            # Create a conversation item
            await self.ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}]
                }
            }))
            # Trigger a response
            await self.ws.send(json.dumps({"type": "response.create"}))
        except Exception as e:
            logger.error(f"OpenAI: Error sending text: {e}")

    async def listen(self) -> None:
        """Listen for OpenAI Realtime API messages."""
        try:
            async for raw in self.ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                await self._handle_message(msg)

        except asyncio.CancelledError:
            pass
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"OpenAI: Error in listener: {e}")

    async def _handle_message(self, msg: dict) -> None:
        """
        Handle an OpenAI WebSocket message.

        Args:
            msg: Parsed JSON message
        """
        current_time = asyncio.get_event_loop().time()
        msg_type = msg.get("type", "")

        # Log important events
        if msg_type not in ("response.audio.delta", "input_audio_buffer.speech_started",
                           "input_audio_buffer.committed"):
            if msg_type == "error":
                logger.error(f"OpenAI error: {msg.get('error', {})}")
            elif msg_type in ("session.created", "session.updated", "response.created",
                            "response.done", "input_audio_buffer.speech_stopped",
                            "conversation.item.created"):
                logger.info(f"OpenAI event: {msg_type}")

        if msg_type in ("session.created", "session.updated"):
            self._emit_ready()

        elif msg_type == "input_audio_buffer.speech_started":
            logger.info("OpenAI: Detected speech start")

        elif msg_type == "input_audio_buffer.speech_stopped":
            logger.info("OpenAI: Detected speech stop")

        elif msg_type == "response.audio_transcript.delta":
            # Customer speaking (model output)
            transcript = msg.get("delta", "")
            if transcript:
                self._emit_transcript_output(transcript, current_time)

        elif msg_type == "conversation.item.input_audio_transcription.completed":
            # Agent speaking (input transcription)
            transcript = msg.get("transcript", "")
            if transcript:
                self._emit_transcript_input(transcript, current_time)

        elif msg_type == "response.audio.delta":
            # Audio output from model
            audio_b64 = msg.get("delta", "")
            if audio_b64:
                await self._emit_audio_output(audio_b64, current_time)

        elif msg_type == "response.done":
            if self._on_response_done:
                self._on_response_done()
