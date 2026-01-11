"""Tests for bot core logic."""

import pytest
from unittest.mock import Mock, patch

from bot.core import LaptopBot


class TestLaptopBot:
    """Tests for LaptopBot core functionality."""

    @patch("bot.core.Database")
    @patch("bot.core.LLMRecommender")
    @patch("bot.core.QueryParser")
    def test_initialization(self, mock_query_parser, mock_recommender, mock_db):
        """Test that LaptopBot initializes correctly."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.elevenlabs_api_key = ""

        bot = LaptopBot(settings=mock_settings)

        # Check that dependencies are initialized
        assert bot.settings == mock_settings
        mock_db.assert_called_once()
        mock_recommender.assert_called_once_with(mock_db.return_value)
        mock_query_parser.assert_called_once_with(mock_settings)

        # Check that handlers are created
        assert bot.command_handlers is not None
        assert bot.search_handlers is not None
        assert bot.recommend_handlers is not None
        assert bot.message_handlers is not None

        # Voice features should be disabled (empty API key)
        assert bot.transcriber is None
        assert bot.voice_handler is None

    @patch("bot.core.Database")
    @patch("bot.core.LLMRecommender")
    @patch("bot.core.QueryParser")
    @patch("bot.core.Transcriber")
    @patch("bot.core.VoiceHandler")
    def test_initialization_with_voice(
        self,
        mock_voice_handler,
        mock_transcriber,
        mock_query_parser,
        mock_recommender,
        mock_db,
    ):
        """Test that LaptopBot initializes with voice features enabled."""
        # Mock settings with API key
        mock_settings = Mock()
        mock_settings.elevenlabs_api_key = "test_api_key"

        bot = LaptopBot(settings=mock_settings)

        # Check that voice components are initialized
        mock_transcriber.assert_called_once_with(mock_settings)
        mock_voice_handler.assert_called_once()

        assert bot.transcriber is not None
        assert bot.voice_handler is not None

    @patch("bot.core.Database")
    @patch("bot.core.LLMRecommender")
    @patch("bot.core.QueryParser")
    def test_close_method(self, mock_query_parser, mock_recommender, mock_db):
        """Test that close method cleans up resources."""
        mock_settings = Mock()
        mock_settings.elevenlabs_api_key = ""

        bot = LaptopBot(settings=mock_settings)

        # Call close
        bot.close()

        # Verify cleanup calls
        mock_query_parser.return_value.close.assert_called_once()
        mock_recommender.return_value.close.assert_called_once()
