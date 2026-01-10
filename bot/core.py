"""Core bot class and entry point."""

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

from core.config import Settings, get_settings, setup_logging
from core.database import Database
from core.recommender import LLMRecommender

from bot.constants import ConvState
from bot.parser import QueryParser
from bot.transcriber import Transcriber
from bot.handlers import (
    CommandHandlers,
    SearchHandlers,
    RecommendHandlers,
    MessageHandlers,
    VoiceHandler,
)

logger = setup_logging()


class LaptopBot:
    """Telegram bot for laptop search and recommendations."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.db = Database()
        self.recommender = LLMRecommender(self.db)
        self.query_parser = QueryParser(self.settings)

        # Initialize handlers
        self.command_handlers = CommandHandlers(self.db)
        self.search_handlers = SearchHandlers(self.db)
        self.recommend_handlers = RecommendHandlers(self.recommender)
        self.message_handlers = MessageHandlers(
            self.db, self.recommender, self.query_parser
        )

        # Optional: voice search
        self.transcriber = None
        self.voice_handler = None
        if self.settings.elevenlabs_api_key != "":
            self.transcriber = Transcriber(self.settings)
            self.voice_handler = VoiceHandler(
                self.transcriber, self.message_handlers.handle_message
            )
            logger.info("Voice search enabled")

        logger.info("LaptopBot initialized")

    def run(self):
        """Run the bot."""
        if not self.settings.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set")

        app = Application.builder().token(self.settings.telegram_bot_token).build()

        self._register_handlers(app)

        logger.info("Starting bot...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

    def _register_handlers(self, app: Application):
        """Register all bot handlers."""
        # Shared fallbacks for conversations
        shared_fallbacks = [
            CommandHandler("cancel", self.message_handlers.cancel_conversation),
            CommandHandler("help", self.command_handlers.help_command),
            CommandHandler("search", self.search_handlers.search_start),
            CommandHandler("recommend", self.recommend_handlers.recommend_start),
            CommandHandler("browse", self.command_handlers.browse),
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.message_handlers.handle_unexpected_text,
            ),
        ]

        # Search conversation
        search_conv = ConversationHandler(
            entry_points=[CommandHandler("search", self.search_handlers.search_start)],
            states={
                ConvState.SEARCH_BRAND: [
                    CallbackQueryHandler(
                        self.search_handlers.search_brand, pattern="^sbrand:"
                    )
                ],
                ConvState.SEARCH_PRICE: [
                    CallbackQueryHandler(
                        self.search_handlers.search_price, pattern="^sprice:"
                    )
                ],
                ConvState.SEARCH_RAM: [
                    CallbackQueryHandler(
                        self.search_handlers.search_ram, pattern="^sram:"
                    )
                ],
                ConvState.SEARCH_SCREEN: [
                    CallbackQueryHandler(
                        self.search_handlers.search_screen, pattern="^sscreen:"
                    )
                ],
            },
            fallbacks=shared_fallbacks,
            per_message=False,
        )

        # Recommend conversation
        recommend_conv = ConversationHandler(
            entry_points=[
                CommandHandler("recommend", self.recommend_handlers.recommend_start)
            ],
            states={
                ConvState.RECOMMEND_USE_CASE: [
                    CallbackQueryHandler(
                        self.recommend_handlers.recommend_use_case, pattern="^ruse:"
                    )
                ],
                ConvState.RECOMMEND_BUDGET: [
                    CallbackQueryHandler(
                        self.recommend_handlers.recommend_budget, pattern="^rbudget:"
                    )
                ],
                ConvState.RECOMMEND_SCREEN: [
                    CallbackQueryHandler(
                        self.recommend_handlers.recommend_screen, pattern="^rscreen:"
                    )
                ],
            },
            fallbacks=shared_fallbacks,
            per_message=False,
        )

        # 1. Basic commands
        app.add_handler(CommandHandler("start", self.command_handlers.start))
        app.add_handler(CommandHandler("help", self.command_handlers.help_command))
        app.add_handler(CommandHandler("browse", self.command_handlers.browse))

        # 2. Conversation handlers
        app.add_handler(search_conv)
        app.add_handler(recommend_conv)

        # 3. Pagination callbacks
        app.add_handler(
            CallbackQueryHandler(
                self.command_handlers.browse_pagination, pattern="^browse:"
            )
        )
        app.add_handler(
            CallbackQueryHandler(
                self.search_handlers.search_pagination, pattern="^search:"
            )
        )

        # 4. Noop callback (disabled buttons)
        app.add_handler(
            CallbackQueryHandler(self.command_handlers.handle_noop, pattern="^noop$")
        )

        # 5. Voice handler (optional)
        if self.voice_handler:
            app.add_handler(
                MessageHandler(filters.VOICE, self.voice_handler.handle_voice)
            )

        # 6. Natural language handler (must be last)
        app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, self.message_handlers.handle_message
            )
        )

    def close(self):
        """Cleanup resources."""
        self.query_parser.close()
        self.recommender.close()
        if self.transcriber:
            self.transcriber.close()


def run_bot():
    """Entry point for running the bot."""
    bot = LaptopBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        bot.close()


if __name__ == "__main__":
    run_bot()
