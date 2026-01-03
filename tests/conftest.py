"""Pytest fixtures and configuration."""

import os
import pytest
from datetime import datetime
from pathlib import Path


@pytest.fixture
def sample_messages() -> list[str]:
    """Sample Telegram messages for testing."""
    return [
        """
        ✅✅New arrival 2024!!
        DELL INSPIRON 
        ✅  14th generation  
        ✅ Intel core Ultra 7 150U generation 10 cores 12 logical processors upto 5.0GHZ
        Model : inspiron 16 5640
        ✅GRAPHICS: Intel® Iris® Xe graphics
        🖥 Screen :16.1"inch FHD Resolution Screen.
        ✅Storage : 1TB Nvme SSD
        ✅Ram : 16gb DDR4
        Price : 128,500Birr
        📞0932823071
        https://t.me/Linktechcomputers
        """,
        """
        ✅New arrival 
        Brand New Asus vivobook Core i7 -13620H
        ✅16GB Ram DDR4
        ✅ 1TB GB SSD super fast
        ✅ Screen :14.1 inch 
        Price : 115,500
        📞0932823071
        """,
        """
        Hello everyone! 👋
        Check out our new products.
        Contact us at 0911223344
        """,
    ]


@pytest.fixture
def temp_database(tmp_path) -> str:
    """Create a temporary database for testing."""
    db_path = tmp_path / "test_laptops.db"
    return str(db_path)


@pytest.fixture
def mock_settings(temp_database, monkeypatch):
    """Mock settings for testing."""
    monkeypatch.setenv("DATABASE_PATH", temp_database)
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "test_hash")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
    monkeypatch.setenv(
        "OPENROUTER_API_KEY", os.getenv("OPENROUTER_API_KEY", "test_key")
    )
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")

    # Clear settings cache
    from core.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
def sample_laptop():
    """Create a sample laptop for testing."""
    from core.schemas import Laptop

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
