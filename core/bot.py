"""Telegram bot interface for laptop recommendations."""

import logging
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from .config import get_settings, setup_logging
from .database import Database
from .recommender import LLMRecommender
from .schemas import RecommendationRequest
from .utils import format_source_link, format_phone_link

logger = logging.getLogger(__name__)


class LaptopBot:
    """Telegram bot for laptop recommendations."""

    def __init__(self):
        self.settings = get_settings()
        self.db = Database()
        self.recommender = LLMRecommender(self.db)
        logger.info("LaptopBot initialized")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        stats = self.db.get_dashboard_stats()

        welcome = f"""
🔍 **Laptop Addis**

I help you find the best laptop deals from Ethiopian Telegram channels!

📊 Currently tracking **{stats.total_laptops}** laptops from **{stats.total_channels}** channels.

**Commands:**
/find - Get personalized recommendations
/browse - Browse latest laptops
/search - Search by brand
/help - Show this message

**Quick start:**
Just tell me what you're looking for!

Example: _"Programming laptop under 100,000 ETB"_
        """
        await update.message.reply_text(welcome, parse_mode="Markdown")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        await self.start(update, context)

    async def find(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /find command - start recommendation flow."""
        keyboard = [
            [
                InlineKeyboardButton("💻 Programming", callback_data="use_programming"),
                InlineKeyboardButton("🎮 Gaming", callback_data="use_gaming"),
            ],
            [
                InlineKeyboardButton("📊 Office/Work", callback_data="use_office"),
                InlineKeyboardButton("🎓 Student", callback_data="use_student"),
            ],
            [
                InlineKeyboardButton("🎬 Video Editing", callback_data="use_video"),
                InlineKeyboardButton("🤷 General Use", callback_data="use_general"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "What will you mainly use the laptop for?",
            reply_markup=reply_markup,
        )

    async def handle_use_case(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle use case selection."""
        query = update.callback_query
        await query.answer()

        use_case = query.data.replace("use_", "")
        context.user_data["use_case"] = use_case

        use_case_labels = {
            "programming": "💻 Programming",
            "gaming": "🎮 Gaming",
            "office": "📊 Office/Work",
            "student": "🎓 Student",
            "video": "🎬 Video Editing",
            "general": "🤷 General Use",
        }

        keyboard = [
            [
                InlineKeyboardButton("Under 50K", callback_data="budget_50000"),
                InlineKeyboardButton("50K - 80K", callback_data="budget_80000"),
            ],
            [
                InlineKeyboardButton("80K - 120K", callback_data="budget_120000"),
                InlineKeyboardButton("120K - 150K", callback_data="budget_150000"),
            ],
            [
                InlineKeyboardButton("150K+", callback_data="budget_300000"),
                InlineKeyboardButton("💰 No limit", callback_data="budget_0"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"✅ {use_case_labels.get(use_case, use_case.title())}\n\n"
            "What's your budget in ETB?",
            reply_markup=reply_markup,
        )

    async def handle_budget(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle budget selection and generate recommendations."""
        query = update.callback_query
        await query.answer()

        budget = int(query.data.replace("budget_", ""))
        use_case = context.user_data.get("use_case", "general")

        budget_label = f"{budget:,} ETB" if budget > 0 else "No limit"

        # TODO: show rotating progress text until results are ready
        await query.edit_message_text(
            f"🔍 Finding the best laptops...\n\n"
            f"Use case: {use_case.title()}\n"
            f"Budget: {budget_label}"
        )

        request = RecommendationRequest(
            budget_max=budget if budget > 0 else None,
            use_case=use_case,
        )

        try:
            response = self.recommender.recommend(request)
        except Exception as e:
            logger.error(f"Recommendation failed: {e}")
            await query.edit_message_text(
                "❌ Sorry, something went wrong. Please try again later.\n\n"
                "Use /find to start over."
            )
            return

        if not response.recommendations:
            await query.edit_message_text(
                "😔 No laptops found matching your criteria.\n\n"
                "Try:\n"
                "• Increasing your budget\n"
                "• Choosing a different use case\n\n"
                "Use /find to search again."
            )
            return

        message = await self._format_recommendations(response)
        await query.edit_message_text(
            message, parse_mode="Markdown", disable_web_page_preview=True
        )

    async def _format_recommendations(self, response) -> str:
        """Format recommendation response for Telegram."""
        message = f"📋 **{response.query_summary}**\n\n"

        if response.market_insight:
            message += f"💡 _{response.market_insight}_\n\n"

        message += "━━━━━━━━━━━━━━━━━━━━\n\n"

        for rec in response.recommendations:
            laptop = rec.laptop
            price_str = (
                f"{laptop.price_etb:,.0f} ETB"
                if laptop.price_etb
                else "📞 Call for price"
            )

            # Header
            message += f"**#{rec.rank} {laptop.brand} {laptop.model or ''}**\n"
            message += f"💰 {price_str}\n\n"

            # Specs
            specs = []
            if laptop.cpu:
                specs.append(f"🔲 {laptop.cpu}")
            if laptop.ram_gb:
                specs.append(f"🧠 {laptop.ram_gb}GB RAM")
            if laptop.storage_gb:
                storage = f"💾 {laptop.storage_gb}GB"
                if laptop.storage_type:
                    storage += f" {laptop.storage_type}"
                specs.append(storage)
            if laptop.screen_size:
                specs.append(f'🖥 {laptop.screen_size}"')
            if laptop.gpu:
                specs.append(f"🎮 {laptop.gpu}")
            if laptop.battery_life: 
                specs.append(f"🔋 {laptop.battery_life}")

            if specs:
                message += "\n".join(specs) + "\n\n"

            # Pros & Cons
            message += "✅ **Pros:**\n"
            for pro in rec.pros[:3]:
                message += f"  • {pro}\n"

            message += "\n⚠️ **Cons:**\n"
            for con in rec.cons[:2]:
                message += f"  • {con}\n"

            # Verdict
            message += f"\n🎯 _{rec.verdict}_\n"
            message += f"👤 **{rec.best_for}**\n"

            # Contact (clickable phone - works on mobile)
            if laptop.contact:
                display, tel_link = format_phone_link(laptop.contact)
                message += f"\n📞 Contact: [{display}]({tel_link})\n"

            # Source link (clickable)
            channel_name, source_link = format_source_link(
                laptop.channel, laptop.message_id
            )
            message += f"\nSource: [@{channel_name}]({source_link})\n"

            message += "\n━━━━━━━━━━━━━━━━━━━━\n\n"

        message += "Use /find to search again!"

        return message

    async def browse(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /browse command - show latest laptops."""
        laptops = self.db.get_laptops(limit=10)

        if not laptops:
            await update.message.reply_text(
                "📭 No laptops in database yet.\n" "Check back later!"
            )
            return

        message = "💻 **Latest Laptops:**\n\n"

        for i, laptop in enumerate(laptops, 1):
            price_str = f"{laptop.price_etb:,.0f} ETB" if laptop.price_etb else "Call"
            specs = []
            if laptop.ram_gb:
                specs.append(f"{laptop.ram_gb}GB RAM")
            if laptop.storage_gb:
                specs.append(f"{laptop.storage_gb}GB")

            specs_str = " | ".join(specs) if specs else ""

            message += f"{i}. **{laptop.brand} {laptop.model or ''}**\n"
            message += f"   💰 {price_str}"
            if specs_str:
                message += f" • {specs_str}"

            channel_name = laptop.channel.rstrip("/").split("/")[-1]
            source_link = f"https://t.me/{channel_name}/{laptop.message_id}"
            message += f"\n    [View]({source_link})"

            if laptop.contact:
                display, tel_link = format_phone_link(laptop.contact)
                message += f" • 📞 `{display}`"
                # message += f" • 📞 [{display}]({tel_link})"
            message += "\n\n"

        message += "_Use /find for personalized recommendations!_"

        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            disable_web_page_preview=True,  # Prevents link previews cluttering the message
        )

    async def search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command."""
        if context.args:
            brand = " ".join(context.args)
            await self._search_by_brand(update, brand)
        else:
            keyboard = [
                [
                    InlineKeyboardButton("Dell", callback_data="search_Dell"),
                    InlineKeyboardButton("HP", callback_data="search_HP"),
                    InlineKeyboardButton("Lenovo", callback_data="search_Lenovo"),
                ],
                [
                    InlineKeyboardButton("Asus", callback_data="search_Asus"),
                    InlineKeyboardButton("Acer", callback_data="search_Acer"),
                    InlineKeyboardButton("Apple", callback_data="search_Apple"),
                ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "🔍 Search by brand:\n\n" "Select a brand or type `/search <brand>`",
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )

    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle search brand selection."""
        query = update.callback_query
        await query.answer()

        brand = query.data.replace("search_", "")
        await query.edit_message_text(f"🔍 Searching for {brand}...")

        await self._search_by_brand_callback(query, brand)

    async def _search_by_brand(self, update: Update, brand: str):
        """Search laptops by brand."""
        from .schemas import SearchFilters

        filters = SearchFilters(brand=brand, posted_within_days=90)
        laptops = self.db.search_laptops(filters)

        if not laptops:
            await update.message.reply_text(
                f"😔 No {brand} laptops found.\n\n" "Try /browse to see all laptops."
            )
            return

        message = f"🔍 **{brand} Laptops** ({len(laptops)} found):\n\n"

        for i, laptop in enumerate(laptops[:10], 1):
            price_str = f"{laptop.price_etb:,.0f} ETB" if laptop.price_etb else "Call"
            message += f"{i}. **{laptop.brand} {laptop.model or ''}**\n"
            message += f"   💰 {price_str}"

            if laptop.ram_gb:
                message += f" • {laptop.ram_gb}GB RAM"

            channel_name = laptop.channel.rstrip("/").split("/")[-1]
            source_link = f"https://t.me/{channel_name}/{laptop.message_id}"
            message += f"\n    [View]({source_link})"

            if laptop.contact:
                display, tel_link = format_phone_link(laptop.contact)
                message += f" • 📞 [{display}]({tel_link})"
            message += "\n\n"

        if len(laptops) > 10:
            message += f"_...and {len(laptops) - 10} more_\n\n"

        message += "_Use /find for personalized recommendations!_"

        await update.message.reply_text(
            message, parse_mode="Markdown", disable_web_page_preview=True
        )

    async def _search_by_brand_callback(self, query, brand: str):
        """Search laptops by brand (callback version)."""
        from .schemas import SearchFilters

        filters = SearchFilters(brand=brand, posted_within_days=90)
        laptops = self.db.search_laptops(filters)

        if not laptops:
            await query.edit_message_text(
                f"😔 No {brand} laptops found.\n\n" "Try /browse to see all laptops."
            )
            return

        message = f"🔍 **{brand} Laptops** ({len(laptops)} found):\n\n"

        for i, laptop in enumerate(laptops[:10], 1):
            price_str = f"{laptop.price_etb:,.0f} ETB" if laptop.price_etb else "Call"
            message += f"{i}. **{laptop.brand} {laptop.model or ''}**\n"
            message += f"   💰 {price_str}"

            if laptop.ram_gb:
                message += f" • {laptop.ram_gb}GB RAM"

            channel_name = laptop.channel.rstrip("/").split("/")[-1]
            source_link = f"https://t.me/{channel_name}/{laptop.message_id}"
            message += f"\n    [View]({source_link})"
            if laptop.contact:
                display, tel_link = format_phone_link(laptop.contact)
                message += f" • 📞 [{display}]({tel_link})"

            message += "\n\n"

        if len(laptops) > 10:
            message += f"_...and {len(laptops) - 10} more_\n\n"

        message += "_Use /find for personalized recommendations!_"

        await query.edit_message_text(
            message, parse_mode="Markdown", disable_web_page_preview=True
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle free-form messages with natural language."""
        text = update.message.text.lower()

        # Extract budget
        budget = None
        budget_match = re.search(r"(\d{2,3})[,.]?(\d{3})?", text.replace(" ", ""))
        if budget_match:
            budget_str = budget_match.group(0).replace(",", "").replace(".", "")
            budget = int(budget_str)
            if budget < 1000:
                budget *= 1000

        # Extract use case
        use_case = None
        use_case_keywords = {
            "programming": ["programming", "coding", "developer", "software", "code"],
            "gaming": ["gaming", "game", "play", "gamer"],
            "office": ["office", "work", "business", "excel", "word"],
            "student": ["student", "school", "study", "university", "college"],
            "video": ["video", "editing", "premiere", "davinci", "youtube"],
        }

        for case, keywords in use_case_keywords.items():
            if any(kw in text for kw in keywords):
                use_case = case
                break

        # Extract brand
        brand = None
        brands = [
            "dell",
            "hp",
            "lenovo",
            "asus",
            "acer",
            "apple",
            "macbook",
            "thinkpad",
        ]
        for b in brands:
            if b in text:
                brand = b.title()
                break

        if not budget and not use_case and not brand:
            await update.message.reply_text(
                "I can help you find laptops! Try:\n\n"
                '• "Programming laptop under 100,000"\n'
                '• "Gaming laptop around 150k"\n'
                '• "Dell laptops"\n\n'
                "Or use /find for guided search."
            )
            return

        await update.message.reply_text("🔍 Searching...")

        request = RecommendationRequest(
            budget_max=budget,
            use_case=use_case,
            brand_preference=brand,
        )

        try:
            response = self.recommender.recommend(request)
        except Exception as e:
            logger.error(f"Recommendation failed: {e}")
            await update.message.reply_text(
                "❌ Something went wrong. Please try /find instead."
            )
            return

        if not response.recommendations:
            await update.message.reply_text(
                "😔 No laptops found matching your criteria.\n\n"
                "Try adjusting your requirements or use /find."
            )
            return

        message = await self._format_recommendations(response)
        await update.message.reply_text(
            message, parse_mode="Markdown", disable_web_page_preview=True
        )

    def run(self):
        """Run the bot."""
        if not self.settings.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set")

        app = Application.builder().token(self.settings.telegram_bot_token).build()

        # Command handlers
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("find", self.find))
        app.add_handler(CommandHandler("browse", self.browse))
        app.add_handler(CommandHandler("search", self.search))

        # Callback handlers
        app.add_handler(CallbackQueryHandler(self.handle_use_case, pattern="^use_"))
        app.add_handler(CallbackQueryHandler(self.handle_budget, pattern="^budget_"))
        app.add_handler(CallbackQueryHandler(self.handle_search, pattern="^search_"))

        # Message handler
        app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

        logger.info("Starting bot...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


def run_bot():
    """Entry point for running the bot."""
    setup_logging()
    bot = LaptopBot()
    bot.run()


if __name__ == "__main__":
    run_bot()
