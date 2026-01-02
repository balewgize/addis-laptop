"""Tests for the recommendation engine."""

import pytest
from datetime import datetime

from telegram_laptop_scraper.database import Database
from telegram_laptop_scraper.recommender import Recommender
from telegram_laptop_scraper.schemas import Laptop, RecommendationQuery


class TestRecommender:
    """Tests for Recommender class."""

    @pytest.fixture
    def db(self, temp_database, monkeypatch):
        """Create a test database with sample data."""
        monkeypatch.setenv("DATABASE_PATH", temp_database)
        from telegram_laptop_scraper.config import get_settings

        get_settings.cache_clear()

        db = Database()

        # Add sample laptops
        laptops = [
            Laptop(
                brand="Dell",
                model="Budget",
                ram_gb=8,
                storage_gb=256,
                price_etb=50000,
                condition="new",
                channel="test",
                message_id=1,
                posted_at=datetime.utcnow(),
                raw_text="test",
            ),
            Laptop(
                brand="Dell",
                model="Mid-range",
                ram_gb=16,
                storage_gb=512,
                price_etb=85000,
                condition="new",
                channel="test",
                message_id=2,
                posted_at=datetime.utcnow(),
                raw_text="test",
            ),
            Laptop(
                brand="Asus",
                model="Gaming",
                ram_gb=32,
                storage_gb=1000,
                price_etb=150000,
                condition="new",
                channel="test",
                message_id=3,
                posted_at=datetime.utcnow(),
                raw_text="test",
            ),
        ]

        for laptop in laptops:
            db.add(laptop)

        return db

    @pytest.fixture
    def recommender(self, db):
        """Create a recommender with test database."""
        return Recommender(db)

    def test_recommend_by_budget(self, recommender):
        """Test budget filtering."""
        query = RecommendationQuery(budget_max=60000)
        results = recommender.recommend(query)

        assert len(results) == 1
        assert results[0].brand == "Dell"
        assert results[0].model == "Budget"

    def test_recommend_by_ram(self, recommender):
        """Test RAM filtering."""
        query = RecommendationQuery(min_ram=16)
        results = recommender.recommend(query)

        assert len(results) == 2
        assert all(r.ram_gb >= 16 for r in results)

    def test_recommend_by_use_case(self, recommender):
        """Test use case profiles."""
        # Programming: needs 16GB RAM, 256GB storage
        query = RecommendationQuery(use_case="programming")
        results = recommender.recommend(query)

        assert len(results) == 2
        assert all(r.ram_gb >= 16 for r in results)

    def test_recommend_by_brand(self, recommender):
        """Test brand filtering."""
        query = RecommendationQuery(brand="Dell")
        results = recommender.recommend(query)

        assert len(results) == 2
        assert all(r.brand == "Dell" for r in results)

    def test_recommend_combined_filters(self, recommender):
        """Test combining multiple filters."""
        query = RecommendationQuery(
            budget_max=100000,
            min_ram=16,
            brand="Dell",
        )
        results = recommender.recommend(query)

        assert len(results) == 1
        assert results[0].model == "Mid-range"

    def test_recommend_no_results(self, recommender):
        """Test when no laptops match criteria."""
        query = RecommendationQuery(
            budget_max=10000,  # Too low
            min_ram=64,  # Too high
        )
        results = recommender.recommend(query)

        assert len(results) == 0
