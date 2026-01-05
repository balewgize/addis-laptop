"""Recommendation conversation handlers."""

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from core.recommender import LLMRecommender
from core.schemas import RecommendationRequest
from bot.constants import ConvState, PRICE_OPTIONS, SCREEN_OPTIONS
from bot.utils import format_recommendations

logger = logging.getLogger(__name__)


class RecommendHandlers:
    """Handlers for recommendation conversation flow."""

    def __init__(self, recommender: LLMRecommender):
        self.recommender = recommender

    async def recommend_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Start recommendation flow."""
        logger.info(f"User {update.effective_user.id} starting recommend")
        context.user_data["recommend_filters"] = {}

        keyboard = [
            [
                InlineKeyboardButton(
                    "💻 Programming", callback_data="ruse:programming"
                ),
                InlineKeyboardButton("🎮 Gaming", callback_data="ruse:gaming"),
            ],
            [
                InlineKeyboardButton("📊 Office/Work", callback_data="ruse:office"),
                InlineKeyboardButton("🎓 Student", callback_data="ruse:student"),
            ],
            [
                InlineKeyboardButton(
                    "🎬 Video Editing", callback_data="ruse:video_editing"
                ),
                InlineKeyboardButton(
                    "🤷 General Use", callback_data="ruse:general_use"
                ),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "🎯 **Get AI Recommendations**\n\n"
            "What will you mainly use the laptop for?\n\n"
            "_Type /cancel to exit_",
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )
        return ConvState.RECOMMEND_USE_CASE

    async def recommend_use_case(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle use case selection."""
        query = update.callback_query
        await query.answer()

        use_case = query.data.split(":")[1]
        if use_case != "any":
            logger.info(f"User {query.from_user.id} selected use case: {use_case}")
            context.user_data["recommend_filters"]["use_case"] = use_case

        buttons = [
            [
                InlineKeyboardButton(
                    f"Under {p // 1000}K", callback_data=f"rbudget:{p}"
                )
                for p in PRICE_OPTIONS[:2]
            ],
            [
                InlineKeyboardButton(
                    f"Under {p // 1000}K", callback_data=f"rbudget:{p}"
                )
                for p in PRICE_OPTIONS[2:]
            ],
            [InlineKeyboardButton("No Limit 💰", callback_data="rbudget:any")],
        ]

        use_display = (
            use_case.replace("_", " ").title() if use_case != "any" else "General"
        )
        await query.edit_message_text(
            f"🎯 **Get AI Recommendations**\n\n✅ Use: {use_display}\n\nBudget:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return ConvState.RECOMMEND_BUDGET

    async def recommend_budget(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle budget selection."""
        query = update.callback_query
        await query.answer()

        budget = query.data.split(":")[1]
        if budget != "any":
            context.user_data["recommend_filters"]["max_price"] = int(budget)

        buttons = [
            [
                InlineKeyboardButton(f'{s}"+ ', callback_data=f"rscreen:{s}")
                for s in SCREEN_OPTIONS[:2]
            ],
            [
                InlineKeyboardButton(f'{s}"+ ', callback_data=f"rscreen:{s}")
                for s in SCREEN_OPTIONS[2:]
            ],
            [InlineKeyboardButton("Any Size ↩️", callback_data="rscreen:any")],
        ]

        filters = context.user_data["recommend_filters"]
        summary = self._recommend_summary(filters)

        await query.edit_message_text(
            f"🎯 **Get AI Recommendations**\n\n{summary}\n\nScreen size:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return ConvState.RECOMMEND_SCREEN

    async def recommend_screen(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle screen selection and generate recommendations."""
        query = update.callback_query
        await query.answer()

        screen = query.data.split(":")[1]
        if screen != "any":
            context.user_data["recommend_filters"]["min_screen"] = float(screen)

        filters = context.user_data["recommend_filters"]
        summary = self._recommend_summary(filters)

        await query.edit_message_text(
            f"🎯 **Get AI Recommendations**\n\n{summary}\n\n🤖 Finding the best laptops...",
            parse_mode="Markdown",
        )

        await self._generate_recommendations(query, context, filters)
        return ConversationHandler.END

    async def _generate_recommendations(
        self, query, context: ContextTypes.DEFAULT_TYPE, filters: dict
    ):
        """Generate and display recommendations."""
        request = RecommendationRequest(
            budget_max=filters.get("max_price"),
            use_case=filters.get("use_case"),
            min_screen=filters.get("min_screen"),
        )

        response = self.recommender.recommend(request, limit=3)

        if not response.recommendations:
            await query.edit_message_text(
                "😔 No matching laptops found.\n\nTry /recommend with different options."
            )
            return

        message = format_recommendations(response)
        await query.edit_message_text(
            message, parse_mode="Markdown", disable_web_page_preview=True
        )

    def _recommend_summary(self, filters: dict) -> str:
        """Format recommendation summary."""
        parts = []
        if filters.get("use_case"):
            parts.append(f"✅ {filters['use_case'].replace('_', ' ').title()}")
        if filters.get("max_price"):
            parts.append(f"✅ Under {filters['max_price'] // 1000}K ETB")
        else:
            parts.append("✅ No budget limit")
        if filters.get("min_screen"):
            parts.append(f"✅ {filters['min_screen']}\"+ screen")
        return "\n".join(parts)
