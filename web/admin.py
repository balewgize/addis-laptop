"""Admin dashboard for managing channels and syncing data."""

import asyncio
import time
from datetime import datetime

import streamlit as st
import pandas as pd

from core.config import setup_logging, get_settings
from core.database import Database
from core.extractor import LaptopExtractor
from core.telegram import TelegramFetcher
from core.schemas import ChannelConfig, SyncFrequency, SyncResult

# Setup
logger = setup_logging()
settings = get_settings()

st.set_page_config(
    page_title="Admin - Addis Laptop",
    page_icon="⚙️",
    # layout="wide",
)


# Authentication
def check_password():
    """Simple password authentication."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("🔐 Admin Login")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            if (
                username == settings.admin_username
                and password == settings.admin_password
            ):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid credentials")

    return False


if not check_password():
    st.stop()


# Authenticated content
@st.cache_resource
def get_database() -> Database:
    return Database()


def run_async(coro):
    """Run async function in Streamlit."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def sync_channel_async(
    channel: str,
    limit: int,
    progress_callback=None,
) -> SyncResult:
    """Sync a single channel."""
    db = get_database()
    start_time = time.time()

    if progress_callback:
        progress_callback(f"🔌 Connecting to Telegram...")

    async with TelegramFetcher() as fetcher:
        # Get channel info
        channel_config = db.get_channel(channel)
        min_id = channel_config.last_message_id if channel_config else 0

        if progress_callback:
            progress_callback(f"📥 Fetching messages (from ID {min_id})...")

        messages = await fetcher.fetch_messages(channel, limit=limit, min_id=min_id)

        if not messages:
            if progress_callback:
                progress_callback("📭 No new messages")

            return SyncResult(
                channel=channel,
                messages_fetched=0,
                laptops_extracted=0,
                errors=0,
                skipped=0,
                duration_seconds=time.time() - start_time,
            )

        if progress_callback:
            progress_callback(f"🔍 Processing {len(messages)} messages...")

        laptops_extracted = 0
        errors = 0
        skipped = 0
        max_message_id = min_id

        with LaptopExtractor() as extractor:
            for i, (message, channel_name) in enumerate(messages):
                max_message_id = max(max_message_id, message.id)

                # Skip if exists
                if db.laptop_exists(channel_name, message.id):
                    skipped += 1
                    continue

                if progress_callback and i % 5 == 0:
                    progress_callback(
                        f"🤖 Processing {i + 1}/{len(messages)}... "
                        f"(✅ {laptops_extracted} | ❌ {errors} | ⏭️ {skipped})"
                    )

                try:
                    extracted = extractor.extract(message.text)

                    if extracted:
                        laptop = fetcher.message_to_laptop(
                            message, channel_name, extracted
                        )
                        db.add_laptop(laptop)
                        laptops_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to process message {message.id}: {e}")
                    errors += 1

                await asyncio.sleep(0.3)

    # Update channel sync status
    db.update_channel_sync(
        channel=channel,
        last_message_id=max_message_id,
        messages_count=len(messages),
        laptops_count=laptops_extracted,
    )

    duration = time.time() - start_time

    if progress_callback:
        progress_callback(
            f"✅ Done! {laptops_extracted} laptops extracted in {duration:.1f}s"
        )

    return SyncResult(
        channel=channel,
        messages_fetched=len(messages),
        laptops_extracted=laptops_extracted,
        errors=errors,
        skipped=skipped,
        duration_seconds=duration,
    )


# Header
st.title("⚙️ Admin Dashboard")
st.caption("Manage channels and sync data")

# Logout button
if st.sidebar.button("🚪 Logout"):
    st.session_state.authenticated = False
    st.rerun()

db = get_database()

# Dashboard Stats
st.header("📊 Overview")

stats = db.get_dashboard_stats()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Laptops", stats.total_laptops)
col2.metric("Channels", stats.total_channels)
col3.metric("Views", stats.total_views)
col4.metric("Clicks", stats.total_clicks)
col5.metric("New (7 days)", stats.laptops_last_7_days)

if stats.top_brands:
    st.markdown(
        "**Top Brands:** " + " | ".join([f"{b}: {c}" for b, c in stats.top_brands])
    )

st.divider()

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(
    ["📢 Channels", "🔄 Manual Sync", "⏰ Scheduled Sync", "📋 All Laptops"]
)


# Channels Tab
with tab1:
    st.header("Manage Channels")

    # Add new channel
    st.subheader("➕ Add New Channel")

    with st.form("add_channel"):
        col1, col2 = st.columns(2)

        with col1:
            new_channel = st.text_input(
                "Channel URL",
                placeholder="https://t.me/channelname",
            )
        with col2:
            new_name = st.text_input(
                "Display Name",
                placeholder="My Tech Channel",
            )

        new_frequency = st.selectbox(
            "Sync Frequency",
            options=[
                (SyncFrequency.DAILY, "Daily"),
                (SyncFrequency.EVERY_3_DAYS, "Every 3 Days"),
                (SyncFrequency.WEEKLY, "Weekly"),
                (SyncFrequency.MANUAL, "Manual Only"),
            ],
            format_func=lambda x: x[1],
        )

        submitted = st.form_submit_button("Add Channel", type="primary")

        if submitted:
            if not new_channel or not new_name:
                st.error("Please fill in all fields")
            elif db.get_channel(new_channel):
                st.error("Channel already exists")
            else:
                config = ChannelConfig(
                    channel=new_channel,
                    name=new_name,
                    sync_frequency=new_frequency[0],
                )
                db.add_channel(config)
                st.success(f"Added channel: {new_name}")
                st.rerun()

    st.divider()

    # List channels
    st.subheader("📋 Tracked Channels")

    channels = db.get_all_channels()

    if not channels:
        st.info("No channels added yet. Add one above!")
    else:
        for channel in channels:
            with st.expander(
                f"{'🟢' if channel.is_active else '🔴'} **{channel.name}** — {channel.total_laptops} laptops",
                expanded=False,
            ):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.write(f"**URL:** {channel.channel}")
                    st.write(f"**Frequency:** {channel.sync_frequency.value}")

                with col2:
                    st.write(f"**Total Messages:** {channel.total_messages}")
                    st.write(f"**Total Laptops:** {channel.total_laptops}")

                with col3:
                    if channel.last_synced:
                        days_ago = (datetime.utcnow() - channel.last_synced).days
                        st.write(f"**Last Synced:** {days_ago} days ago")
                    else:
                        st.write("**Last Synced:** Never")

                # Actions
                action_col1, action_col2, action_col3 = st.columns(3)

                with action_col1:
                    new_freq = st.selectbox(
                        "Change frequency",
                        options=list(SyncFrequency),
                        index=list(SyncFrequency).index(channel.sync_frequency),
                        key=f"freq_{channel.id}",
                    )
                    if st.button("Update", key=f"update_{channel.id}"):
                        db.update_channel_config(
                            channel.channel, sync_frequency=new_freq
                        )
                        st.success("Updated!")
                        st.rerun()

                with action_col2:
                    if channel.is_active:
                        if st.button("🔴 Deactivate", key=f"deactivate_{channel.id}"):
                            db.update_channel_config(channel.channel, is_active=False)
                            st.rerun()
                    else:
                        if st.button("🟢 Activate", key=f"activate_{channel.id}"):
                            db.update_channel_config(channel.channel, is_active=True)
                            st.rerun()

                with action_col3:
                    if st.button("🗑️ Delete", key=f"delete_{channel.id}"):
                        db.delete_channel(channel.channel)
                        st.success("Deleted!")
                        st.rerun()


# Manual Sync Tab
with tab2:
    st.header("Manual Sync")

    channels = db.get_all_channels(active_only=True)

    if not channels:
        st.warning("No active channels. Add channels in the Channels tab.")
    else:
        # Select channel
        channel_options = {c.name: c.channel for c in channels}
        selected_name = st.selectbox(
            "Select Channel",
            options=list(channel_options.keys()),
        )
        selected_channel = channel_options[selected_name]

        # Options
        col1, col2 = st.columns(2)

        with col1:
            sync_limit = st.slider(
                "Messages to fetch", min_value=20, max_value=400, value=100, step=20
            )

        with col2:
            channel_config = db.get_channel(selected_channel)
            if channel_config and channel_config.last_synced:
                days_ago = (datetime.utcnow() - channel_config.last_synced).days
                st.info(f"Last synced: {days_ago} days ago")
            else:
                st.info("Never synced before")

        # Sync button
        if st.button("🔄 Start Sync", type="primary", use_container_width=True):
            progress_text = st.empty()
            progress_bar = st.progress(0)

            def update_progress(text: str):
                progress_text.text(text)

            try:
                result = run_async(
                    sync_channel_async(
                        selected_channel,
                        sync_limit,
                        progress_callback=update_progress,
                    )
                )

                progress_bar.progress(100)

                # Show results
                st.success(f"Sync completed in {result.duration_seconds:.1f} seconds!")

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Messages Fetched", result.messages_fetched)
                col2.metric("Laptops Extracted", result.laptops_extracted)
                col3.metric("Errors", result.errors)
                col4.metric("Skipped (duplicates)", result.skipped)

            except Exception as e:
                logger.error(f"Sync failed: {e}")
                st.error(f"Sync failed: {e}")


# Scheduled Sync Tab
with tab3:
    st.header("Scheduled Sync")

    st.info(
        """
    **How scheduled sync works:**

    1. Channels are synced automatically based on their frequency setting
    2. Run the sync script as a cron job or scheduled task
    3. The script checks which channels are due for sync and processes them

    **Setup:**
    ```bash
    # Run manually
    python scripts/sync_channels.py

    # Or set up a cron job (every 6 hours)
    0 */6 * * * cd /path/to/project && python scripts/sync_channels.py
    ```
    """
    )

    # Show channels due for sync
    st.subheader("📅 Channels Due for Sync")

    due_channels = db.get_channels_to_sync()

    if not due_channels:
        st.success("✅ All channels are up to date!")
    else:
        for channel in due_channels:
            days_ago = "never"
            if channel.last_synced:
                days_ago = f"{(datetime.utcnow() - channel.last_synced).days} days ago"

            st.write(
                f"• **{channel.name}** — Last synced: {days_ago} ({channel.sync_frequency.value})"
            )

        if st.button("🔄 Sync All Due Channels", type="primary"):
            total_results = []

            for channel in due_channels:
                st.write(f"Syncing {channel.name}...")
                progress_text = st.empty()

                try:
                    result = run_async(
                        sync_channel_async(
                            channel.channel,
                            limit=200,
                            progress_callback=lambda t: progress_text.text(t),
                        )
                    )
                    total_results.append(result)
                except Exception as e:
                    st.error(f"Failed to sync {channel.name}: {e}")

            # Summary
            st.success("Sync complete!")
            total_laptops = sum(r.laptops_extracted for r in total_results)
            st.metric("Total Laptops Extracted", total_laptops)


# All Laptops Tab
with tab4:
    st.header("All Laptops")

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        filter_channel = st.selectbox(
            "Filter by Channel",
            options=["All"] + [c.name for c in db.get_all_channels()],
        )

    with col2:
        filter_active = st.selectbox(
            "Status",
            options=["Active Only", "All", "Inactive Only"],
        )

    with col3:
        sort_by = st.selectbox(
            "Sort by",
            options=["Newest First", "Most Views", "Most Clicks"],
        )

    # Get laptops
    all_laptops = db.get_laptops(
        limit=500, active_only=(filter_active == "Active Only")
    )

    # Apply filters
    if filter_channel != "All":
        channel_url = next(
            (c.channel for c in db.get_all_channels() if c.name == filter_channel), None
        )
        if channel_url:
            all_laptops = [l for l in all_laptops if l.channel == channel_url]

    if filter_active == "Inactive Only":
        all_laptops = [l for l in all_laptops if not l.is_active]

    # Sort
    if sort_by == "Most Views":
        all_laptops.sort(key=lambda x: x.view_count, reverse=True)
    elif sort_by == "Most Clicks":
        all_laptops.sort(key=lambda x: x.click_count, reverse=True)

    st.caption(f"Showing {len(all_laptops)} laptops")

    if all_laptops:
        # Create DataFrame
        df = pd.DataFrame(
            [
                {
                    "ID": l.id,
                    "Brand": l.brand,
                    "Model": l.model or "",
                    "Price (ETB)": l.price_etb,
                    "RAM": l.ram_gb,
                    "Storage": l.storage_gb,
                    "Views": l.view_count,
                    "Clicks": l.click_count,
                    "Active": "✅" if l.is_active else "❌",
                    "Posted": l.posted_at.strftime("%Y-%m-%d"),
                    "Channel": l.channel.split("/")[-1],
                }
                for l in all_laptops
            ]
        )

        st.dataframe(df, use_container_width=True, hide_index=True)

        # Bulk actions
        st.subheader("Bulk Actions")

        col1, col2 = st.columns(2)

        with col1:
            laptop_id = st.number_input("Laptop ID", min_value=1, step=1)

        with col2:
            action = st.selectbox(
                "Action",
                options=[
                    "Deactivate",
                    "Activate",
                    "Set Featured",
                    "Set Premium",
                    "Set Free",
                ],
            )

        if st.button("Apply Action"):
            if action == "Deactivate":
                db.set_laptop_active(laptop_id, False)
            elif action == "Activate":
                db.set_laptop_active(laptop_id, True)
            elif action == "Set Featured":
                from core.schemas import ListingTier

                db.set_laptop_tier(laptop_id, ListingTier.FEATURED)
            elif action == "Set Premium":
                from core.schemas import ListingTier

                db.set_laptop_tier(laptop_id, ListingTier.PREMIUM)
            elif action == "Set Free":
                from core.schemas import ListingTier

                db.set_laptop_tier(laptop_id, ListingTier.FREE)

            st.success(f"Applied {action} to laptop {laptop_id}")
            st.rerun()
