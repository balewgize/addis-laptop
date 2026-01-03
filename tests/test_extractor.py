"""Tests for the LLM extractor."""

import os
import pytest

from core.extractor import LaptopExtractor


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
        assert result.brand.lower() == "dell"
        assert result.ram_gb == 16
        assert result.storage_gb == 1000
        assert result.price_etb == 128500

    @pytest.mark.slow
    def test_extract_non_laptop_returns_none(self, sample_messages):
        """Test that non-laptop messages return None."""
        with LaptopExtractor() as extractor:
            result = extractor.extract(sample_messages[2])

        assert result is None


class TestLaptopExtractorUnit:
    """Unit tests (no API calls)."""

    def test_parse_json_simple(self):
        """Test JSON parsing."""
        extractor = LaptopExtractor.__new__(LaptopExtractor)
        result = extractor._parse_json('{"brand": "Dell", "price_etb": 100000}')
        assert result == {"brand": "Dell", "price_etb": 100000}

    def test_parse_json_with_markdown(self):
        """Test JSON parsing with markdown."""
        extractor = LaptopExtractor.__new__(LaptopExtractor)
        result = extractor._parse_json('```json\n{"brand": "Dell"}\n```')
        assert result == {"brand": "Dell"}

    def test_parse_json_invalid(self):
        """Test invalid JSON returns None."""
        extractor = LaptopExtractor.__new__(LaptopExtractor)
        result = extractor._parse_json("not json")
        assert result is None
