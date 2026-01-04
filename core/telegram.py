"""Telegram client for fetching messages from channels, HTML and JSON exports."""

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient as TelethonClient
from telethon.errors import FloodWaitError
from telethon.tl.types import Message

from .config import Settings, get_settings
from .schemas import Laptop, LaptopCreate

logger = logging.getLogger(__name__)


class ExportedMessage:
    """Represents a message parsed from HTML/JSON export.

    Mimics the interface of telethon Message for compatibility.
    """

    def __init__(
        self,
        message_id: int,
        text: str,
        date: datetime,
        contact: str | None = None,
    ):
        self.id = message_id
        self.text = text
        self.date = date
        self.contact = contact  # Phone number extracted from export

    def __repr__(self) -> str:
        return (
            f"ExportedMessage(id={self.id}, date={self.date}, text={self.text[:50]}...)"
        )


class TelegramFetcher:
    """Fetches messages from Telegram channels, HTML and JSON exports."""

    def __init__(
        self,
        settings: Settings | None = None,
        session_name: str = "addis_laptop_session",
    ):
        self.settings = settings or get_settings()
        self.session_name = session_name
        self._client: TelethonClient | None = None
        logger.info(f"TelegramFetcher initialized with session: {session_name}")

    @property
    def client(self) -> TelethonClient:
        """Lazy initialization of Telegram client."""
        if self._client is None:
            self._client = TelethonClient(
                self.session_name,
                self.settings.telegram_api_id,
                self.settings.telegram_api_hash,
            )
        return self._client

    async def connect(self):
        """Connect and authenticate with Telegram."""
        logger.info("Connecting to Telegram...")
        await self.client.start()
        me = await self.client.get_me()
        logger.info(f"Connected as: {me.username or me.phone}")

    async def disconnect(self):
        """Disconnect from Telegram."""
        if self._client is not None:
            await self._client.disconnect()
            logger.info("Disconnected from Telegram")

    async def get_channel_info(self, channel: str) -> dict | None:
        """Get channel information."""
        try:
            entity = await self.client.get_entity(channel)
            return {
                "id": entity.id,
                "title": getattr(entity, "title", None),
                "username": getattr(entity, "username", None),
            }
        except Exception as e:
            logger.error(f"Failed to get channel info for {channel}: {e}")
            return None

    async def fetch_messages(
        self,
        channel: str,
        limit: int = 100,
        min_id: int = 0,
    ) -> list[tuple[Message, str]]:
        """
        Fetch messages from a channel via Telegram API.

        Args:
            channel: Channel URL or username
            limit: Maximum messages to fetch
            min_id: Only fetch messages newer than this ID

        Returns:
            List of (message, channel) tuples
        """
        logger.info(f"Fetching up to {limit} messages from {channel} (min_id={min_id})")

        try:
            entity = await self.client.get_entity(channel)
            logger.debug(f"Got entity: {getattr(entity, 'title', entity)}")

            messages = []
            async for message in self.client.iter_messages(
                entity,
                limit=limit,
                min_id=min_id,
            ):
                if message.text:
                    messages.append((message, channel))

            logger.info(f"Fetched {len(messages)} text messages from {channel}")
            return messages

        except FloodWaitError as e:
            logger.warning(f"Flood wait {e.seconds}s for {channel}")
            await asyncio.sleep(e.seconds)
            return []
        except Exception as e:
            logger.error(f"Failed to fetch from {channel}: {type(e).__name__}: {e}")
            return []

    def fetch_messages_json(
        self,
        json_path: str | Path,
        channel: str | None = None,
        min_id: int = 0,
    ) -> list[tuple[ExportedMessage, str]]:
        """
        Fetch messages from an exported JSON file.

        Args:
            json_path: Path to the JSON export file
            channel: Channel URL/name. If None, derived from filename
            min_id: Only return messages with ID > min_id

        Returns:
            List of (ExportedMessage, channel) tuples
        """
        json_path = Path(json_path)

        if not json_path.exists():
            logger.error(f"JSON file not found: {json_path}")
            return []

        # Derive channel name from filename if not provided
        if channel is None:
            channel = f"https://t.me/{json_path.stem}"

        logger.info(f"Parsing JSON export: {json_path} for channel: {channel}")

        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read JSON file: {e}")
            return []

        messages = []
        raw_messages = data.get("messages", [])

        for msg in raw_messages:
            if msg.get("type") != "message":
                continue

            message_id = msg.get("id")
            if not message_id:
                continue

            if message_id <= min_id:
                continue

            # Extract text and contact from text_entities field
            text_entities = msg.get("text_entities", [])
            text, contact = self._extract_from_text_entities(text_entities)

            if not text or len(text.strip()) < 10:
                logger.debug(f"Skipping message {message_id}: text too short")
                continue

            date_str = msg.get("date", "")
            date = self._parse_json_date(date_str)

            exported_message = ExportedMessage(
                message_id=message_id,
                text=text,
                date=date,
                contact=contact,
            )
            messages.append((exported_message, channel))

        logger.info(f"Parsed {len(messages)} messages from JSON (min_id={min_id})")
        return messages

    def _extract_from_text_entities(self, entities: list) -> tuple[str, str | None]:
        """
        Extract text and contact from text_entities field.

        Args:
            entities: List of entity objects with type and text

        Returns:
            Tuple of (text, contact)
        """
        if not entities:
            return "", None

        text_parts = []
        contact = None

        for entity in entities:
            if not isinstance(entity, dict):
                continue

            entity_type = entity.get("type", "")
            entity_text = entity.get("text", "")

            if entity_type == "phone":
                contact = entity_text

            text_parts.append(entity_text)

        text = "".join(text_parts)

        # Clean up whitespace
        lines = text.split("\n")
        cleaned_lines = [line.strip() for line in lines]
        text = "\n".join(cleaned_lines)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip(), contact

    def _parse_json_date(self, date_str: str) -> datetime:
        """
        Parse date from Telegram JSON export format.

        Format: "2026-01-03T12:17:03"
        """
        if not date_str:
            return datetime.now()

        try:
            return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            logger.warning(f"Failed to parse date: {date_str}")
            return datetime.now()

    def message_to_laptop(
        self,
        message: Message | ExportedMessage,
        channel: str,
        extracted: LaptopCreate,
    ) -> Laptop:
        """Convert a Telegram message and extracted data to a Laptop."""
        # Handle both Message and ExportedMessage
        posted_at = message.date
        if hasattr(posted_at, "replace") and posted_at.tzinfo is not None:
            posted_at = posted_at.replace(tzinfo=None)

        return Laptop(
            brand=extracted.brand,
            model=extracted.model,
            cpu=extracted.cpu,
            ram_gb=extracted.ram_gb,
            storage_gb=extracted.storage_gb,
            storage_type=extracted.storage_type,
            screen_size=extracted.screen_size,
            gpu=extracted.gpu,
            price_etb=extracted.price_etb,
            battery_life=extracted.battery_life,
            condition=extracted.condition,
            contact=extracted.contact,
            channel=channel,
            message_id=message.id,
            posted_at=posted_at,
            raw_text=message.text,
        )

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()
