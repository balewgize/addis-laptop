"""Entry point for the Telegram bot."""

import os
from core.config import setup_logging
from core.bot import LaptopBot

logger = setup_logging()

if __name__ == "__main__":
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")

    bot = LaptopBot()
    bot.run(token)
