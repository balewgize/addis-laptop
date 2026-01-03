"""Tests for database operations."""

import pytest
from datetime import datetime, timedelta

from core.database import Database
from core.schemas import (
    Laptop,
    SearchFilters,
    ChannelConfig,
    SyncFrequency,
)


class TestDatabase:
    """Tests for Database class."""

    @pytest.fixture
    def db(self, mock_settings):
        """Create a test database."""
        return Database()

    def test_add_and_get_laptop(self, db, sample_laptop):
        """Test adding and retrieving a laptop."""
        added = db.add_laptop(sample_laptop)

        assert added.id is not None
        assert added.brand == "Dell"

        retrieved = db.get_laptop_by_id(added.id)
        assert retrieved is not None
        assert retrieved.brand == "Dell"
        assert retrieved.ram_gb == 16

    def test_laptop_exists(self, db, sample_laptop):
        """Test duplicate detection."""
        assert not db.laptop_exists(sample_laptop.channel, sample_laptop.message_id)

        db.add_laptop(sample_laptop)

        assert db.laptop_exists(sample_laptop.channel, sample_laptop.message_id)

    def test_search_by_brand(self, db, sample_laptop):
        """Test searching by brand."""
        db.add_laptop(sample_laptop)

        results = db.search_laptops(SearchFilters(brand="Dell"))
        assert len(results) == 1

        results = db.search_laptops(SearchFilters(brand="HP"))
        assert len(results) == 0

    def test_search_by_price(self, db, sample_laptop):
        """Test searching by price range."""
        db.add_laptop(sample_laptop)

        results = db.search_laptops(SearchFilters(max_price=100000))
        assert len(results) == 1

        results = db.search_laptops(SearchFilters(max_price=50000))
        assert len(results) == 0

    def test_view_count(self, db, sample_laptop):
        """Test view count increment."""
        added = db.add_laptop(sample_laptop)
        assert added.view_count == 0

        db.increment_view_count(added.id)

        retrieved = db.get_laptop_by_id(added.id)
        assert retrieved.view_count == 1

    def test_channel_operations(self, db):
        """Test channel CRUD operations."""
        config = ChannelConfig(
            channel="https://t.me/testchannel",
            name="Test Channel",
            sync_frequency=SyncFrequency.WEEKLY,
        )

        # Add
        added = db.add_channel(config)
        assert added.id is not None

        # Get
        retrieved = db.get_channel(config.channel)
        assert retrieved is not None
        assert retrieved.name == "Test Channel"

        # Update
        db.update_channel_config(config.channel, sync_frequency=SyncFrequency.DAILY)
        updated = db.get_channel(config.channel)
        assert updated.sync_frequency == SyncFrequency.DAILY

        # Delete
        db.delete_channel(config.channel)
        deleted = db.get_channel(config.channel)
        assert deleted is None

    def test_channels_to_sync(self, db):
        """Test getting channels due for sync."""
        # Add channel that was never synced
        config1 = ChannelConfig(
            channel="https://t.me/channel1",
            name="Channel 1",
            sync_frequency=SyncFrequency.DAILY,
        )
        db.add_channel(config1)

        # Should be in sync list
        due = db.get_channels_to_sync()
        assert len(due) == 1

        # Update sync status
        db.update_channel_sync("https://t.me/channel1", 100, 10, 5)

        # Should not be in sync list (just synced)
        due = db.get_channels_to_sync()
        assert len(due) == 0
