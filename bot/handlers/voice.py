"""Voice message handler."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from core.config import get_settings
from bot.transcriber import Transcriber, TranscriptionError, AudioTooLongError

logger = logging.getLogger(__name__)


class VoiceHandler:
    """Handle voice messages."""

    def __init__(self, transcriber: Transcriber, message_handler_callback):
        """
        Args:
            transcriber: Transcriber instance
            message_handler_callback: Function to process transcribed text
                                      (MessageHandlers.handle_message)
        """
        self.settings = get_settings()
        self.transcriber = transcriber
        self.process_text = message_handler_callback

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process voice message."""
        voice = update.message.voice
        user_id = update.effective_user.id

        logger.info(f"Voice from user {user_id}: {voice.duration}s")

        # Check duration before downloading
        if voice.duration > self.settings.max_audio_duration_seconds:
            await update.message.reply_text(
                f"⚠️ Voice too long ({voice.duration}s).\n\n"
                f"Please keep under {self.settings.max_audio_duration_seconds} seconds or type your query."
            )
            return

        status_msg = await update.message.reply_text("🎤 Transcribing...")

        try:
            file = await voice.get_file()
            audio_bytes = await file.download_as_bytearray()

            text = self.transcriber.transcribe(bytes(audio_bytes), voice.duration)

            await status_msg.edit_text(f"📝 _{text}_", parse_mode="Markdown")

            # Process as text query
            fake_update = Update(
                update_id=update.update_id,
                message=update.message,
            )
            fake_update.message._unfreeze()
            fake_update.message.text = text
            await self.process_text(fake_update, context)

        except AudioTooLongError:
            await update.message.reply_text(
                f"⚠️ Please keep voice under {self.settings.max_audio_duration_seconds} seconds."
            )
        except TranscriptionError as e:
            logger.warning(f"Transcription failed for user {user_id}: {e}")
            await update.message.reply_text(
                "❌ Couldn't transcribe audio.\n\nPlease type your query or try again."
            )
        except Exception as e:
            logger.exception(f"Voice handling error: {e}")
            await update.message.reply_text(
                "❌ Something went wrong.\n\nPlease type your query."
            )
