"""Tests for the recommendation engine."""

import pytest
from datetime import datetime

from core.database import Database
from core.recommender import LLMRecommender
from core.schemas import Laptop, RecommendationRequest


class TestRecommender:
    """Tests for LLMRecommender."""

    @pytest.fixture
    def db_with_data(self, mock_settings):
        """Create database with test data."""
        db = Database()

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
            db.add_laptop(laptop)

        return db

    def test_get_candidates(self, db_with_data):
        """Test candidate filtering."""
        recommender = LLMRecommender(db_with_data)

        request = RecommendationRequest(budget_max=100000)
        candidates = recommender._get_candidates(request)

        assert len(candidates) == 2
        assert all(l.price_etb <= 100000 for l in candidates)

    def test_format_requirements(self, db_with_data):
        """Test requirements formatting."""
        recommender = LLMRecommender(db_with_data)

        request = RecommendationRequest(
            budget_max=100000,
            use_case="programming",
        )
        formatted = recommender._format_requirements(request)

        assert "100,000" in formatted
        assert "programming" in formatted

    def test_fallback_recommendations(self, db_with_data):
        """Test fallback when LLM fails."""
        recommender = LLMRecommender(db_with_data)

        request = RecommendationRequest(budget_max=100000)
        candidates = recommender._get_candidates(request)

        response = recommender._fallback_recommendations(candidates, request, 3)

        assert len(response.recommendations) <= 3
        assert response.query_summary
