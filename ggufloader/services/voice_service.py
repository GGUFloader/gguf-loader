"""
VoiceService - Voice-to-text input using Whisper.

Inspired by Aider's voice.py which uses OpenAI's Whisper model for
voice coding. This implementation provides a simple recording + transcription
pipeline that can be triggered from a microphone button.

Source: aider/aider/voice.py
"""

from __future__ import annotations

import io
import logging
import tempfile
import threading
import wave
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import audio libraries
try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False

try:
    import whisper
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False


class VoiceService:
    """Records audio from microphone and transcribes with Whisper.

    Usage:
        voice = VoiceService()
        if voice.is_available():
            text = voice.record_and_transcribe(timeout=10)
    """

    def __init__(self, model_name: str = "base") -> None:
        self.model_name = model_name
        self._model = None
        self._recording = False
        self._audio_data: Optional[bytes] = None

    def is_available(self) -> bool:
        """Check if voice input is available."""
        return HAS_PYAUDIO and HAS_WHISPER

    def _ensure_model(self) -> None:
        """Lazily load the Whisper model."""
        if self._model is None:
            logger.info("Loading Whisper model: %s", self.model_name)
            self._model = whisper.load_model(self.model_name)

    def record_audio(self, duration: int = 10, sample_rate: int = 16000) -> Optional[bytes]:
        """Record audio from microphone.

        Args:
            duration: Maximum recording duration in seconds
            sample_rate: Audio sample rate

        Returns:
            WAV audio bytes, or None on failure
        """
        if not HAS_PYAUDIO:
            logger.warning("pyaudio not installed. Install with: pip install pyaudio")
            return None

        try:
            pa = pyaudio.PyAudio()
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=sample_rate,
                input=True,
                frames_per_buffer=1024,
            )

            frames = []
            for _ in range(0, int(sample_rate / 1024 * duration)):
                data = stream.read(1024, exception_on_overflow=False)
                frames.append(data)

            stream.stop_stream()
            stream.close()
            pa.terminate()

            # Convert to WAV
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(b"".join(frames))

            return buf.getvalue()

        except Exception as e:
            logger.error("Audio recording failed: %s", e)
            return None

    def transcribe(self, audio_data: bytes) -> Optional[str]:
        """Transcribe audio using Whisper.

        Args:
            audio_data: WAV audio bytes

        Returns:
            Transcribed text, or None on failure
        """
        if not HAS_WHISPER:
            logger.warning("whisper not installed. Install with: pip install openai-whisper")
            return None

        try:
            self._ensure_model()

            # Write to temp file for Whisper
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_data)
                temp_path = f.name

            result = self._model.transcribe(temp_path)

            # Clean up
            import os
            os.unlink(temp_path)

            text = result.get("text", "").strip()
            if text:
                logger.info("Voice transcription: %s", text[:100])
            return text

        except Exception as e:
            logger.error("Transcription failed: %s", e)
            return None

    def record_and_transcribe(self, duration: int = 10) -> Optional[str]:
        """Record audio and transcribe in one call.

        Args:
            duration: Maximum recording duration in seconds

        Returns:
            Transcribed text, or None on failure
        """
        audio = self.record_audio(duration)
        if audio is None:
            return None
        return self.transcribe(audio)


class VoiceServiceThread(threading.Thread):
    """Non-blocking voice service that runs in a background thread.

    Usage:
        service = VoiceServiceThread()
        service.start_recording(duration=10)
        # ... do other work ...
        text = service.get_result()  # blocks until done
    """

    def __init__(self, model_name: str = "base") -> None:
        super().__init__(daemon=True)
        self._voice = VoiceService(model_name)
        self._result: Optional[str] = None
        self._error: Optional[str] = None
        self._duration = 10
        self._done = threading.Event()

    def is_available(self) -> bool:
        return self._voice.is_available()

    def start_recording(self, duration: int = 10) -> None:
        """Start recording in background thread."""
        self._duration = duration
        self._result = None
        self._error = None
        self._done.clear()
        self.start()

    def run(self) -> None:
        try:
            self._result = self._voice.record_and_transcribe(self._duration)
        except Exception as e:
            self._error = str(e)
        finally:
            self._done.set()

    def get_result(self, timeout: float = 30) -> Optional[str]:
        """Get the transcription result (blocks until done)."""
        self._done.wait(timeout)
        if self._error:
            logger.error("Voice service error: %s", self._error)
            return None
        return self._result

    def is_done(self) -> bool:
        return self._done.is_set()
