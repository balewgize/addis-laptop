"""Tests for the LLM extractor."""

import os
import json
from unittest.mock import Mock, patch

import pytest
import httpx

from core.extractor import LaptopExtractor
from core.schemas import LaptopCreate


@pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set",
)
class TestLaptopExtractorIntegration:
    """Integration tests requiring API key."""

    @pytest.mark.slow
    def test_extract_dell_laptop(self, sample_messages):
        """Test extraction of Dell laptop."""
        with LaptopExtractor() as extractor:
            result = extractor.extract(sample_messages[0])

        assert result is not None
        assert isinstance(result, LaptopCreate)
        assert result.brand.lower() == "dell"
        assert result.ram_gb == 16
        assert result.storage_gb == 1000
        assert result.price_etb == 128500

    @pytest.mark.slow
    def test_extract_asus_laptop(self, sample_messages):
        """Test extraction of Asus laptop."""
        with LaptopExtractor() as extractor:
            result = extractor.extract(sample_messages[1])

        assert result is not None
        assert isinstance(result, LaptopCreate)
        assert result.brand.lower() == "asus"
        assert result.ram_gb == 16
        assert result.storage_gb == 1000
        assert result.price_etb == 115500

    @pytest.mark.slow
    def test_extract_non_laptop_returns_none(self, sample_messages):
        """Test that non-laptop messages return None."""
        with LaptopExtractor() as extractor:
            result = extractor.extract(sample_messages[2])

        assert result is None

    @pytest.mark.slow
    def test_extract_with_error_handling(self):
        """Test extraction handles various error cases."""
        with LaptopExtractor() as extractor:
            # Test empty message
            assert extractor.extract("") is None
            # Test very short message
            assert extractor.extract("hi") is None
            # Test message without laptop info
            assert (
                extractor.extract("Looking for a good restaurant in Addis Ababa")
                is None
            )


class TestLaptopExtractorUnit:
    """Unit tests (no API calls)."""

    @patch("httpx.Client")
    def test_initialization(self, mock_client):
        """Test extractor initialization."""
        mock_settings = Mock()
        mock_settings.openrouter_api_key = "test_key"
        mock_settings.llm_model = "test_model"

        extractor = LaptopExtractor(settings=mock_settings)

        mock_client.assert_called_once()
        call_kwargs = mock_client.call_args[1]
        assert call_kwargs["base_url"] == "https://openrouter.ai/api/v1"
        assert "Authorization" in call_kwargs["headers"]
        assert call_kwargs["headers"]["Authorization"] == "Bearer test_key"
        assert call_kwargs["timeout"] == 60.0

    @patch("httpx.Client")
    def test_extract_success_path(self, mock_client):
        """Test successful extraction flow."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"brand": "Dell", "ram_gb": 16, "price_etb": 100000}'
                    }
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_client.return_value.post.return_value = mock_response

        mock_settings = Mock()
        mock_settings.openrouter_api_key = "test_key"
        mock_settings.llm_model = "test_model"

        extractor = LaptopExtractor(settings=mock_settings)

        result = extractor.extract("Test laptop message")

        assert result is not None
        assert isinstance(result, LaptopCreate)
        assert result.brand == "Dell"
        assert result.ram_gb == 16
        assert result.price_etb == 100000

        # Verify API call was made correctly
        mock_client.return_value.post.assert_called_once()
        call_args = mock_client.return_value.post.call_args
        assert call_args[0][0] == "/chat/completions"
        request_data = call_args[1]["json"]
        assert request_data["model"] == "test_model"
        assert len(request_data["messages"]) == 2
        assert "system" in request_data["messages"][0]["role"]
        assert "user" in request_data["messages"][1]["role"]

    @patch("httpx.Client")
    def test_extract_invalid_brand_filtering(self, mock_client):
        """Test that invalid brands are filtered out."""
        # Mock response with invalid brand
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"brand": "unknown", "ram_gb": 16}'}}]
        }
        mock_response.raise_for_status.return_value = None
        mock_client.return_value.post.return_value = mock_response

        mock_settings = Mock()
        extractor = LaptopExtractor(settings=mock_settings)

        result = extractor.extract("Test message")
        assert result is None

    @patch("httpx.Client")
    def test_extract_null_brand_returns_none(self, mock_client):
        """Test that null brand returns None."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"brand": null}'}}]
        }
        mock_response.raise_for_status.return_value = None
        mock_client.return_value.post.return_value = mock_response

        mock_settings = Mock()
        extractor = LaptopExtractor(settings=mock_settings)

        result = extractor.extract("Test message")
        assert result is None

    @patch("httpx.Client")
    def test_extract_api_error_handling(self, mock_client):
        """Test API error handling."""
        # Mock HTTP error
        mock_client.return_value.post.side_effect = httpx.HTTPStatusError(
            "API Error",
            request=Mock(),
            response=Mock(status_code=429, text="Rate limited"),
        )

        mock_settings = Mock()
        extractor = LaptopExtractor(settings=mock_settings)

        result = extractor.extract("Test message")
        assert result is None

    @patch("httpx.Client")
    def test_extract_json_parsing_failure(self, mock_client):
        """Test handling of invalid JSON from LLM."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "not json at all"}}]
        }
        mock_response.raise_for_status.return_value = None
        mock_client.return_value.post.return_value = mock_response

        mock_settings = Mock()
        extractor = LaptopExtractor(settings=mock_settings)

        result = extractor.extract("Test message")
        assert result is None

    @patch("httpx.Client")
    def test_extract_pydantic_validation_failure(self, mock_client):
        """Test handling of invalid data that fails Pydantic validation."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": '{"brand": "Dell", "ram_gb": "invalid"}'}}
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_client.return_value.post.return_value = mock_response

        mock_settings = Mock()
        extractor = LaptopExtractor(settings=mock_settings)

        result = extractor.extract("Test message")
        assert result is None

    @patch("httpx.Client")
    def test_context_manager(self, mock_client):
        """Test context manager functionality."""
        mock_settings = Mock()
        extractor = LaptopExtractor(settings=mock_settings)

        with extractor as ext:
            assert ext is extractor

        # Verify close was called
        mock_client.return_value.close.assert_called_once()

    @patch("httpx.Client")
    def test_close_method(self, mock_client):
        """Test explicit close method."""
        mock_settings = Mock()
        extractor = LaptopExtractor(settings=mock_settings)

        extractor.close()

        mock_client.return_value.close.assert_called_once()


class TestLaptopExtractorValidation:
    """Tests for validation logic."""

    def test_brand_validation_cases(self):
        """Test various brand validation scenarios."""
        from core.extractor import LaptopExtractor

        # Create extractor instance without API client for validation testing
        extractor = LaptopExtractor.__new__(LaptopExtractor)

        # Valid brands should pass
        valid_data = {"brand": "Dell", "ram_gb": 16}
        laptop = LaptopCreate.model_validate(valid_data)
        assert laptop.brand == "Dell"

        # Invalid brands should be filtered
        invalid_brands = ["unknown", "n/a", "null", "none", "Unknown", "N/A"]
        for invalid_brand in invalid_brands:
            # This would normally be caught before validation, but test the logic
            pass  # The filtering happens in extract method, not in schema validation

    def test_schema_validation(self):
        """Test Pydantic schema validation."""
        # Valid data
        valid_data = {
            "brand": "Dell",
            "model": "Inspiron 15",
            "cpu": "Intel Core i7",
            "ram_gb": 16,
            "storage_gb": 512,
            "storage_type": "SSD",
            "screen_size": 15.6,
            "gpu": "Intel Iris Xe",
            "price_etb": 85000.0,
            "condition": "new",
            "battery_life": "8 hrs",
            "contact": "0912345678",
        }
        laptop = LaptopCreate.model_validate(valid_data)
        assert laptop.brand == "Dell"
        assert laptop.ram_gb == 16
        assert laptop.price_etb == 85000.0

        # Test optional fields can be None
        minimal_data = {"brand": "Dell"}
        laptop = LaptopCreate.model_validate(minimal_data)
        assert laptop.brand == "Dell"
        assert laptop.model is None
        assert laptop.ram_gb is None
