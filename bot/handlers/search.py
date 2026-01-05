"""Search conversation handlers."""

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from core.database import Database
from core.schemas import LaptopDB, SearchFilters
from bot.constants import (
    ConvState,
    TOP_BRANDS,
    PRICE_OPTIONS,
    RAM_OPTIONS,
    SCREEN_OPTIONS,
    ITEMS_PER_PAGE,
)
from bot.utils import format_laptop_short, build_pagination_keyboard, PaginationState

logger = logging.getLogger(__name__)


class SearchHandlers:
    """Handlers for search conversation flow."""

    def __init__(self, db: Database):
        self.db = db

    async def search_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Start guided search."""
        logger.info(f"User {update.effective_user.id} starting search")
        context.user_data["search_filters"] = {}

        keyboard = [
            [
                InlineKeyboardButton(brand, callback_data=f"sbrand:{brand}")
                for brand in TOP_BRANDS[:3]
            ],
            [
                InlineKeyboardButton(brand, callback_data=f"sbrand:{brand}")
                for brand in TOP_BRANDS[3:]
            ],
            [InlineKeyboardButton("Any Brand ↩️", callback_data="sbrand:any")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "🔍 **Search Laptops**\n\nSelect brand:\n\n_Type /cancel to exit_",
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )
        return ConvState.SEARCH_BRAND

    async def search_brand(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle brand selection."""
        query = update.callback_query
        await query.answer()

        brand = query.data.split(":")[1]
        if brand != "any":
            context.user_data["search_filters"]["brand"] = brand
            logger.info(f"User {query.from_user.id} selected brand: {brand}")

        keyboard = [
            [
                InlineKeyboardButton(f"Under {p // 1000}K", callback_data=f"sprice:{p}")
                for p in PRICE_OPTIONS[:2]
            ],
            [
                InlineKeyboardButton(f"Under {p // 1000}K", callback_data=f"sprice:{p}")
                for p in PRICE_OPTIONS[2:]
            ],
            [InlineKeyboardButton("Any Price ↩️", callback_data="sprice:any")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        brand_display = brand if brand != "any" else "Any"
        await query.edit_message_text(
            f"🔍 **Search Laptops**\n\n✅ Brand: {brand_display}\n\nWhat's your budget in ETB?",
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )
        return ConvState.SEARCH_PRICE

    async def search_price(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle price selection."""
        query = update.callback_query
        await query.answer()

        price = query.data.split(":")[1]
        if price != "any":
            context.user_data["search_filters"]["max_price"] = int(price)

        buttons = [
            [
                InlineKeyboardButton(f"{r}GB+", callback_data=f"sram:{r}")
                for r in RAM_OPTIONS
            ],
            [InlineKeyboardButton("Any RAM ↩️", callback_data="sram:any")],
        ]

        filters = context.user_data["search_filters"]
        summary = self._filter_summary(filters)

        await query.edit_message_text(
            f"🔍 **Search Laptops**\n\n{summary}\n\nMin RAM:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return ConvState.SEARCH_RAM

    async def search_ram(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle RAM selection."""
        query = update.callback_query
        await query.answer()

        ram = query.data.split(":")[1]
        if ram != "any":
            context.user_data["search_filters"]["min_ram"] = int(ram)

        buttons = [
            [
                InlineKeyboardButton(f'{s}"+ ', callback_data=f"sscreen:{s}")
                for s in SCREEN_OPTIONS[:2]
            ],
            [
                InlineKeyboardButton(f'{s}"+ ', callback_data=f"sscreen:{s}")
                for s in SCREEN_OPTIONS[2:]
            ],
            [InlineKeyboardButton("Any Size ↩️", callback_data="sscreen:any")],
        ]

        filters = context.user_data["search_filters"]
        summary = self._filter_summary(filters)

        await query.edit_message_text(
            f"🔍 **Search Laptops**\n\n{summary}\n\nMin screen size:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return ConvState.SEARCH_SCREEN

    async def search_screen(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle screen selection and execute search."""
        query = update.callback_query
        await query.answer()

        screen = query.data.split(":")[1]
        if screen != "any":
            context.user_data["search_filters"]["min_screen"] = float(screen)

        await query.edit_message_text("🔍 Searching...")
        await self._execute_search(query, context)

        return ConversationHandler.END

    async def _execute_search(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Execute search with filters."""
        filters_dict = context.user_data.get("search_filters", {})

        filters = SearchFilters(
            brand=filters_dict.get("brand"),
            max_price=filters_dict.get("max_price"),
            min_ram=filters_dict.get("min_ram"),
        )

        laptops = self.db.search_laptops(filters)

        # Filter by screen size in memory
        min_screen = filters_dict.get("min_screen")
        if min_screen:
            laptops = [
                l for l in laptops if l.screen_size and l.screen_size >= min_screen
            ]

        total = len(laptops)

        if total == 0:
            await query.edit_message_text(
                "😔 No laptops found.\n\nTry /search with different filters."
            )
            return

        state = PaginationState(
            command="search", page=1, total_items=total, filters=filters_dict
        )
        context.user_data["pagination"] = state
        context.user_data["search_results"] = laptops

        page_laptops = laptops[:ITEMS_PER_PAGE]
        message = self._format_search_message(page_laptops, state, filters_dict)
        keyboard = build_pagination_keyboard(state, "search")

        await query.edit_message_text(
            message,
            parse_mode="Markdown",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

    async def search_pagination(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle search pagination."""
        query = update.callback_query
        await query.answer()

        action = query.data.split(":")[1]
        state: PaginationState = context.user_data.get("pagination")
        results: list[LaptopDB] = context.user_data.get("search_results", [])

        if not state or state.command != "search":
            await query.edit_message_text("Session expired. Use /search again.")
            return

        if action == "next" and state.has_next:
            state.page += 1
        elif action == "prev" and state.has_prev:
            state.page -= 1
        else:
            return

        start = state.offset
        page_laptops = results[start : start + ITEMS_PER_PAGE]

        message = self._format_search_message(page_laptops, state, state.filters)
        keyboard = build_pagination_keyboard(state, "search")

        await query.edit_message_text(
            message,
            parse_mode="Markdown",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

    def _format_search_message(
        self, laptops: list[LaptopDB], state: PaginationState, filters: dict
    ) -> str:
        """Format search results."""
        start = state.offset + 1
        end = min(state.offset + ITEMS_PER_PAGE, state.total_items)
        summary = self._filter_summary(filters)

        lines = [
            f"🔍 **Results** ({start}-{end} of {state.total_items})",
            f"_{summary}_" if summary else "",
            "",
        ]
        for i, laptop in enumerate(laptops, start=start):
            lines.append(format_laptop_short(laptop, i))
        lines.append("\nUse /search to search again.")

        return "\n".join(lines)

    def _filter_summary(self, filters: dict) -> str:
        """Format filter summary."""
        parts = []
        if filters.get("brand"):
            parts.append(f"✅ {filters['brand']}")
        if filters.get("max_price"):
            parts.append(f"✅ Under {filters['max_price'] // 1000}K")
        if filters.get("min_ram"):
            parts.append(f"✅ {filters['min_ram']}GB+ RAM")
        if filters.get("min_screen"):
            parts.append(f"✅ {filters['min_screen']}\"+ screen")
        return " ".join(parts)
