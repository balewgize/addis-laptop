"""Entry point for the Telegram bot."""

from core.config import setup_logging
from core.bot import LaptopBot

logger = setup_logging()

if __name__ == "__main__":
    bot = LaptopBot()
    bot.run()
