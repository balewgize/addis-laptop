"""Application configuration via environment variables."""

import logging
import sys
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram Scraper
    telegram_api_id: int
    telegram_api_hash: str

    telegram_bot_token: str = ""

    openrouter_api_key: str
    llm_model: str = "anthropic/claude-haiku-4.5"

    database_path: str = "data/laptops.db"

    admin_username: str = "admin"
    admin_password: str = "admin"  # Change in production!

    log_level: str = "INFO"

    # Sync settings
    default_sync_days: int = 90  # How far back to scrape
    max_messages_per_sync: int = 500

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def setup_logging(level: str | None = None) -> logging.Logger:
    """Configure logging for the application (console + file)."""
    from pathlib import Path
    from logging.handlers import RotatingFileHandler

    log_level = level or get_settings().log_level

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # File handler (rotating: 5MB max, keep 5 backups)
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    file_handler = RotatingFileHandler(
        filename=log_dir / "app.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    # Configure logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    logger.handlers = []
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    # Reduce noise from libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)

    logger.info(
        f"Logging configured at {log_level} level (file: {log_dir / 'app.log'})"
    )
    return logger
