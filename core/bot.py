"""Telegram bot interface for laptop scraper with pagination."""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from .config import Settings, get_settings, setup_logging
from .database import Database
from .recommender import LLMRecommender
from .schemas import (
    LaptopDB,
    RecommendationRequest,
    SearchFilters,
)

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

ITEMS_PER_PAGE = 10


# Conversation states
class ConvState(int, Enum):
    SEARCH_BRAND = 1
    SEARCH_PRICE = 2
    SEARCH_RAM = 3
    SEARCH_SCREEN = 4
    RECOMMEND_USE_CASE = 10
    RECOMMEND_BUDGET = 11
    RECOMMEND_SCREEN = 12


# Filter options
TOP_BRANDS = ["Dell", "HP", "Lenovo", "Asus", "Acer", "Apple"]
PRICE_OPTIONS = [50000, 80000, 120000, 150000]  # Max price options
RAM_OPTIONS = [8, 16, 32]
SCREEN_OPTIONS = [13, 14, 15, 17]  # Min screen size options
USE_CASES = [
    "Programming",
    "Gaming",
    "Office",
    "Student",
    "Video Editing",
    "General Use",
]


# -----------------------------------------------------------------------------
# Query Parser (LLM-based)
# -----------------------------------------------------------------------------

QUERY_PARSER_PROMPT = """Extract laptop search parameters from this query.

Return JSON with these fields (use null if not mentioned):
- brand: string or null (Dell, HP, Asus, Lenovo, Apple, etc.)
- max_price: number or null (in ETB - Ethiopian Birr)
- min_ram: number or null (in GB: 8, 16, 32)
- min_screen: number or null (in inches: 13, 14, 15, 17)
- use_case: string or null (programming, gaming, office, student, video_editing, general)

Examples:
- "Dell under 100k" → {{"brand": "Dell", "max_price": 100000}}
- "Gaming laptop 16GB RAM" → {{"use_case": "gaming", "min_ram": 16}}
- "15 inch laptop for programming" → {{"min_screen": 15, "use_case": "programming"}}

Query: {query}

JSON only:"""


@dataclass
class ParsedQuery:
    """Parsed search parameters from natural language."""

    brand: str | None = None
    max_price: float | None = None
    min_ram: int | None = None
    min_screen: float | None = None
    use_case: str | None = None
    raw_query: str = ""

    def to_search_filters(self) -> SearchFilters:
        """Convert to SearchFilters for database query."""
        return SearchFilters(
            brand=self.brand,
            max_price=self.max_price,
            min_ram=self.min_ram,
            min_screen=self.min_screen,
        )

    def to_recommendation_request(self) -> RecommendationRequest:
        """Convert to RecommendationRequest."""
        return RecommendationRequest(
            use_case=self.use_case,
            budget_max=self.max_price,
            min_ram=self.min_ram,
            min_screen=self.min_screen,
            brand_preference=self.brand,
        )

    def summary(self) -> str:
        """Human-readable summary of filters."""
        parts = []
        if self.brand:
            parts.append(f"Brand: {self.brand}")
        if self.max_price:
            parts.append(f"Under {self.max_price:,.0f} ETB")
        if self.min_ram:
            parts.append(f"{self.min_ram}GB+ RAM")
        if self.min_screen:
            parts.append(f'{self.min_screen}"+ screen')
        if self.use_case:
            parts.append(f"For {self.use_case}")

        return " • ".join(parts) if parts else "All laptops"


class QueryParser:
    """Parse natural language queries using LLM."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.client = httpx.Client(
            base_url="https://openrouter.ai/api/v1",
            headers={
                "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def parse(self, query: str) -> ParsedQuery:
        """Parse a natural language query into structured filters."""
        logger.info(f"Parsing query: {query}")

        try:
            response = self.client.post(
                "/chat/completions",
                json={
                    "model": self.settings.llm_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": QUERY_PARSER_PROMPT.format(query=query),
                        }
                    ],
                    "temperature": 0.1,
                    "max_tokens": 300,
                },
            )
            response.raise_for_status()

            content = response.json()["choices"][0]["message"]["content"]
            parsed_data = self._parse_json(content)

            if parsed_data:
                result = ParsedQuery(
                    brand=parsed_data.get("brand"),
                    max_price=parsed_data.get("max_price"),
                    min_ram=parsed_data.get("min_ram"),
                    min_screen=parsed_data.get("min_screen"),
                    use_case=parsed_data.get("use_case"),
                    raw_query=query,
                )
                logger.info(f"Parsed: {result.summary()}")
                return result

        except Exception as e:
            logger.error(f"Query parsing failed: {e}")

        return ParsedQuery(raw_query=query)

    def _parse_json(self, content: str) -> dict | None:
        """Parse JSON from LLM response."""
        content = content.strip()

        # Remove markdown code blocks
        if content.startswith("```"):
            lines = content.split("\n")
            lines = [line for line in lines if not line.startswith("```")]
            content = "\n".join(lines)

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(content[start:end])
                except json.JSONDecodeError:
                    return None
            return None

    def close(self):
        self.client.close()


# -----------------------------------------------------------------------------
# Pagination
# -----------------------------------------------------------------------------


@dataclass
class PaginationState:
    """Track pagination state for a user."""

    command: str  # "browse" or "search"
    page: int = 1
    total_items: int = 0
    filters: dict = field(default_factory=dict)

    @property
    def total_pages(self) -> int:
        return max(1, (self.total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    @property
    def offset(self) -> int:
        return (self.page - 1) * ITEMS_PER_PAGE

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1


# -----------------------------------------------------------------------------
# Formatting Helpers
# -----------------------------------------------------------------------------


def format_laptop_short(laptop: LaptopDB, index: int) -> str:
    """Format laptop for list view."""
    price_str = f"{laptop.price_etb:,.0f} ETB" if laptop.price_etb else "Call"

    specs = []
    if laptop.ram_gb:
        specs.append(f"{laptop.ram_gb}GB")
    if laptop.storage_gb:
        specs.append(f"{laptop.storage_gb}GB")
    if laptop.screen_size:
        specs.append(f'{laptop.screen_size}"')
    specs_str = " • ".join(specs)

    model = (laptop.model or "")[:20]
    # TODO: make brand clickable to source
    line = f"{index}. **{laptop.brand}** {model}\n"
    line += f"   💰 {price_str}"
    if specs_str:
        line += f" | {specs_str}"

    return line


def build_pagination_keyboard(
    state: PaginationState, prefix: str
) -> InlineKeyboardMarkup:
    """Build pagination keyboard."""
    buttons = []

    # Previous
    if state.has_prev:
        buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"{prefix}:prev"))
    else:
        buttons.append(InlineKeyboardButton("◀️", callback_data="noop"))

    # Page indicator
    buttons.append(
        InlineKeyboardButton(f"{state.page}/{state.total_pages}", callback_data="noop")
    )

    # Next
    if state.has_next:
        buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"{prefix}:next"))
    else:
        buttons.append(InlineKeyboardButton("▶️", callback_data="noop"))

    return InlineKeyboardMarkup([buttons])


# -----------------------------------------------------------------------------
# Bot Class
# -----------------------------------------------------------------------------


class LaptopBot:
    """Telegram bot for laptop search and recommendations."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.db = Database()
        self.recommender = LLMRecommender(self.db)
        self.query_parser = QueryParser(self.settings)
        logger.info("LaptopBot initialized")

    # -------------------------------------------------------------------------
    # Basic Commands
    # -------------------------------------------------------------------------

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        welcome = """
🔍 **Addis Laptop Bot**

Find the best laptop deals from Ethiopian Telegram channels!

**Commands:**
/browse - Browse latest laptops
/search - Search with filters
/recommend - Get AI recommendations
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

    # -------------------------------------------------------------------------
    # Browse Command
    # -------------------------------------------------------------------------

    async def browse(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /browse - show latest laptops with pagination."""
        logger.info(f"User {update.effective_user.id} browsing")

        total = self.db.count_laptops()
        if total == 0:
            await update.message.reply_text("📭 No laptops yet. Check back later!")
            return

        state = PaginationState(command="browse", page=1, total_items=total)
        context.user_data["pagination"] = state

        laptops = self.db.get_all(limit=ITEMS_PER_PAGE, offset=0)
        message = self._format_browse_message(laptops, state)
        keyboard = build_pagination_keyboard(state, "browse")

        await update.message.reply_text(
            message, parse_mode="Markdown", reply_markup=keyboard
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

        laptops = self.db.get_all(limit=ITEMS_PER_PAGE, offset=state.offset)
        message = self._format_browse_message(laptops, state)
        keyboard = build_pagination_keyboard(state, "browse")

        await query.edit_message_text(
            message, parse_mode="Markdown", reply_markup=keyboard
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

    # -------------------------------------------------------------------------
    # Search Command (Guided)
    # -------------------------------------------------------------------------

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
            "🔍 **Search Laptops**\n\nSelect brand:",
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
                InlineKeyboardButton(f"Under {p//1000}K", callback_data=f"sprice:{p}")
                for p in PRICE_OPTIONS[:2]
            ],
            [
                InlineKeyboardButton(f"Under {p//1000}K", callback_data=f"sprice:{p}")
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

        # Filter by screen size in memory (simpler than adding to DB query)
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
            message, parse_mode="Markdown", reply_markup=keyboard
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
            message, parse_mode="Markdown", reply_markup=keyboard
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

        return "\n".join(lines)

    def _filter_summary(self, filters: dict) -> str:
        """Format filter summary."""
        parts = []
        if filters.get("brand"):
            parts.append(f"✅ {filters['brand']}")
        if filters.get("max_price"):
            parts.append(f"✅ Under {filters['max_price']//1000}K")
        if filters.get("min_ram"):
            parts.append(f"✅ {filters['min_ram']}GB+ RAM")
        if filters.get("min_screen"):
            parts.append(f"✅ {filters['min_screen']}\"+ screen")
        return " ".join(parts)

    async def search_cancel(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Cancel search."""
        await update.message.reply_text("Cancelled. Use /search to start again.")
        return ConversationHandler.END

    # -------------------------------------------------------------------------
    # Recommend Command
    # -------------------------------------------------------------------------

    async def recommend_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Start recommendation flow."""
        logger.info(f"User {update.effective_user.id} starting recommend")
        context.user_data["recommend_filters"] = {}

        keyboard = [
            [
                InlineKeyboardButton(
                    "💻 Programming", callback_data=f"ruse:programming"
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
            "🎯 **Get AI Recommendations**\n\nWhat will you mainly use the laptop for?",
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
            context.user_data["recommend_filters"]["use_case"] = use_case

        buttons = [
            [
                InlineKeyboardButton(f"Under {p//1000}K", callback_data=f"rbudget:{p}")
                for p in PRICE_OPTIONS[:2]
            ],
            [
                InlineKeyboardButton(f"Under {p//1000}K", callback_data=f"rbudget:{p}")
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
            f"🎯 **Get AI Recommendations**\n\n{summary}\n\n🤖 Analyzing...",
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

        message = f"🎯 **{response.query_summary}**\n\n"

        if response.market_insight:
            message += f"💡 _{response.market_insight}_\n\n"

        for rec in response.recommendations:
            laptop = rec.laptop
            price_str = f"{laptop.price_etb:,.0f} ETB" if laptop.price_etb else "Call"

            message += f"**#{rec.rank} {laptop.brand} {laptop.model or ''}**\n"
            message += f"💰 {price_str}\n"

            specs = []
            if laptop.ram_gb:
                specs.append(f"{laptop.ram_gb}GB RAM")
            if laptop.storage_gb:
                specs.append(f"{laptop.storage_gb}GB")
            if laptop.screen_size:
                specs.append(f'{laptop.screen_size}"')
            if specs:
                message += f"⚙️ {' • '.join(specs)}\n"

            # message += f"\n✅ **Pros:** {', '.join(rec.pros)}\n"
            # message += f"⚠️ **Cons:** {', '.join(rec.cons)}\n"

            # Pros & Cons
            message += "✅ **Pros:**\n"
            for pro in rec.pros[:3]:
                message += f"  • {pro}\n"
            # message += f"\n✅ **Pros:** {', '.join(rec.pros)}\n"
            # message += f"⚠️ **Cons:** {', '.join(rec.cons)}\n"
            message += "\n⚠️ **Cons:**\n"
            for con in rec.cons[:2]:
                message += f"  • {con}\n"

            # message += f"📝 _{rec.verdict}_\n"
            message += f"👤 {rec.best_for}\n"

            if laptop.contact:
                message += f"📞 `{laptop.contact}`\n"

            channel_name = laptop.channel.split("/")[-1]
            message += f"📢 @{channel_name}\n"
            message += "\n" + "─" * 25 + "\n\n"

        message += "Use /recommend for more options!"

        await query.edit_message_text(message, parse_mode="Markdown")

    def _recommend_summary(self, filters: dict) -> str:
        """Format recommendation summary."""
        parts = []
        if filters.get("use_case"):
            parts.append(f"✅ {filters['use_case'].replace('_', ' ').title()}")
        if filters.get("max_price"):
            parts.append(f"✅ Under {filters['max_price']//1000}K ETB")
        else:
            parts.append("✅ No budget limit")
        if filters.get("min_screen"):
            parts.append(f"✅ {filters['min_screen']}\"+ screen")
        return "\n".join(parts)

    async def recommend_cancel(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Cancel recommendation."""
        await update.message.reply_text("Cancelled. Use /recommend to start again.")
        return ConversationHandler.END

    # -------------------------------------------------------------------------
    # Natural Language Handler
    # -------------------------------------------------------------------------

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle free-form natural language queries."""
        text = update.message.text
        logger.info(f"User {update.effective_user.id}: {text}")

        await update.message.reply_text("🔍 Understanding your request...")

        parsed = self.query_parser.parse(text)

        # Decide: recommendation or search
        is_recommend = parsed.use_case is not None or any(
            w in text.lower() for w in ["recommend", "suggest", "best", "good for"]
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
                l
                for l in laptops
                if l.screen_size and l.screen_size >= parsed.min_screen
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

        keyboard = build_pagination_keyboard(state, "search")

        await update.message.reply_text(
            "\n".join(lines), parse_mode="Markdown", reply_markup=keyboard
        )

    async def _nl_recommend(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: ParsedQuery
    ):
        """Handle natural language recommendation."""
        request = parsed.to_recommendation_request()

        await update.message.reply_text("🤖 Finding best options...")

        response = self.recommender.recommend(request, limit=3)

        if not response.recommendations:
            await update.message.reply_text(
                f"😔 No results for: _{parsed.summary()}_\n\nTry /recommend",
                parse_mode="Markdown",
            )
            return

        message = f"🎯 **{response.query_summary}**\n\n"

        if response.market_insight:
            message += f"💡 _{response.market_insight}_\n\n"

        for rec in response.recommendations:
            laptop = rec.laptop
            price_str = f"{laptop.price_etb:,.0f} ETB" if laptop.price_etb else "Call"

            message += f"**#{rec.rank} {laptop.brand} {laptop.model or ''}**\n"
            message += f"💰 {price_str}\n"

            specs = []
            if laptop.ram_gb:
                specs.append(f"{laptop.ram_gb}GB RAM")
            if laptop.storage_gb:
                specs.append(f"{laptop.storage_gb}GB")
            if laptop.screen_size:
                specs.append(f'{laptop.screen_size}"')
            if specs:
                message += f"⚙️ {' • '.join(specs)}\n"

            message += f"\n✅ **Pros:** {', '.join(rec.pros)}\n"
            message += f"⚠️ **Cons:** {', '.join(rec.cons)}\n"
            message += f"📝 _{rec.verdict}_\n"
            message += f"👤 {rec.best_for}\n"

            if laptop.contact:
                message += f"📞 `{laptop.contact}`\n"

            channel_name = laptop.channel.split("/")[-1]
            message += f"📢 @{channel_name}\n"
            message += "\n" + "─" * 25 + "\n\n"

        message += "Use /recommend for more!"

        await update.message.reply_text(message, parse_mode="Markdown")

    # -------------------------------------------------------------------------
    # Noop Handler
    # -------------------------------------------------------------------------

    async def handle_noop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle disabled button clicks."""
        await update.callback_query.answer()

    # -------------------------------------------------------------------------
    # Run
    # -------------------------------------------------------------------------

    def run(self):
        """Run the bot."""
        if not self.settings.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set")

        app = Application.builder().token(self.settings.telegram_bot_token).build()

        # Search conversation
        search_conv = ConversationHandler(
            entry_points=[CommandHandler("search", self.search_start)],
            states={
                ConvState.SEARCH_BRAND: [
                    CallbackQueryHandler(self.search_brand, pattern="^sbrand:")
                ],
                ConvState.SEARCH_PRICE: [
                    CallbackQueryHandler(self.search_price, pattern="^sprice:")
                ],
                ConvState.SEARCH_RAM: [
                    CallbackQueryHandler(self.search_ram, pattern="^sram:")
                ],
                ConvState.SEARCH_SCREEN: [
                    CallbackQueryHandler(self.search_screen, pattern="^sscreen:")
                ],
            },
            fallbacks=[CommandHandler("cancel", self.search_cancel)],
            per_message=False,
        )

        # Recommend conversation
        recommend_conv = ConversationHandler(
            entry_points=[CommandHandler("recommend", self.recommend_start)],
            states={
                ConvState.RECOMMEND_USE_CASE: [
                    CallbackQueryHandler(self.recommend_use_case, pattern="^ruse:")
                ],
                ConvState.RECOMMEND_BUDGET: [
                    CallbackQueryHandler(self.recommend_budget, pattern="^rbudget:")
                ],
                ConvState.RECOMMEND_SCREEN: [
                    CallbackQueryHandler(self.recommend_screen, pattern="^rscreen:")
                ],
            },
            fallbacks=[CommandHandler("cancel", self.recommend_cancel)],
            per_message=False,
        )

        # Register handlers
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("browse", self.browse))
        app.add_handler(search_conv)
        app.add_handler(recommend_conv)

        # Pagination
        app.add_handler(
            CallbackQueryHandler(self.browse_pagination, pattern="^browse:")
        )
        app.add_handler(
            CallbackQueryHandler(self.search_pagination, pattern="^search:")
        )

        # Noop
        app.add_handler(CallbackQueryHandler(self.handle_noop, pattern="^noop$"))

        # Natural language (last)
        app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

        logger.info("Starting bot...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

    def close(self):
        """Cleanup."""
        self.query_parser.close()
        self.recommender.close()


def run_bot():
    """Entry point for running the bot."""
    setup_logging()
    bot = LaptopBot()
    bot.run()


if __name__ == "__main__":
    run_bot()
