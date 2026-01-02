"""Standalone Streamlit UI for Telegram Laptop Scraper."""

import asyncio
import logging
from datetime import datetime

import streamlit as st
import pandas as pd

from telegram_laptop_scraper.config import setup_logging, get_settings
from telegram_laptop_scraper.database import Database
from telegram_laptop_scraper.extractor import LaptopExtractor
from telegram_laptop_scraper.recommender import Recommender
from telegram_laptop_scraper.schemas import (
    RecommendationQuery,
    SearchFilters,
    SyncResult,
)
from telegram_laptop_scraper.telegram import TelegramFetcher

logger = setup_logging()

st.set_page_config(
    page_title="Laptop Scraper",
    page_icon="💻",
    layout="wide",
)

st.title("💻 Telegram Laptop Scraper")
st.caption("Find the best laptop deals from Ethiopian Telegram channels")


@st.cache_resource
def get_database() -> Database:
    """Get cached database instance."""
    logger.info("Initializing database...")
    return Database()


@st.cache_resource
def get_recommender() -> Recommender:
    """Get cached recommender instance."""
    return Recommender(get_database())


def run_async(coro):
    """Run async function in Streamlit."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def sync_channel(
    channel: str,
    limit: int,
    force: bool = False,
    progress_callback=None,
) -> SyncResult:
    """
    Sync a channel and extract laptop data.

    Args:
        channel: Telegram channel URL
        limit: Max messages to fetch
        force: Bypass cooldown check
        progress_callback: Function to call with progress updates
    """
    db = get_database()
    settings = get_settings()

    # Check cooldown unless forced
    if not force and not db.should_sync_channel(channel, settings.sync_cooldown_days):
        status = db.get_channel_sync_status(channel)
        days_ago = (datetime.utcnow() - status.last_synced).days
        logger.info(
            f"Channel {channel} synced {days_ago} days ago, skipping (use force=True to override)"
        )

        if progress_callback:
            progress_callback(
                f"⏭️ Channel synced {days_ago} days ago. Using cached data."
            )

        return SyncResult(
            channel=channel,
            messages_fetched=0,
            laptops_extracted=0,
            errors=0,
            skipped=status.laptop_count,
        )

    if progress_callback:
        progress_callback("🔌 Connecting to Telegram...")

    async with TelegramFetcher() as fetcher:
        # Get latest message ID for incremental sync
        min_id = db.get_latest_message_id(channel)
        logger.info(f"Starting sync from message ID {min_id}")

        if progress_callback:
            progress_callback(f"📥 Fetching messages from {channel}...")

        messages = await fetcher.fetch_messages(channel, limit=limit, min_id=min_id)

        if not messages:
            if progress_callback:
                progress_callback("📭 No new messages found")

            # Still update sync status
            existing_count = db.count_by_channel(channel)
            db.update_channel_sync(channel, 0, existing_count)

            return SyncResult(
                channel=channel,
                messages_fetched=0,
                laptops_extracted=0,
                errors=0,
                skipped=0,
            )

        if progress_callback:
            progress_callback(f"🔍 Extracting data from {len(messages)} messages...")

        laptops_extracted = 0
        errors = 0
        skipped = 0

        with LaptopExtractor() as extractor:
            for i, (message, channel_name) in enumerate(messages):
                # Skip if already processed
                if db.exists(channel_name, message.id):
                    skipped += 1
                    continue

                # Update progress
                if progress_callback and i % 5 == 0:
                    progress_callback(
                        f"🤖 Processing message {i + 1}/{len(messages)}... "
                        f"(✅ {laptops_extracted} extracted, ❌ {errors} failed)"
                    )

                # Extract laptop data
                try:
                    extracted = extractor.extract(message.text)

                    if extracted:
                        laptop = fetcher.message_to_laptop(
                            message, channel_name, extracted
                        )
                        db.add(laptop)
                        laptops_extracted += 1
                        logger.info(
                            f"✅ Extracted: {extracted.brand} {extracted.model or ''}"
                        )
                    else:
                        logger.debug(f"⏭️ Message {message.id} is not a laptop listing")

                except Exception as e:
                    errors += 1
                    logger.error(f"❌ Failed to process message {message.id}: {e}")

                # Small delay to avoid rate limiting
                await asyncio.sleep(1)

    # Update sync status
    total_laptops = db.count_by_channel(channel)
    db.update_channel_sync(channel, len(messages), total_laptops)

    if progress_callback:
        progress_callback(
            f"✅ Done! Extracted {laptops_extracted} laptops from {len(messages)} messages"
        )

    return SyncResult(
        channel=channel,
        messages_fetched=len(messages),
        laptops_extracted=laptops_extracted,
        errors=errors,
        skipped=skipped,
    )


with st.sidebar:
    st.header("⚙️ Channel Sync")

    # Channel input
    channel_url = st.text_input(
        "Channel URL",
        placeholder="https://t.me/Linktechcomputers",
        help="Enter a Telegram channel URL to scrape",
    )

    sync_limit = st.slider(
        "Messages to fetch",
        min_value=10,
        max_value=200,
        value=50,
        help="Maximum number of messages to fetch from the channel",
    )

    force_sync = st.checkbox(
        "Force sync (bypass weekly cooldown)",
        help="By default, channels are only synced once per week",
    )

    if st.button("🔄 Sync Channel", type="primary", disabled=not channel_url):
        progress_text = st.empty()
        progress_bar = st.progress(0)

        def update_progress(text: str):
            progress_text.text(text)

        try:
            result = run_async(
                sync_channel(
                    channel_url,
                    sync_limit,
                    force=force_sync,
                    progress_callback=update_progress,
                )
            )

            progress_bar.progress(100)

            if result.laptops_extracted > 0:
                st.success(f"Extracted {result.laptops_extracted} new laptops!")
            elif result.skipped > 0:
                st.info(f"Using {result.skipped} cached laptops")
            else:
                st.warning("No laptops found in messages")

            if result.errors > 0:
                st.warning(f"{result.errors} messages failed to process")

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            st.error(f"Sync failed: {e}")

    st.divider()

    # Channel status
    st.subheader("📊 Synced Channels")
    db = get_database()
    statuses = db.get_all_channel_statuses()

    if statuses:
        for status in statuses:
            channel_name = status.channel.split("/")[-1]
            days_ago = (datetime.utcnow() - status.last_synced).days
            st.write(f"**@{channel_name}**")
            st.caption(f"📦 {status.laptop_count} laptops • 🕐 {days_ago}d ago")
    else:
        st.caption("No channels synced yet")

    st.divider()

    st.subheader("📈 Database Stats")
    st.metric("Total Laptops", db.count())


# Main content tabs
tab1, tab2, tab3 = st.tabs(["🔍 Browse", "🎯 Recommend", "📋 Export"])


with tab1:
    st.header("Browse Laptops")

    # Filters
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        brand_filter = st.text_input("Brand", placeholder="Dell, Asus...")
    with col2:
        max_price = st.number_input("Max Price (ETB)", min_value=0, value=0, step=10000)
    with col3:
        min_ram = st.selectbox("Min RAM (GB)", [None, 8, 16, 32], index=0)
    with col4:
        min_storage = st.selectbox("Min Storage (GB)", [None, 256, 512, 1000], index=0)

    # Build search filters
    filters = SearchFilters(
        brand=brand_filter if brand_filter else None,
        max_price=max_price if max_price > 0 else None,
        min_ram=min_ram,
        min_storage=min_storage,
    )

    db = get_database()

    has_filters = any([brand_filter, max_price > 0, min_ram, min_storage])
    if has_filters:
        laptops = db.search(filters)
    else:
        laptops = db.get_all(limit=100)

    if not laptops:
        st.info("No laptops found. Try syncing a channel first!")
    else:
        st.caption(f"Showing {len(laptops)} laptops")

        for laptop in laptops:
            price_str = (
                f"ETB {laptop.price_etb:,.0f}" if laptop.price_etb else "Price: Call"
            )

            with st.expander(f"**{laptop.brand}** {laptop.model or ''} — {price_str}"):
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Specifications**")
                    st.write(f"🔲 CPU: {laptop.cpu or 'N/A'}")
                    st.write(f"🧠 RAM: {laptop.ram_gb or 'N/A'} GB")
                    storage_info = f"{laptop.storage_gb or 'N/A'} GB"
                    if laptop.storage_type:
                        storage_info += f" {laptop.storage_type}"
                    st.write(f"💾 Storage: {storage_info}")
                    st.write(f"🖥️ Screen: {laptop.screen_size or 'N/A'} inches")
                    st.write(f"🎮 GPU: {laptop.gpu or 'N/A'}")

                with col2:
                    st.markdown("**Details**")
                    st.write(f"📦 Condition: {laptop.condition or 'N/A'}")
                    st.write(f"📞 Contact: {laptop.contact or 'N/A'}")
                    st.write(f"📅 Posted: {laptop.posted_at.strftime('%Y-%m-%d')}")
                    channel_name = laptop.channel.split("/")[-1]
                    st.write(f"📢 Channel: @{channel_name}")

                with st.expander("📝 Original Message"):
                    st.code(laptop.raw_text)


with tab2:
    st.header("Get Recommendations")

    col1, col2 = st.columns(2)

    with col1:
        budget = st.number_input(
            "Budget (ETB)",
            min_value=0,
            value=100000,
            step=10000,
            help="Maximum price you're willing to pay",
        )

        use_case = st.selectbox(
            "Use Case",
            [None, "programming", "gaming", "office", "general"],
            format_func=lambda x: x.title() if x else "Any",
            help="What will you use the laptop for?",
        )

    with col2:
        rec_brand = st.text_input("Preferred Brand (optional)")
        rec_min_ram = st.selectbox("Minimum RAM (GB)", [None, 8, 16, 32], key="rec_ram")
        rec_min_storage = st.selectbox(
            "Minimum Storage (GB)", [None, 256, 512, 1000], key="rec_storage"
        )

    if st.button("🎯 Get Recommendations", type="primary"):
        query = RecommendationQuery(
            budget_max=budget if budget > 0 else None,
            use_case=use_case,
            brand=rec_brand if rec_brand else None,
            min_ram=rec_min_ram,
            min_storage=rec_min_storage,
        )

        recommender = get_recommender()
        recommendations = recommender.recommend(query)

        if not recommendations:
            st.warning("No laptops match your criteria. Try adjusting your filters.")
        else:
            st.success(f"Found {len(recommendations)} recommendations!")

            for i, laptop in enumerate(recommendations, 1):
                price_str = (
                    f"ETB {laptop.price_etb:,.0f}"
                    if laptop.price_etb
                    else "Call for price"
                )

                st.markdown(f"### #{i} {laptop.brand} {laptop.model or ''}")

                cols = st.columns([2, 1])

                with cols[0]:
                    specs = []
                    if laptop.cpu:
                        specs.append(f"🔲 {laptop.cpu}")
                    if laptop.ram_gb:
                        specs.append(f"🧠 {laptop.ram_gb}GB RAM")
                    if laptop.storage_gb:
                        storage_str = f"💾 {laptop.storage_gb}GB"
                        if laptop.storage_type:
                            storage_str += f" {laptop.storage_type}"
                        specs.append(storage_str)

                    st.write(" • ".join(specs) if specs else "Specs not available")

                with cols[1]:
                    st.metric("Price", price_str)
                    if laptop.contact:
                        st.write(f"📞 {laptop.contact}")

                st.divider()


with tab3:
    st.header("Export Data")

    db = get_database()
    laptops = db.get_all(limit=1000)

    if not laptops:
        st.info("No data to export. Sync some channels first!")
    else:
        df = pd.DataFrame([laptop.model_dump() for laptop in laptops])

        # Select columns to display
        display_cols = [
            "id",
            "brand",
            "model",
            "cpu",
            "ram_gb",
            "storage_gb",
            "price_etb",
            "condition",
            "contact",
            "posted_at",
            "channel",
        ]
        display_cols = [c for c in display_cols if c in df.columns]

        st.dataframe(
            df[display_cols],
            use_container_width=True,
            hide_index=True,
        )

        # Download buttons
        col1, col2 = st.columns(2)

        with col1:
            csv = df.to_csv(index=False)
            st.download_button(
                "📥 Download CSV",
                csv,
                "laptops.csv",
                "text/csv",
            )

        with col2:
            json_data = df.to_json(orient="records", indent=2)
            st.download_button(
                "📥 Download JSON",
                json_data,
                "laptops.json",
                "application/json",
            )
