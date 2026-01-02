"""Tests for the LLM extractor."""

import os
import pytest

from telegram_laptop_scraper.extractor import LaptopExtractor


# Mark all tests in this class as requiring API key
@pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set - skipping integration tests",
)
class TestLaptopExtractorIntegration:
    """Integration tests for LaptopExtractor (requires API key)."""

    @pytest.mark.slow
    def test_extract_dell_laptop(self, sample_messages, expected_extractions):
        """Test extraction of Dell laptop message."""
        with LaptopExtractor() as extractor:
            result = extractor.extract(sample_messages[0])

        assert result is not None
        assert result.brand.lower() == "dell"
        assert result.ram_gb == expected_extractions[0]["ram_gb"]
        assert result.storage_gb == expected_extractions[0]["storage_gb"]
        assert result.price_etb == expected_extractions[0]["price_etb"]
        assert expected_extractions[0]["contact"] in (result.contact or "")

    @pytest.mark.slow
    def test_extract_asus_laptop(self, sample_messages, expected_extractions):
        """Test extraction of Asus laptop message."""
        with LaptopExtractor() as extractor:
            result = extractor.extract(sample_messages[1])

        assert result is not None
        assert result.brand.lower() == "asus"
        assert result.ram_gb == expected_extractions[1]["ram_gb"]
        assert result.price_etb == expected_extractions[1]["price_etb"]

    @pytest.mark.slow
    def test_extract_non_laptop_returns_none(self, sample_messages):
        """Test that non-laptop messages return None."""
        with LaptopExtractor() as extractor:
            result = extractor.extract(sample_messages[2])

        assert result is None

    @pytest.mark.slow
    def test_extract_random_text_returns_none(self):
        """Test that random text returns None."""
        with LaptopExtractor() as extractor:
            result = extractor.extract("Hello, how are you today?")

        assert result is None


class TestLaptopExtractorUnit:
    """Unit tests for LaptopExtractor (no API calls)."""

    def test_parse_json_simple(self):
        """Test JSON parsing with simple input."""
        extractor = LaptopExtractor.__new__(LaptopExtractor)

        result = extractor._parse_json('{"brand": "Dell", "price_etb": 100000}')

        assert result == {"brand": "Dell", "price_etb": 100000}

    def test_parse_json_with_markdown(self):
        """Test JSON parsing with markdown code blocks."""
        extractor = LaptopExtractor.__new__(LaptopExtractor)

        result = extractor._parse_json(
            '```json\n{"brand": "Dell", "price_etb": 100000}\n```'
        )

        assert result == {"brand": "Dell", "price_etb": 100000}

    def test_parse_json_with_extra_text(self):
        """Test JSON parsing when there's extra text around JSON."""
        extractor = LaptopExtractor.__new__(LaptopExtractor)

        result = extractor._parse_json(
            'Here is the extracted data:\n{"brand": "HP", "ram_gb": 16}\nDone!'
        )

        assert result == {"brand": "HP", "ram_gb": 16}

    def test_parse_json_invalid_returns_none(self):
        """Test that invalid JSON returns None."""
        extractor = LaptopExtractor.__new__(LaptopExtractor)

        result = extractor._parse_json("This is not JSON at all")

        assert result is None
