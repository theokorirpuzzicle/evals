"""
Audio mixing utilities for combining agent and customer audio streams.
"""

from typing import List, Tuple, Optional
import numpy as np

from .config import AGENT_SAMPLE_RATE, CUSTOMER_SAMPLE_RATE, OUTPUT_SAMPLE_RATE


class AudioMixer:
    """Handles mixing of agent and customer audio streams into a single file."""

    def __init__(self, output_sample_rate: int = OUTPUT_SAMPLE_RATE):
        self.output_sample_rate = output_sample_rate
        self.agent_chunks: List[Tuple[float, bytes]] = []
        self.customer_chunks: List[Tuple[float, bytes]] = []
        self.start_time: Optional[float] = None
        self.agent_next_time: float = 0.0  # Track expected next agent audio time
        self.customer_next_time: float = 0.0  # Track expected next customer audio time

    def set_start_time(self, start_time: float):
        self.start_time = start_time

    def add_agent_audio(self, audio_bytes: bytes, timestamp: float):
        if self.start_time is None:
            self.start_time = timestamp
        relative_time = timestamp - self.start_time

        # Prevent overlapping: if timestamp suggests overlap, use sequential placement
        duration = len(audio_bytes) / 2 / AGENT_SAMPLE_RATE
        if relative_time < self.agent_next_time:
            # This chunk would overlap previous audio, place it sequentially instead
            relative_time = self.agent_next_time

        self.agent_chunks.append((relative_time, audio_bytes))
        self.agent_next_time = relative_time + duration

    def add_customer_audio(self, audio_bytes: bytes, timestamp: float):
        if self.start_time is None:
            self.start_time = timestamp
        relative_time = timestamp - self.start_time

        # Prevent overlapping: if timestamp suggests overlap, use sequential placement
        duration = len(audio_bytes) / 2 / CUSTOMER_SAMPLE_RATE
        if relative_time < self.customer_next_time:
            # This chunk would overlap previous audio, place it sequentially instead
            relative_time = self.customer_next_time

        self.customer_chunks.append((relative_time, audio_bytes))
        self.customer_next_time = relative_time + duration

    def resample_audio(self, audio_data: bytes, from_rate: int, to_rate: int) -> bytes:
        if from_rate == to_rate:
            return audio_data

        samples = np.frombuffer(audio_data, dtype=np.int16)
        duration = len(samples) / from_rate
        new_length = int(duration * to_rate)

        if new_length == 0:
            return b""

        old_indices = np.arange(len(samples))
        new_indices = np.linspace(0, len(samples) - 1, new_length)
        resampled = np.interp(new_indices, old_indices, samples).astype(np.int16)

        return resampled.tobytes()

    def mix_audio(self) -> bytes:
        """Mix agent and customer audio into a single timeline."""
        if not self.agent_chunks and not self.customer_chunks:
            return b""

        max_time = 0

        for timestamp, audio_bytes in self.agent_chunks:
            duration = len(audio_bytes) / 2 / AGENT_SAMPLE_RATE
            end_time = timestamp + duration
            max_time = max(max_time, end_time)

        for timestamp, audio_bytes in self.customer_chunks:
            duration = len(audio_bytes) / 2 / CUSTOMER_SAMPLE_RATE
            end_time = timestamp + duration
            max_time = max(max_time, end_time)

        total_samples = int((max_time + 1) * self.output_sample_rate)

        # Create separate channels for agent and customer, then mix properly
        agent_track = np.zeros(total_samples, dtype=np.float32)
        customer_track = np.zeros(total_samples, dtype=np.float32)

        # IMPROVED: Sort and concatenate agent chunks first, then place smoothly
        # This avoids applying crossfade to every individual chunk in the mix
        if self.agent_chunks:
            sorted_agent = sorted(self.agent_chunks, key=lambda x: x[0])

            # Build continuous segments (chunks that should be concatenated)
            segments = []
            current_segment = []
            current_segment_start = None
            last_end_time = None

            for timestamp, audio_bytes in sorted_agent:
                duration = len(audio_bytes) / 2 / AGENT_SAMPLE_RATE

                # If this chunk continues from the previous (within 100ms), add to segment
                if last_end_time is None or abs(timestamp - last_end_time) < 0.1:
                    if current_segment_start is None:
                        current_segment_start = timestamp
                    current_segment.append(audio_bytes)
                else:
                    # Gap detected, save current segment and start new one
                    if current_segment:
                        segments.append((current_segment_start, current_segment))
                    current_segment = [audio_bytes]
                    current_segment_start = timestamp

                last_end_time = timestamp + duration

            # Don't forget the last segment
            if current_segment:
                segments.append((current_segment_start, current_segment))

            # Now place each segment smoothly
            for seg_start, seg_chunks in segments:
                # Concatenate chunks in this segment
                concatenated = b''.join(seg_chunks)

                # Resample to output rate
                resampled = self.resample_audio(
                    concatenated, AGENT_SAMPLE_RATE, self.output_sample_rate
                )
                samples = np.frombuffer(resampled, dtype=np.int16).astype(np.float32)

                # Place in track
                start_sample = int(seg_start * self.output_sample_rate)
                end_sample = start_sample + len(samples)

                if end_sample > len(agent_track):
                    end_sample = len(agent_track)
                    samples = samples[: end_sample - start_sample]

                if len(samples) > 0:
                    agent_track[start_sample:end_sample] = samples

        # Add customer audio to its track with crossfade smoothing
        crossfade_samples = 80  # ~3.3ms at 24kHz for customer chunk boundaries
        for timestamp, audio_bytes in self.customer_chunks:
            resampled = self.resample_audio(
                audio_bytes, CUSTOMER_SAMPLE_RATE, self.output_sample_rate
            )
            samples = np.frombuffer(resampled, dtype=np.int16).astype(np.float32)

            start_sample = int(timestamp * self.output_sample_rate)
            end_sample = start_sample + len(samples)

            if end_sample > len(customer_track):
                end_sample = len(customer_track)
                samples = samples[: end_sample - start_sample]

            if len(samples) > 0:
                # Apply fade in/out to prevent clicks at chunk boundaries
                fade_len = min(crossfade_samples, len(samples) // 2)
                if fade_len > 0:
                    # Fade in at start
                    fade_in = np.linspace(0.0, 1.0, fade_len)
                    samples[:fade_len] *= fade_in

                    # Fade out at end
                    fade_out = np.linspace(1.0, 0.0, fade_len)
                    samples[-fade_len:] *= fade_out

                customer_track[start_sample:end_sample] += samples

        # Normalize each track to similar RMS levels before mixing
        # This ensures both speakers have balanced volume
        agent_rms = np.sqrt(np.mean(agent_track**2))
        customer_rms = np.sqrt(np.mean(customer_track**2))

        # Target RMS level for balanced audio
        target_rms = 8000.0  # Good level with headroom

        if agent_rms > 0:
            agent_gain = target_rms / agent_rms
            agent_track = agent_track * agent_gain

        if customer_rms > 0:
            customer_gain = target_rms / customer_rms
            customer_track = customer_track * customer_gain

        # Mix the normalized tracks with slight attenuation to prevent clipping
        mixed = (agent_track * 0.7) + (customer_track * 0.7)

        # Final safety clip to handle any edge cases
        mixed = np.clip(mixed, -32768, 32767)

        return mixed.astype(np.int16).tobytes()

    def get_agent_audio(self) -> bytes:
        """Get concatenated agent audio with smoothing at chunk boundaries."""
        if not self.agent_chunks:
            return b""

        sorted_chunks = sorted(self.agent_chunks, key=lambda x: x[0])

        # Simple concatenation if only one chunk
        if len(sorted_chunks) == 1:
            return sorted_chunks[0][1]

        # Concatenate with crossfade smoothing to prevent clicks/pops
        result = []
        crossfade_samples = 80  # ~5ms at 16kHz

        for i, (timestamp, chunk_bytes) in enumerate(sorted_chunks):
            samples = np.frombuffer(chunk_bytes, dtype=np.int16).copy()  # Make writable copy

            if i == 0:
                # First chunk: no modification
                result.append(samples)
            else:
                # Apply crossfade with previous chunk's end
                if len(result) > 0 and len(samples) > 0:
                    prev_samples = result[-1]

                    # Only crossfade if both chunks have enough samples
                    if len(prev_samples) >= crossfade_samples and len(samples) >= crossfade_samples:
                        # Create fade out for end of previous chunk
                        fade_out = np.linspace(1.0, 0.0, crossfade_samples)
                        prev_samples[-crossfade_samples:] = (
                            prev_samples[-crossfade_samples:] * fade_out
                        ).astype(np.int16)

                        # Create fade in for start of current chunk
                        fade_in = np.linspace(0.0, 1.0, crossfade_samples)
                        samples[:crossfade_samples] = (
                            samples[:crossfade_samples] * fade_in
                        ).astype(np.int16)

                result.append(samples)

        # Concatenate all smoothed chunks
        if not result:
            return b""

        concatenated = np.concatenate(result)
        return concatenated.tobytes()

    def get_customer_audio(self) -> bytes:
        """Get concatenated customer audio with smoothing at chunk boundaries."""
        if not self.customer_chunks:
            return b""

        sorted_chunks = sorted(self.customer_chunks, key=lambda x: x[0])

        # Simple concatenation if only one chunk
        if len(sorted_chunks) == 1:
            return sorted_chunks[0][1]

        # Concatenate with crossfade smoothing to prevent clicks/pops
        result = []
        crossfade_samples = 80  # ~5ms at 16kHz or ~3.3ms at 24kHz

        for i, (timestamp, chunk_bytes) in enumerate(sorted_chunks):
            samples = np.frombuffer(chunk_bytes, dtype=np.int16).copy()  # Make writable copy

            if i == 0:
                # First chunk: no modification
                result.append(samples)
            else:
                # Apply crossfade with previous chunk's end
                if len(result) > 0 and len(samples) > 0:
                    prev_samples = result[-1]

                    # Only crossfade if both chunks have enough samples
                    if len(prev_samples) >= crossfade_samples and len(samples) >= crossfade_samples:
                        # Create fade out for end of previous chunk
                        fade_out = np.linspace(1.0, 0.0, crossfade_samples)
                        prev_samples[-crossfade_samples:] = (
                            prev_samples[-crossfade_samples:] * fade_out
                        ).astype(np.int16)

                        # Create fade in for start of current chunk
                        fade_in = np.linspace(0.0, 1.0, crossfade_samples)
                        samples[:crossfade_samples] = (
                            samples[:crossfade_samples] * fade_in
                        ).astype(np.int16)

                result.append(samples)

        # Concatenate all smoothed chunks
        if not result:
            return b""

        concatenated = np.concatenate(result)
        return concatenated.tobytes()
