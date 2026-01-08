#!/usr/bin/env python3
"""Script to sync laptops from JSON exports.

Export channels from Telegram Desktop and place JSON files in data/exports/

Usage:
    # Sync all JSON files in data/exports/
    python scripts/sync_json.py

    # Sync specific file
    python scripts/sync_json.py data/exports/Linktechcomputers.json
"""

import sys
import time
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import setup_logging
from core.database import Database
from core.extractor import LaptopExtractor
from core.telegram import TelegramFetcher
from core.schemas import SyncResult

logger = setup_logging()

EXPORTS_DIR = Path("data/exports")


def sync_json_file(json_path: Path, dry_run: bool = False) -> SyncResult:
    """Sync a single JSON export file."""
    db = Database()
    fetcher = TelegramFetcher()
    start_time = time.time()

    # Derive channel from filename
    channel = f"https://t.me/{json_path.stem}"
    logger.info(f"Starting sync for {json_path} -> {channel}")

    # Get min_id to avoid duplicates
    channel_config = db.get_channel(channel)
    if not channel_config:
        logger.error(f"Channel not found in database: {channel}")
        return SyncResult(
            channel=channel,
            messages_fetched=0,
            laptops_extracted=0,
            errors=1,
            skipped=0,
            duration_seconds=time.time() - start_time,
        )

    min_id = channel_config.last_message_id
    logger.info(f"Using min_id={min_id}")

    messages = fetcher.fetch_messages_json(
        json_path=json_path,
        channel=channel,
        min_id=min_id,
    )

    if not messages:
        logger.info(f"No new messages in {json_path}")
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
                if extracted is None:
                    continue
                extracted.contact = message.contact  # contact will come form JSON

                laptop = fetcher.message_to_laptop(message, channel_name, extracted)

                if dry_run:
                    logger.info(
                        f"[DRY RUN] Would save: {laptop.brand} {laptop.model} - {laptop.price_etb} ETB"
                    )
                    laptops_extracted += 1
                    continue

                # TODO: check for duplicate before saving
                db.add_laptop(laptop)
                laptops_extracted += 1
                logger.info(f"Extracted: {extracted.brand} {extracted.model or ''}")

            except Exception as e:
                logger.exception(f"Failed to process message {message.id}")
                errors += 1

    if dry_run:
        logger.info(
            f"[DRY RUN] Would update channel {channel} with max_message_id={max_message_id}"
        )
    else:
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


def list_json_exports(exports_dir: str = "data/exports") -> list[Path]:
    """List all JSON export files in the exports directory."""
    exports_path = Path(exports_dir)

    if not exports_path.exists():
        logger.warning(f"Exports directory not found: {exports_path}")
        return []

    json_files = list(exports_path.glob("*.json"))
    logger.info(f"Found {len(json_files)} JSON exports in {exports_path}")

    return json_files


def sync_all_exports(dry_run: bool = False) -> list[SyncResult]:
    """Sync all JSON exports in the exports directory."""
    json_files = list_json_exports(str(EXPORTS_DIR))

    if not json_files:
        logger.warning(f"No JSON files found in {EXPORTS_DIR}")
        return []

    logger.info(f"Found {len(json_files)} JSON exports to sync")

    results = []
    for json_path in json_files:
        try:
            result = sync_json_file(json_path, dry_run)
            results.append(result)
        except Exception as e:
            logger.exception(f"Failed to sync {json_path}")

    # Summary
    total_laptops = sum(r.laptops_extracted for r in results)
    total_errors = sum(r.errors for r in results)

    logger.info("=" * 50)
    logger.info("SYNC SUMMARY")
    logger.info("=" * 50)
    for result in results:
        logger.info(
            f"  {result.channel}: {result.laptops_extracted} laptops, {result.errors} errors"
        )
    logger.info("=" * 50)
    logger.info(f"Total: {total_laptops} laptops, {total_errors} errors")

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync laptop listings from Telegram JSON exports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "json_path",
        nargs="?",
        help="Path to JSON file (if not provided, syncs all files in data/exports/)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't save to database, just show what would be extracted",
    )

    args = parser.parse_args()

    if args.json_path:
        json_path = Path(args.json_path)
        if not json_path.exists():
            logger.error(f"File not found: {json_path}")
            sys.exit(1)

        sync_json_file(json_path, dry_run=args.dry_run)

    else:
        sync_all_exports(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
