"""Speech-to-text using ElevenLabs API."""

import logging

import httpx

from core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    """Transcription failed."""

    pass


class AudioTooLongError(TranscriptionError):
    """Audio exceeds max duration."""

    pass


class Transcriber:
    """ElevenLabs STT wrapper."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.client = httpx.Client(
            base_url="https://api.elevenlabs.io/v1",
            headers={"xi-api-key": self.settings.elevenlabs_api_key},
            timeout=30.0,
        )

    def transcribe(self, audio_bytes: bytes, duration_seconds: float) -> str:
        """
        Transcribe audio to text.

        Args:
            audio_bytes: Audio file content
            duration_seconds: Audio duration

        Returns:
            Transcribed text

        Raises:
            AudioTooLongError: If audio exceeds limit
            TranscriptionError: If transcription fails
        """
        if duration_seconds > self.settings.max_audio_duration_seconds:
            logger.warning(f"Audio too long: {duration_seconds:.1f}s")
            raise AudioTooLongError(
                f"Audio must be under {self.settings.max_audio_duration_seconds} seconds"
            )

        logger.info(f"Transcribing {duration_seconds:.1f}s audio")

        try:
            response = self.client.post(
                "/speech-to-text",
                files={"file": ("audio.ogg", audio_bytes, "audio/ogg")},
                data={"model_id": "scribe_v2", "language_code": "am"},
            )
            response.raise_for_status()

            text = response.json().get("text", "").strip()

            if not text:
                raise TranscriptionError("Empty transcription")

            logger.info(f"Transcribed: {text[:50]}...")
            return text

        except httpx.HTTPStatusError as e:
            logger.error(f"ElevenLabs API error: {e.response.status_code}")
            raise TranscriptionError("Transcription service error")
        except httpx.RequestError as e:
            logger.exception(f"Request failed:")
            raise TranscriptionError("Could not reach transcription service")
        except Exception as e:
            logger.exception(f"Transcription failed:")
            raise TranscriptionError("Transcription failed")

    def close(self):
        """Close HTTP client."""
        self.client.close()
