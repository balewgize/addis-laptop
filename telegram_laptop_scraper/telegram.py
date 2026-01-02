"""Telegram client for fetching messages from channels."""

import logging
from datetime import datetime

from telethon import TelegramClient as TelethonClient
from telethon.tl.types import Message

from .config import Settings, get_settings
from .schemas import Laptop, LaptopCreate

logger = logging.getLogger(__name__)


class TelegramFetcher:
    """Fetches messages from Telegram channels."""

    def __init__(
        self,
        settings: Settings | None = None,
        session_name: str = "laptop_scraper_session",
    ):
        self.settings = settings or get_settings()
        self.session_name = session_name
        self.client = TelethonClient(
            self.session_name,
            self.settings.telegram_api_id,
            self.settings.telegram_api_hash,
        )
        logger.info(f"TelegramFetcher initialized with session: {session_name}")

    async def connect(self):
        """Connect and authenticate with Telegram."""
        logger.info("Connecting to Telegram...")
        await self.client.start()
        me = await self.client.get_me()
        logger.info(f"Connected as: {me.username or me.phone}")

    async def disconnect(self):
        """Disconnect from Telegram."""
        await self.client.disconnect()
        logger.info("Disconnected from Telegram")

    async def fetch_messages(
        self,
        channel: str,
        limit: int = 100,
        min_id: int = 0,
    ) -> list[tuple[Message, str]]:
        """
        Fetch messages from a channel.

        Args:
            channel: Channel URL or username
            limit: Maximum messages to fetch
            min_id: Only fetch messages newer than this ID (for incremental sync)

        Returns:
            List of (message, channel_name) tuples
        """
        logger.info(f"Fetching up to {limit} messages from {channel} (min_id={min_id})")

        try:
            entity = await self.client.get_entity(channel)
            logger.debug(
                f"Got entity: {entity.title if hasattr(entity, 'title') else entity}"
            )

            messages = []
            async for message in self.client.iter_messages(
                entity,
                limit=limit,
                min_id=min_id,
            ):
                if message.text:  # Only text messages
                    messages.append((message, channel))

            logger.info(f"Fetched {len(messages)} text messages from {channel}")
            return messages

        except Exception as e:
            logger.error(f"Failed to fetch from {channel}: {type(e).__name__}: {e}")
            return []

    def message_to_laptop(
        self,
        message: Message,
        channel: str,
        extracted: LaptopCreate,
    ) -> Laptop:
        """Convert a Telegram message and extracted data to a Laptop."""
        return Laptop(
            # From extraction
            brand=extracted.brand,
            model=extracted.model,
            cpu=extracted.cpu,
            ram_gb=extracted.ram_gb,
            storage_gb=extracted.storage_gb,
            storage_type=extracted.storage_type,
            screen_size=extracted.screen_size,
            gpu=extracted.gpu,
            price_etb=extracted.price_etb,
            condition=extracted.condition,
            contact=extracted.contact,
            # From message
            channel=channel,
            message_id=message.id,
            posted_at=message.date.replace(tzinfo=None),
            raw_text=message.text,
        )

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()
