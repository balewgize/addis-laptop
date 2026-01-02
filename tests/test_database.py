"""Tests for database operations."""

import pytest
from datetime import datetime, timedelta

from telegram_laptop_scraper.database import Database
from telegram_laptop_scraper.schemas import Laptop, SearchFilters


class TestDatabase:
    """Tests for Database class."""

    @pytest.fixture
    def db(self, temp_database, monkeypatch):
        """Create a test database."""
        monkeypatch.setenv("DATABASE_PATH", temp_database)
        # Clear settings cache
        from telegram_laptop_scraper.config import get_settings

        get_settings.cache_clear()
        return Database()

    @pytest.fixture
    def sample_laptop(self) -> Laptop:
        """Create a sample laptop for testing."""
        return Laptop(
            brand="Dell",
            model="Inspiron 15",
            cpu="Intel Core i7",
            ram_gb=16,
            storage_gb=512,
            storage_type="SSD",
            screen_size=15.6,
            gpu="Intel Iris Xe",
            price_etb=85000,
            condition="new",
            contact="0912345678",
            channel="https://t.me/testchannel",
            message_id=12345,
            posted_at=datetime.utcnow(),
            raw_text="Sample laptop message",
        )

    def test_add_and_get_laptop(self, db, sample_laptop):
        """Test adding and retrieving a laptop."""
        added = db.add(sample_laptop)

        assert added.id is not None
        assert added.brand == "Dell"

        retrieved = db.get_by_id(added.id)
        assert retrieved is not None
        assert retrieved.brand == "Dell"
        assert retrieved.ram_gb == 16

    def test_exists_check(self, db, sample_laptop):
        """Test duplicate detection."""
        assert not db.exists(sample_laptop.channel, sample_laptop.message_id)

        db.add(sample_laptop)

        assert db.exists(sample_laptop.channel, sample_laptop.message_id)

    def test_search_by_brand(self, db, sample_laptop):
        """Test searching by brand."""
        db.add(sample_laptop)

        results = db.search(SearchFilters(brand="Dell"))
        assert len(results) == 1

        results = db.search(SearchFilters(brand="HP"))
        assert len(results) == 0

    def test_search_by_price(self, db, sample_laptop):
        """Test searching by price range."""
        db.add(sample_laptop)

        results = db.search(SearchFilters(max_price=100000))
        assert len(results) == 1

        results = db.search(SearchFilters(max_price=50000))
        assert len(results) == 0

        results = db.search(SearchFilters(min_price=80000, max_price=90000))
        assert len(results) == 1

    def test_search_by_ram(self, db, sample_laptop):
        """Test searching by minimum RAM."""
        db.add(sample_laptop)

        results = db.search(SearchFilters(min_ram=16))
        assert len(results) == 1

        results = db.search(SearchFilters(min_ram=32))
        assert len(results) == 0

    def test_channel_sync_status(self, db):
        """Test channel sync tracking."""
        channel = "https://t.me/testchannel"

        # Initially no status
        status = db.get_channel_sync_status(channel)
        assert status is None

        # Should sync (never synced)
        assert db.should_sync_channel(channel) is True

        # Update sync status
        db.update_channel_sync(channel, message_count=50, laptop_count=10)

        # Check status
        status = db.get_channel_sync_status(channel)
        assert status is not None
        assert status.message_count == 50
        assert status.laptop_count == 10

        # Should not sync (just synced)
        assert db.should_sync_channel(channel) is False

    def test_count(self, db, sample_laptop):
        """Test counting laptops."""
        assert db.count() == 0

        db.add(sample_laptop)
        assert db.count() == 1

        # Add another with different message_id
        sample_laptop.message_id = 99999
        db.add(sample_laptop)
        assert db.count() == 2
