"""Speech-to-text using Hasab AI (preferred) or ElevenLabs API (fallback)."""

import logging
from abc import ABC, abstractmethod

import httpx

from core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    """Transcription failed."""

    pass


class AudioTooLongError(TranscriptionError):
    """Audio exceeds max duration."""

    pass


class BaseTranscriber(ABC):
    """Abstract base class for transcription services."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    @abstractmethod
    def transcribe(self, audio_bytes: bytes, duration_seconds: float) -> str:
        """Transcribe audio to text."""
        pass

    @abstractmethod
    def close(self):
        """Close resources."""
        pass


class HasabAITranscriber(BaseTranscriber):
    """Hasab AI STT wrapper (preferred for Amharic)."""

    def __init__(self, settings: Settings | None = None):
        super().__init__(settings)
        self.client = httpx.Client(
            base_url="https://hasab.co/api/v1",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.settings.hasab_ai_api_key}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            },
            timeout=30.0,
        )
        logger.info("HasabAITranscriber initialized")

    def transcribe(self, audio_bytes: bytes, duration_seconds: float) -> str:
        """Transcribe audio to text using Hasab AI."""
        if duration_seconds > self.settings.max_audio_duration_seconds:
            logger.warning(f"Audio too long: {duration_seconds:.1f}s")
            raise AudioTooLongError(
                f"Audio must be under {self.settings.max_audio_duration_seconds} seconds"
            )

        logger.info(f"Transcribing {duration_seconds:.1f}s audio with Hasab AI")

        try:
            response = self.client.post(
                "/upload-audio",
                files={"audio": ("audio.ogg", audio_bytes, "audio/ogg")},
                data={"transcribe": "true"},
            )
            response.raise_for_status()

            data = response.json()
            text = data.get("transcription", "").strip()

            if not text:
                raise TranscriptionError("Empty transcription from Hasab AI")

            logger.info(f"Transcribed (Hasab AI): {text[:50]}...")
            return text

        except httpx.HTTPStatusError as e:
            logger.error(f"Hasab AI API error: {e.response.status_code}")
            raise TranscriptionError("Hasab AI transcription service error")
        except httpx.RequestError as e:
            logger.exception("Hasab AI request failed:")
            raise TranscriptionError("Could not reach Hasab AI transcription service")
        except Exception as e:
            logger.exception("Hasab AI transcription failed:")
            raise TranscriptionError("Hasab AI transcription failed")

    def close(self):
        """Close HTTP client."""
        self.client.close()
        logger.debug("HasabAITranscriber closed")


class ElevenLabsTranscriber(BaseTranscriber):
    """ElevenLabs STT wrapper (fallback)."""

    def __init__(self, settings: Settings | None = None):
        super().__init__(settings)
        self.client = httpx.Client(
            base_url="https://api.elevenlabs.io/v1",
            headers={"xi-api-key": self.settings.elevenlabs_api_key},
            timeout=30.0,
        )
        logger.info("ElevenLabsTranscriber initialized")

    def transcribe(self, audio_bytes: bytes, duration_seconds: float) -> str:
        """Transcribe audio to text using ElevenLabs."""
        if duration_seconds > self.settings.max_audio_duration_seconds:
            logger.warning(f"Audio too long: {duration_seconds:.1f}s")
            raise AudioTooLongError(
                f"Audio must be under {self.settings.max_audio_duration_seconds} seconds"
            )

        logger.info(f"Transcribing {duration_seconds:.1f}s audio with ElevenLabs")

        try:
            response = self.client.post(
                "/speech-to-text",
                files={"file": ("audio.ogg", audio_bytes, "audio/ogg")},
                data={"model_id": "scribe_v2", "language_code": "am"},
            )
            response.raise_for_status()

            text = response.json().get("text", "").strip()

            if not text:
                raise TranscriptionError("Empty transcription from ElevenLabs")

            logger.info(f"Transcribed (ElevenLabs): {text[:50]}...")
            return text

        except httpx.HTTPStatusError as e:
            logger.error(f"ElevenLabs API error: {e.response.status_code}")
            raise TranscriptionError("ElevenLabs transcription service error")
        except httpx.RequestError as e:
            logger.exception("ElevenLabs request failed:")
            raise TranscriptionError("Could not reach ElevenLabs transcription service")
        except Exception as e:
            logger.exception("ElevenLabs transcription failed:")
            raise TranscriptionError("ElevenLabs transcription failed")

    def close(self):
        """Close HTTP client."""
        self.client.close()
        logger.debug("ElevenLabsTranscriber closed")


class Transcriber:
    """Transcriber that uses Hasab AI or ElevenLabs."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._transcriber: BaseTranscriber

        if self.settings.hasab_ai_api_key:
            self._transcriber = HasabAITranscriber(self.settings)
            logger.info("Using Hasab AI for transcription")
        elif self.settings.elevenlabs_api_key:
            self._transcriber = ElevenLabsTranscriber(self.settings)
            logger.info("Using ElevenLabs for transcription (Hasab AI key not set)")
        else:
            raise ValueError(
                "No transcription API key configured (HASAB_AI_API_KEY or ELEVENLABS_API_KEY)"
            )

    def transcribe(self, audio_bytes: bytes, duration_seconds: float) -> str:
        """Transcribe audio to text."""
        return self._transcriber.transcribe(audio_bytes, duration_seconds)

    def close(self):
        """Close HTTP client."""
        self._transcriber.close()
