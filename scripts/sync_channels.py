#!/usr/bin/env python3
"""Script to sync all channels that are due for update.

Run this as a cron job or scheduled task.

Example cron (every 6 hours):
    0 */6 * * * cd /path/to/project && python scripts/sync_channels.py
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import setup_logging
from core.database import Database
from core.extractor import LaptopExtractor
from core.telegram import TelegramFetcher
from core.schemas import SyncResult

logger = setup_logging()


async def sync_channel(
    channel: str,
    min_id: int,
    limit: int = 200,
) -> SyncResult:
    """Sync a single channel."""
    db = Database()
    start_time = time.time()

    logger.info(f"Starting sync for {channel}")

    async with TelegramFetcher() as fetcher:
        messages = await fetcher.fetch_messages(channel, limit=limit, min_id=min_id)

        if not messages:
            logger.info(f"No new messages for {channel}")
            return SyncResult(
                channel=channel,
                messages_fetched=0,
                laptops_extracted=0,
                errors=0,
                skipped=0,
                duration_seconds=time.time() - start_time,
            )

        laptops_extracted = 0
        errors = 0
        skipped = 0
        max_message_id = min_id

        with LaptopExtractor() as extractor:
            for message, channel_name in messages:
                max_message_id = max(max_message_id, message.id)

                if db.laptop_exists(channel_name, message.id):
                    skipped += 1
                    continue

                try:
                    extracted = extractor.extract(message.text)

                    if extracted:
                        laptop = fetcher.message_to_laptop(
                            message, channel_name, extracted
                        )
                        db.add_laptop(laptop)
                        laptops_extracted += 1
                        logger.info(
                            f"Extracted: {extracted.brand} {extracted.model or ''}"
                        )

                except Exception as e:
                    logger.error(f"Failed to process message {message.id}: {e}")
                    errors += 1

                await asyncio.sleep(0.3)

        # Update sync status
        db.update_channel_sync(
            channel=channel,
            last_message_id=max_message_id,
            messages_count=len(messages),
            laptops_count=laptops_extracted,
        )

    duration = time.time() - start_time
    logger.info(f"Completed {channel}: {laptops_extracted} laptops in {duration:.1f}s")

    return SyncResult(
        channel=channel,
        messages_fetched=len(messages),
        laptops_extracted=laptops_extracted,
        errors=errors,
        skipped=skipped,
        duration_seconds=duration,
    )


async def sync_all_due_channels():
    """Sync all channels that are due based on their frequency."""
    db = Database()
    channels = db.get_channels_to_sync()

    if not channels:
        logger.info("No channels due for sync")
        return

    logger.info(f"Found {len(channels)} channels to sync")

    results = []
    for channel in channels:
        try:
            result = await sync_channel(
                channel.channel,
                min_id=channel.last_message_id,
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to sync {channel.channel}: {e}")

    # Summary
    total_laptops = sum(r.laptops_extracted for r in results)
    total_errors = sum(r.errors for r in results)

    logger.info(
        f"Sync complete: {total_laptops} laptops extracted, {total_errors} errors"
    )


def main():
    """Main entry point."""
    logger.info("Starting scheduled sync...")
    asyncio.run(sync_all_due_channels())
    logger.info("Scheduled sync finished")


if __name__ == "__main__":
    main()
