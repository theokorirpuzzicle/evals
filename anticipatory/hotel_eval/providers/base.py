"""
Base provider interface for AI integrations.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, Awaitable

import websockets

logger = logging.getLogger("eval-runner")


class BaseProvider(ABC):
    """Abstract base class for AI provider integrations."""

    def __init__(
        self,
        on_audio_output: Optional[Callable[[str, float], Awaitable[None]]] = None,
        on_transcript_output: Optional[Callable[[str, float], None]] = None,
        on_transcript_input: Optional[Callable[[str, float], None]] = None,
        on_ready: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize the provider.

        Args:
            on_audio_output: Callback for audio output (base64, timestamp)
            on_transcript_output: Callback for output transcription (text, timestamp)
            on_transcript_input: Callback for input transcription (text, timestamp)
            on_ready: Callback when provider is ready
        """
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.ready_event = asyncio.Event()

        # Callbacks
        self._on_audio_output = on_audio_output
        self._on_transcript_output = on_transcript_output
        self._on_transcript_input = on_transcript_input
        self._on_ready = on_ready

    @abstractmethod
    async def connect(self, system_instruction: str, voice: str) -> None:
        """
        Connect to the provider and initialize the session.

        Args:
            system_instruction: System prompt for the conversation
            voice: Voice to use for audio output
        """
        pass

    @abstractmethod
    async def send_audio(self, audio_b64: str) -> None:
        """
        Send audio input to the provider.

        Args:
            audio_b64: Base64 encoded audio data
        """
        pass

    @abstractmethod
    async def send_text(self, text: str) -> None:
        """
        Send text input to the provider.

        Args:
            text: Text message to send
        """
        pass

    @abstractmethod
    async def listen(self) -> None:
        """Listen for messages from the provider."""
        pass

    async def wait_ready(self, timeout: float = 10) -> None:
        """
        Wait for the provider to be ready.

        Args:
            timeout: Maximum time to wait in seconds

        Raises:
            RuntimeError: If provider doesn't become ready within timeout
        """
        try:
            await asyncio.wait_for(self.ready_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(f"{self.__class__.__name__} setup failed - timeout")

    async def close(self) -> None:
        """Close the provider connection."""
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None

    async def ping(self) -> None:
        """Send a ping to keep the connection alive."""
        if self.ws:
            try:
                await self.ws.ping()
            except Exception:
                pass

    def _emit_ready(self) -> None:
        """Emit the ready event and call the callback."""
        self.ready_event.set()
        if self._on_ready:
            self._on_ready()

    async def _emit_audio_output(self, audio_b64: str, timestamp: float) -> None:
        """Emit audio output to callback."""
        if self._on_audio_output:
            await self._on_audio_output(audio_b64, timestamp)

    def _emit_transcript_output(self, text: str, timestamp: float) -> None:
        """Emit output transcription to callback."""
        if self._on_transcript_output:
            self._on_transcript_output(text, timestamp)

    def _emit_transcript_input(self, text: str, timestamp: float) -> None:
        """Emit input transcription to callback."""
        if self._on_transcript_input:
            self._on_transcript_input(text, timestamp)
