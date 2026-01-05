"""LLM-based extraction of laptop specs from unstructured text."""

import json
import logging

import httpx

from .config import Settings, get_settings
from .schemas import LaptopCreate
from .utils import parse_json_from_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a laptop specification extractor for Ethiopian e-commerce Telegram channels.

Extract structured laptop data from messages. Key context:
- Prices are in ETB (Ethiopian Birr). Convert "128,500Birr" to 128500.0
- "Generation" refers to Intel/AMD CPU generations
- Storage: Convert 1TB to 1000, 512GB to 512
- "Brand new" or "New arrival" = condition: "new"

Return valid JSON matching the schema. Use null for missing/unclear fields.
Do NOT guess or make up values - only extract what's explicitly stated.

If the message is not about a laptop listing, return: {"brand": null}"""

USER_PROMPT_TEMPLATE = """Extract laptop details from this Telegram message:

---
{message}
---

Return JSON with these fields:
- brand (string or null): Manufacturer name (Dell, Asus, HP, Lenovo, Apple, etc.)
- model (string or null): Specific model name/number
- cpu (string or null): Processor description
- ram_gb (integer or null): RAM in GB
- storage_gb (integer or null): Storage in GB (convert TB to GB)
- storage_type (string or null): "SSD", "HDD", "NVMe SSD"
- screen_size (number or null): Screen size in inches
- gpu (string or null): Graphics card
- price_etb (number or null): Price in Ethiopian Birr
- condition (string or null): "new", "used", or "refurbished"
- battery_life (string or null): Battery life as "N hrs" (e.g., "8 hrs"). Number only, no "+" or ranges.

JSON only, no explanation:"""


class LaptopExtractor:
    """Extracts structured laptop data using OpenRouter LLMs."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.client = httpx.Client(
            base_url="https://openrouter.ai/api/v1",
            headers={
                "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
        logger.info(
            f"LaptopExtractor initialized with model: {self.settings.llm_model}"
        )

    def extract(self, message: str) -> LaptopCreate | None:
        """Extract laptop data from a message."""
        logger.debug(f"Extracting from message ({len(message)} chars)")

        try:
            response = self.client.post(
                "/chat/completions",
                json={
                    "model": self.settings.llm_model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": USER_PROMPT_TEMPLATE.format(message=message),
                        },
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1000,
                },
            )
            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            logger.debug(f"LLM response: {content[:200]}...")

            parsed = parse_json_from_llm(content)
            if not parsed:
                logger.warning("Failed to parse JSON from LLM response")
                return None

            if parsed.get("brand") is None:
                logger.debug("Message is not a laptop listing")
                return None

            laptop = LaptopCreate.model_validate(parsed)

            if not laptop.brand or laptop.brand.lower() in (
                "unknown",
                "n/a",
                "null",
                "none",
            ):
                logger.debug("Extracted data missing valid brand, skipping")
                return None

            logger.info(f"Extracted: {laptop.brand} {laptop.model or 'Unknown Model'}")
            return laptop

        except httpx.HTTPStatusError as e:
            logger.exception(
                f"OpenRouter API error: {e.response.status_code} - {e.response.text}"
            )
            return None
        except Exception as e:
            logger.exception(f"Extraction failed: {type(e).__name__}: {e}")
            return None

    def close(self):
        """Close the HTTP client."""
        self.client.close()
        logger.debug("LaptopExtractor closed")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
