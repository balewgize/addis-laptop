"""Pytest fixtures and configuration."""

import pytest
import os
from pathlib import Path


@pytest.fixture
def sample_messages() -> list[str]:
    """Sample Telegram messages for testing."""
    return [
        """
        ✅✅New arrival 2024!!
        DELL INSPIRON 
        ✅  14th generation  
        ✅ Intel core Ultra 7 150U generation 10 cores  12 logical processors upto 5.0GHZ
        Model : inspiron 16 5640
        ✅GRAPHICS: Intel® Iris® Xe graphics
        🖥 Screen :16.1"inch FHD Resolution Screen.
        ✅Storage : 1TB Nvme SSD
        ✅Ram : 16gb DDR4
        ✅ 10hours ++ battery life 
        ✅almunium body 
        ✅slim & lightweight 
        ✅powered by B&O SOUND SYSTEM
        Price : 128,500Birr
        @dadmomsisbro2121
        📞0932823071
        https://t.me/Linktechcomputers
        """,
        """
        ✅New arrival 
        Brand New   Asus vivobook  plus H processor
        Asus vivobook Core i7 -13620H
        X360 
            2 in 1  convrtable
        ✅ Touch screen
        ✅Core i7
        ✅ 13th generation   2025
        ✅16GB Ram  DDR4
        ✅   4k resolution
        ✅Base speed  2.40GHZ
        10core and 16logical processor
        ✅  with keyboard light
        ✅ Model   :Asus vivobook 
        ✅   Condition: Brand  new  13th generation
        ✅    1TB  GB SSD  super fast
        ✅  Screen :14.1  inch 
        ✅  With intel Iris Graphics card 
        ✅  Best   battery life 
        Price :        115,500
           @dadmomsisbro2121
        📞0932823071
        https://t.me/Linktechcomputers
        """,
        # Non-laptop message
        """
        Hello everyone! 👋
        Check out our new products.
        Contact us at 0911223344
        """,
    ]


@pytest.fixture
def expected_extractions() -> list[dict]:
    """Expected extraction results for sample messages."""
    return [
        {
            "brand": "Dell",
            "ram_gb": 16,
            "storage_gb": 1000,
            "price_etb": 128500,
            "contact": "0932823071",
        },
        {
            "brand": "Asus",
            "ram_gb": 16,
            "storage_gb": 1000,
            "price_etb": 115500,
            "contact": "0932823071",
        },
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
    monkeypatch.setenv(
        "OPENROUTER_API_KEY", os.getenv("OPENROUTER_API_KEY", "test_key")
    )
