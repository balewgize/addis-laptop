"""Basic command handlers: /start, /help, /browse."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from core.database import Database
from core.schemas import LaptopDB
from bot.constants import ITEMS_PER_PAGE
from bot.utils import format_laptop_short, build_pagination_keyboard, PaginationState

logger = logging.getLogger(__name__)


class CommandHandlers:
    """Handlers for basic bot commands."""

    def __init__(self, db: Database):
        self.db = db

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        welcome = """
🔍 **Addis Laptop**

Find the best laptop deals from Ethiopian Telegram channels!

**Commands:**
/browse - Browse latest laptops
/search - Search with filters
/recommend - Get AI recommendations
/cancel - Cancel current operation
/help - Show this message

**Quick Search:**
Just type what you're looking for!

Examples:
• "Dell laptop under 100k"
• "Gaming laptop 16GB RAM"
• "Cheap laptop for student"
        """
        await update.message.reply_text(welcome, parse_mode="Markdown")
        logger.info(f"User {update.effective_user.id} started bot")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        await self.start(update, context)

    async def browse(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /browse - show latest laptops with pagination."""
        logger.info(f"User {update.effective_user.id} browsing")

        total = self.db.count_laptops()
        if total == 0:
            await update.message.reply_text("📭 No laptops yet. Check back later!")
            return

        state = PaginationState(command="browse", page=1, total_items=total)
        context.user_data["pagination"] = state

        laptops = self.db.get_laptops(limit=ITEMS_PER_PAGE, offset=0)
        message = self._format_browse_message(laptops, state)
        keyboard = build_pagination_keyboard(state, "browse")

        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

    async def browse_pagination(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle browse pagination."""
        query = update.callback_query
        await query.answer()

        action = query.data.split(":")[1]
        state: PaginationState = context.user_data.get("pagination")

        if not state or state.command != "browse":
            await query.edit_message_text("Session expired. Use /browse again.")
            return

        if action == "next" and state.has_next:
            state.page += 1
        elif action == "prev" and state.has_prev:
            state.page -= 1
        else:
            return

        laptops = self.db.get_laptops(limit=ITEMS_PER_PAGE, offset=state.offset)
        message = self._format_browse_message(laptops, state)
        keyboard = build_pagination_keyboard(state, "browse")

        await query.edit_message_text(
            message,
            parse_mode="Markdown",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

    def _format_browse_message(
        self, laptops: list[LaptopDB], state: PaginationState
    ) -> str:
        """Format browse results."""
        start = state.offset + 1
        end = min(state.offset + ITEMS_PER_PAGE, state.total_items)

        lines = [f"📱 **Latest Laptops** ({start}-{end} of {state.total_items})", ""]
        for i, laptop in enumerate(laptops, start=start):
            lines.append(format_laptop_short(laptop, i))
        lines.append("\nUse /search to filter results")

        return "\n".join(lines)

    async def handle_noop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle disabled button clicks."""
        await update.callback_query.answer()
