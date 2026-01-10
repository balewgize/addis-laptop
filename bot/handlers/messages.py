"""Natural language message handlers."""

import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from core.database import Database
from core.recommender import LLMRecommender
from bot.constants import ITEMS_PER_PAGE
from bot.parser import QueryParser, ParsedQuery
from bot.utils import (
    format_laptop_short,
    format_recommendations,
    build_pagination_keyboard,
    PaginationState,
)

logger = logging.getLogger(__name__)


class MessageHandlers:
    """Handlers for natural language messages."""

    def __init__(
        self, db: Database, recommender: LLMRecommender, query_parser: QueryParser
    ):
        self.db = db
        self.recommender = recommender
        self.query_parser = query_parser

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle free-form natural language queries (text or transcribed voice)."""
        text = update.message.text
        user_id = update.effective_user.id

        if not text or not text.strip():
            await update.message.reply_text("Please send a text or voice message.")
            return

        logger.info(f"User {user_id}: {text}")

        await update.message.reply_text("🔍 Understanding your request...")

        parsed = self.query_parser.parse(text)

        # Decide: recommendation or search
        recommend_keywords = [
            "recommend",
            "suggest",
            "best",
            "good for",
            "ጥሩ",
            "የሚመከር",
            "ምርጥ",
        ]
        is_recommend = parsed.use_case is not None or any(
            w in text.lower() for w in recommend_keywords
        )

        if is_recommend:
            await self._nl_recommend(update, context, parsed)
        else:
            await self._nl_search(update, context, parsed)

    async def _nl_search(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: ParsedQuery
    ):
        """Handle natural language search."""
        filters = parsed.to_search_filters()
        laptops = self.db.search_laptops(filters)

        # Filter by screen in memory
        if parsed.min_screen:
            laptops = [
                lap
                for lap in laptops
                if lap.screen_size and lap.screen_size >= parsed.min_screen
            ]

        if not laptops:
            await update.message.reply_text(
                f"😔 No results for: _{parsed.summary()}_\n\nTry /search",
                parse_mode="Markdown",
            )
            return

        total = len(laptops)
        state = PaginationState(command="search", page=1, total_items=total)
        context.user_data["pagination"] = state
        context.user_data["search_results"] = laptops

        page_laptops = laptops[:ITEMS_PER_PAGE]
        start, end = 1, min(ITEMS_PER_PAGE, total)

        lines = [
            f"🔍 **Results** ({start}-{end} of {total})",
            f"_{parsed.summary()}_",
            "",
        ]
        for i, laptop in enumerate(page_laptops, start=1):
            lines.append(format_laptop_short(laptop, i))
        lines.append("\nUse /search to search again.")

        keyboard = build_pagination_keyboard(state, "search")

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

    async def _nl_recommend(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: ParsedQuery
    ):
        """Handle natural language recommendation."""
        request = parsed.to_recommendation_request()

        await update.message.reply_text("🤖 Finding best laptops...")

        response = self.recommender.recommend(request, limit=3)

        if not response.recommendations:
            await update.message.reply_text(
                f"😔 No results for: _{parsed.summary()}_\n\nTry /recommend",
                parse_mode="Markdown",
            )
            return

        message = format_recommendations(response)
        await update.message.reply_text(
            message, parse_mode="Markdown", disable_web_page_preview=True
        )

    async def cancel_conversation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Cancel any conversation and return to main menu."""
        context.user_data.pop("search_filters", None)
        context.user_data.pop("recommend_filters", None)
        context.user_data.pop("pagination", None)
        context.user_data.pop("search_results", None)

        await update.message.reply_text(
            "Cancelled.\n\nUse /browse, /search, or /recommend to start again."
        )
        return ConversationHandler.END

    async def handle_unexpected_text(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle unexpected text during conversation — exit and process as NL."""
        context.user_data.pop("search_filters", None)
        context.user_data.pop("recommend_filters", None)

        await update.message.reply_text("↩️ Exiting current flow...")
        await self.handle_message(update, context)

        return ConversationHandler.END
