"""
Gemini Live API provider integration.
"""

import asyncio
import json
import logging
from typing import Optional, Callable, Awaitable

import websockets

from ..config import GEMINI_API_KEY, GEMINI_MODEL
from .base import BaseProvider

logger = logging.getLogger("eval-runner")


class GeminiProvider(BaseProvider):
    """Gemini Live API provider for real-time audio conversations."""

    WEBSOCKET_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"

    def __init__(
        self,
        on_audio_output: Optional[Callable[[str, float], Awaitable[None]]] = None,
        on_transcript_output: Optional[Callable[[str, float], None]] = None,
        on_transcript_input: Optional[Callable[[str, float], None]] = None,
        on_ready: Optional[Callable[[], None]] = None,
        on_turn_complete: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize Gemini provider.

        Args:
            on_audio_output: Callback for audio output (base64, timestamp)
            on_transcript_output: Callback for customer transcription (text, timestamp)
            on_transcript_input: Callback for agent transcription (text, timestamp)
            on_ready: Callback when provider is ready
            on_turn_complete: Callback when a turn is complete
        """
        super().__init__(
            on_audio_output=on_audio_output,
            on_transcript_output=on_transcript_output,
            on_transcript_input=on_transcript_input,
            on_ready=on_ready,
        )
        self._on_turn_complete = on_turn_complete

    async def connect(self, system_instruction: str, voice: str) -> None:
        """
        Connect to Gemini WebSocket API.

        Args:
            system_instruction: System prompt for the conversation
            voice: Gemini voice name (Puck, Charon, Kore, etc.)
        """
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY not set")

        ws_url = f"{self.WEBSOCKET_URL}?key={GEMINI_API_KEY}"
        self.ws = await websockets.connect(ws_url)

        setup_message = {
            "setup": {
                "model": f"models/{GEMINI_MODEL}",
                "generation_config": {
                    "response_modalities": ["AUDIO"],
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {"voice_name": voice}
                        }
                    },
                    "thinking_config": {"thinking_budget": 0},
                },
                "output_audio_transcription": {},
                "input_audio_transcription": {},
                "system_instruction": {"parts": [{"text": system_instruction}]},
            }
        }

        await self.ws.send(json.dumps(setup_message))
        logger.info(f"Gemini: Connected with voice {voice}")

    async def send_audio(self, audio_b64: str) -> None:
        """
        Send audio to Gemini.

        Args:
            audio_b64: Base64 encoded PCM16 audio at 16kHz
        """
        if not self.ws:
            return
        try:
            await self.ws.send(json.dumps({
                "realtimeInput": {
                    "mediaChunks": [
                        {"mimeType": "audio/pcm;rate=16000", "data": audio_b64}
                    ]
                }
            }))
        except Exception:
            pass

    async def send_text(self, text: str) -> None:
        """
        Send text message to Gemini.

        Args:
            text: Text message to send
        """
        if not self.ws:
            return
        try:
            await self.ws.send(json.dumps({
                "clientContent": {
                    "turns": [{"role": "user", "parts": [{"text": text}]}],
                    "turnComplete": True
                }
            }))
        except Exception as e:
            logger.error(f"Gemini: Error sending text: {e}")

    async def listen(self) -> None:
        """Listen for Gemini WebSocket messages."""
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
            logger.error(f"Gemini: Error in listener: {e}")

    async def _handle_message(self, msg: dict) -> None:
        """
        Handle a Gemini WebSocket message.

        Args:
            msg: Parsed JSON message
        """
        current_time = asyncio.get_event_loop().time()

        if "setupComplete" in msg:
            self._emit_ready()
            logger.info("Gemini: Setup complete")

        elif "serverContent" in msg:
            server_content = msg["serverContent"]

            # Handle turn completion
            if server_content.get("turnComplete") or server_content.get("interrupted"):
                if self._on_turn_complete:
                    self._on_turn_complete()

            # Customer speaking (output transcription)
            if "outputTranscription" in server_content:
                transcript = server_content["outputTranscription"].get("text", "")
                if transcript:
                    self._emit_transcript_output(transcript, current_time)

            # Agent speaking (input transcription)
            if "inputTranscription" in server_content:
                transcript = server_content["inputTranscription"].get("text", "")
                if transcript:
                    self._emit_transcript_input(transcript, current_time)

            # Handle audio output
            model_turn = server_content.get("modelTurn", {})
            for part in model_turn.get("parts", []):
                if "inlineData" in part:
                    inline_data = part["inlineData"]
                    if "audio" in inline_data.get("mimeType", ""):
                        audio_b64 = inline_data.get("data", "")
                        if audio_b64:
                            await self._emit_audio_output(audio_b64, current_time)
